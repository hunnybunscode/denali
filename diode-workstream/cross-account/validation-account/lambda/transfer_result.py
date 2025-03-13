import json
import logging
import os
import zoneinfo
from datetime import datetime

import boto3  # type: ignore
from botocore.config import Config  # type: ignore
from botocore.exceptions import ClientError  # type: ignore

DATA_TRANSFER_BUCKET = os.environ["DATA_TRANSFER_BUCKET"]
FAILED_TRANSFER_BUCKET = os.environ["FAILED_TRANSFER_BUCKET"]

DDB_TABLE_NAME = os.environ["DYNAMODB_TABLE_NAME"]
FAILED_TRANSFER_TOPIC_ARN = os.environ["FAILED_TRANSFER_TOPIC_ARN"]
ACCOUNT_ID = os.environ["ACCOUNT_ID"]

SUCCEEDED = "SUCCEEDED"
DATA_TAG_KEY = "DataOwner / DataSteward / GovPOC / KeyOwner"
UNKNOWNS = ["Unknown"] * 4

config = Config(retries={"max_attempts": 5, "mode": "standard"})
DDB_CLIENT = boto3.client("dynamodb", config=config)
S3_CLIENT = boto3.client("s3", config=config)
SNS_CLIENT = boto3.client("sns", config=config)

logger = logging.getLogger()
logger.setLevel(logging.INFO)


def lambda_handler(event, context):
    logger.info(f"Event: {json.dumps(event, default=str)}")

    message = event["Records"][0]
    # SentTimestamp is in the epoch time in milliseconds
    timestamp = int(message["attributes"]["SentTimestamp"]) / 1000
    data = json.loads(message["body"])
    # bucket = data["bucket"]
    key = data["key"]
    status = data["status"]

    # TODO: Get the tags passed from the message
    data_tag_values = get_data_tag_values(key)
    put_item_in_ddb(timestamp, data, *data_tag_values)

    if status != SUCCEEDED:
        logger.warning(f"Data transfer failed for {key}")
        copy_object_to_failed_transfer_bucket(key)
        send_sns_notification_on_failed_transfer(key)

    # Delete it from the transfer bucket whether the transfer was successful or not
    delete_object_from_transfer_bucket(key)


def copy_object_to_failed_transfer_bucket(key: str):
    logger.info(
        f"Copying {key} from {DATA_TRANSFER_BUCKET} to {FAILED_TRANSFER_BUCKET}",
    )
    try:
        S3_CLIENT.copy_object(
            # Source bucket/key/owner
            CopySource={"Bucket": DATA_TRANSFER_BUCKET, "Key": key},
            ExpectedSourceBucketOwner=ACCOUNT_ID,
            # Destination bucket/key/owner
            Bucket=FAILED_TRANSFER_BUCKET,
            Key=key,
            ExpectedBucketOwner=ACCOUNT_ID,
        )
    except ClientError as e:
        if e.response["Error"]["Code"] in ("404", "NoSuchKey"):
            logger.warning(f"{key} not found")
            return
        raise


def send_sns_notification_on_failed_transfer(key: str):
    logger.info("Sending an SNS message regarding the failed transfer")
    SNS_CLIENT.publish(
        TopicArn=FAILED_TRANSFER_TOPIC_ARN,
        Subject="Failed Cross Domain Transfer",
        Message=(
            f"The file, {key}, was NOT successfully transferred.\n"
            f"It has been saved in the Failed Transfer Bucket: {FAILED_TRANSFER_BUCKET}"
        ),
    )


def delete_object_from_transfer_bucket(key: str):
    logger.info(f"Deleting {DATA_TRANSFER_BUCKET}/{key}")
    try:
        S3_CLIENT.delete_object(
            Bucket=DATA_TRANSFER_BUCKET,
            Key=key,
            ExpectedBucketOwner=ACCOUNT_ID,
        )
    except ClientError as e:
        if e.response["Error"]["Code"] in ("404", "NoSuchKey"):
            logger.warning(f"{key} not found")
            return
        raise


def get_data_tag_values(key: str) -> list[str]:
    """
    Returns values for tag key `DataOwner / DataSteward / GovPOC / KeyOwner`
    as individual values in a list.\n
    If the tag is not set, returns "Unknown" x 4 in a list.
    """
    logger.info(f"Getting tags for {key}")
    tags = get_object_tags(key)
    data_tag_value = tags.get(DATA_TAG_KEY)
    if data_tag_value is None:
        logger.warning(f"The object did not have {DATA_TAG_KEY} tag key")
        return UNKNOWNS
    logger.info("Successfully retrieved the data tag value")
    return [tag.strip() for tag in data_tag_value.split("/")]


def get_object_tags(key: str) -> dict[str, str]:
    """
    Returns `TagSet` for `key` in `bucket` in a dict.
    """
    tag_set = S3_CLIENT.get_object_tagging(
        Bucket=DATA_TRANSFER_BUCKET,
        Key=key,
        ExpectedBucketOwner=ACCOUNT_ID,
    )["TagSet"]

    tags = {tag["Key"]: tag["Value"] for tag in tag_set}
    logger.info(f"Tags for {key}: {tags}")
    return tags


def put_item_in_ddb(
    timestamp: float,
    data: dict,
    data_owner: str,
    data_steward: str,
    gov_poc: str,
    key_owner: str,
):
    s3_key = data["key"]
    logger.info(f"Adding an entry into DynamoDB on the transfer status of {s3_key}")
    DDB_CLIENT.put_item(
        TableName=DDB_TABLE_NAME,
        Item={
            "s3Key": {"S": s3_key},  # partition key
            "timestamp": {
                "S": str(
                    datetime.fromtimestamp(
                        timestamp,
                        zoneinfo.ZoneInfo("America/New_York"),  # sort key
                    ),
                ),
            },
            "mappingId": {"S": data["mappingId"]},
            "status": {"S": data["status"]},
            "transferId": {"S": data["transferId"]},
            "error": {"S": data["error"]},
            "dataOwner": {"S": data_owner},
            "dataSteward": {"S": data_steward},
            "govPoc": {"S": gov_poc},
            "keyOwner": {"S": key_owner},
        },
    )
    logger.info("Successfully added the entry")
