import json
import logging
import os
import zoneinfo
from datetime import datetime

import boto3  # type: ignore
from botocore.config import Config  # type: ignore
from botocore.exceptions import ClientError  # type: ignore

DDB_TABLE_NAME = os.environ["DYNAMODB_TABLE_NAME"]
DATA_TRANSFER_BUCKET = os.environ["DATA_TRANSFER_BUCKET"]
FAILED_TRANSFER_TOPIC_ARN = os.environ["FAILED_TRANSFER_TOPIC_ARN"]
FAILED_TRANSFER_BUCKET = os.environ["FAILED_TRANSFER_BUCKET"]
ACCOUNT_ID = os.environ["ACCOUNT_ID"]

config = Config(retries={"max_attempts": 5, "mode": "standard"})
DDB_CLIENT = boto3.client("dynamodb", config=config)
S3_CLIENT = boto3.client("s3", config=config)
SNS_CLIENT = boto3.client("sns", config=config)

logger = logging.getLogger()
logger.setLevel(logging.INFO)


def lambda_handler(event, context):
    logger.info(f"Event: {json.dumps(event, default=str)}")

    data = json.loads(event["Records"][0]["body"])
    bucket = data["bucket"]
    key = data["key"]
    status = data["status"]

    data_owner, gov_poc, key_owner = get_object_tagging(bucket, key)
    put_item_in_ddb(data, data_owner, gov_poc, key_owner)

    if status != "SUCCEEDED":
        logger.info(
            f"Data transfer failed; copying {bucket}/{key} to {FAILED_TRANSFER_BUCKET}",  # noqa: E501
        )
        # Copy the failed S3 object to the failed transfer bucket
        copy_object(DATA_TRANSFER_BUCKET, FAILED_TRANSFER_BUCKET, key)
        # Send a message to the SNS topic for failed data transfers
        send_transfer_error_message(key)

    delete_object(DATA_TRANSFER_BUCKET, key)


def get_object_tagging(bucket: str, key: str):
    """
    Returns values for tag keys `data_owner`, `gov_poc`, and `key_owner`
    for `key` in `bucket`.\n
    If any of these tags are not set, returns "unknown".
    """
    unknown = "unknown"
    try:
        logger.info(f"Getting tags for {bucket}/{key}")

        tags = _get_object_tagging(bucket, key)
        data_owner = tags.get("DataOwner", unknown)
        gov_poc = tags.get("GovPOC", unknown)
        key_owner = tags.get("KeyOwner", unknown)

        logger.info("Successfully retrieved the tags")
        return data_owner, gov_poc, key_owner
    except ClientError as e:
        logger.error(f"Failed to get object tags: {e}")
        return unknown, unknown, unknown


def _get_object_tagging(bucket: str, key: str) -> dict[str, str]:
    """
    Returns `TagSet` for `key` in `bucket` in a dict.
    """
    tag_set = S3_CLIENT.get_object_tagging(
        Bucket=bucket,
        Key=key,
        ExpectedBucketOwner=ACCOUNT_ID,
    )["TagSet"]

    tags = {tag["Key"]: tag["Value"] for tag in tag_set}
    logger.info(f"Tags for {bucket}/{key}: {tags}")
    return tags


def put_item_in_ddb(
    data: dict,
    data_owner: str,
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
                    datetime.now(zoneinfo.ZoneInfo("America/New_York")),  # sort key
                ),
            },
            "mappingId": {"S": data["mappingId"]},
            "status": {"S": data["status"]},
            "transferId": {"S": data["transferId"]},
            "dataOwner": {"S": data_owner},
            "govPoc": {"S": gov_poc},
            "keyOwner": {"S": key_owner},
        },
    )

    logger.info("Successfully added the entry")


def send_transfer_error_message(key: str):
    logger.info("Sending an SNS message regarding the failed transfer")

    SNS_CLIENT.publish(
        TopicArn=FAILED_TRANSFER_TOPIC_ARN,
        Subject="Failed Cross Domain Transfer",
        Message=(
            f"The file {key} was NOT successfully transferred.\n"
            "It has been moved from the Data Transfer bucket to "
            f"the following location:\n{FAILED_TRANSFER_BUCKET}/{key}"
        ),
    )


def copy_object(src_bucket: str, dest_bucket: str, key: str):
    logger.info(f"Copying {src_bucket}/{key} to {dest_bucket}/{key}")

    S3_CLIENT.copy_object(
        # Source bucket/key/owner
        CopySource={"Bucket": src_bucket, "Key": key},
        ExpectedSourceBucketOwner=ACCOUNT_ID,
        # Destination bucket/key/owner
        Bucket=dest_bucket,
        Key=key,
        ExpectedBucketOwner=ACCOUNT_ID,
    )

    logger.info("Successfully copied the object")


def delete_object(bucket: str, key: str):
    logger.info(f"Deleting {bucket}/{key}")

    S3_CLIENT.delete_object(
        Bucket=bucket,
        Key=key,
        ExpectedBucketOwner=ACCOUNT_ID,
    )

    logger.info("Successfully deleted the object")
