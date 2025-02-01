import json
import logging
import os
from urllib.parse import unquote_plus

import boto3  # type: ignore
from botocore.config import Config  # type: ignore
from botocore.exceptions import ClientError  # type: ignore

os.environ["AWS_DATA_PATH"] = "./models"

QUEUE_URL = os.environ["TRANSFER_RESULT_QUEUE_URL"]
USE_DIODE_SIMULATOR = os.environ["USE_DIODE_SIMULATOR"]
DIODE_SIMULATOR_ENDPOINT = os.environ["DIODE_SIMULATOR_ENDPOINT"]

config = Config(retries={"max_attempts": 5, "mode": "standard"})
diode_endpoint_url = "https://diode.us-gov-west-1.amazonaws.com"
if USE_DIODE_SIMULATOR == "True":
    diode_endpoint_url = DIODE_SIMULATOR_ENDPOINT

DIODE_CLIENT = boto3.client(
    "diode",
    config=config,
    endpoint_url=diode_endpoint_url,
)
S3_CLIENT = boto3.client("s3", config=config)
SQS_CLIENT = boto3.client("sqs", config=config)

logger = logging.getLogger()
logger.setLevel(logging.INFO)


def lambda_handler(event, context):
    logger.info(f"Event: {json.dumps(event, default=str)}")

    msg: dict = json.loads(event["Records"][0]["body"])
    records = msg.get("Records")

    if records:  # event_source == "aws:s3"
        handle_create_transfer(msg)
    else:  # event_source == "aws:sqs"
        handle_transfer_status_event(msg)


def handle_create_transfer(msg: dict):
    logger.info("Processing a create transfer request")

    bucket = msg["Records"][0]["s3"]["bucket"]["name"]
    # unquote_plus for handling any whitespaces in the key name
    key = unquote_plus(msg["Records"][0]["s3"]["object"]["key"])
    mapping_id = get_mapping_id(bucket, key)

    logger.info(f"Bucket: {bucket}, Key: {key}")
    logger.info(f"Mapping ID: {mapping_id}")

    try:
        create_transfer(mapping_id, bucket, key)
    except ClientError as e:
        logger.error(f"Failed to create the transfer request for {key}")
        logger.error(e)
        send_status_message(
            bucket,
            key,
            mapping_id,
            "FAILED",
            "CREATE_TRANSFER_FAILED",
        )


def handle_transfer_status_event(msg: dict):
    logger.info("Processing a transfer status event")

    event_detail = msg["detail"]
    bucket = event_detail["s3Bucket"]
    key = event_detail["s3Key"]
    mapping_id = event_detail["mappingId"]
    status = event_detail["status"]
    transfer_id = event_detail["transferId"]

    logger.info(f"Bucket: {bucket}, Key: {key}")
    logger.info(f"Mapping ID: {mapping_id}")
    logger.info(f"Transfer Status: {status}")

    if status != "SUCCEEDED":
        describe_transfer(transfer_id)

    send_status_message(bucket, key, mapping_id, status, transfer_id)


def send_status_message(
    bucket: str,
    key: str,
    mapping_id: str,
    status: str,
    transfer_id: str,
):
    logger.info("Sending a message on transfer status to SQS queue")

    SQS_CLIENT.send_message(
        QueueUrl=QUEUE_URL,
        MessageBody=json.dumps(
            {
                "bucket": bucket,
                "key": key,
                "mappingId": mapping_id,
                "status": status,
                "transferId": transfer_id,
            },
        ),
    )

    logger.info("Message sent successfully")


def get_mapping_id(bucket, key) -> str:
    tags = get_object_tagging(bucket, key)
    mapping_id = tags.get("MappingId")
    if not mapping_id:
        raise ValueError(f"No MappingId tag found for {bucket}/{key}")

    return mapping_id


def get_object_tagging(
    bucket: str,
    key: str,
    expected_bucket_owner: str = "",
) -> dict[str, str]:
    """
    expected_bucket_owner: (optional) 12-digit account ID
    """
    logger.info(f"Getting tags for {bucket}/{key}")

    params = dict(Bucket=bucket, Key=key)
    if expected_bucket_owner:
        params["ExpectedBucketOwner"] = expected_bucket_owner

    tag_set = S3_CLIENT.get_object_tagging(**params)["TagSet"]
    tags = {tag["Key"]: tag["Value"] for tag in tag_set}
    logger.info(f"Tags: {tags}")

    return tags


def create_transfer(mapping_id: str, bucket: str, key: str, include_tags=True):
    logger.info(f"Creating a transfer request for {bucket}/{key}")

    response = DIODE_CLIENT.create_transfer(
        mappingId=mapping_id,
        s3Bucket=bucket,
        s3Key=key,
        # Take the last 100 chars of the key as description
        description=key.split("/")[-1][-100:],
        includeS3ObjectTags=include_tags,
    )["transfer"]

    logger.info(f"Transfer request created: {response}")


def describe_transfer(transfer_id: str):
    logger.info(f"Getting details for transfer: {transfer_id}")

    try:
        response = DIODE_CLIENT.describe_transfer(transferId=transfer_id)["transfer"]
        logger.info(f"Details: {response}")
    except ClientError as e:
        logger.warning(f"Failed to get transfer details: {e}")
