import json
import logging
import os
from urllib.parse import unquote_plus

import boto3  # type: ignore
from botocore.config import Config  # type: ignore

logger = logging.getLogger()
logger.setLevel(logging.INFO)


QUEUE_URL = os.environ["QUEUE_URL"]
TAGS = [
    {"Key": "GovPOC", "Value": os.environ["GOV_POC"]},
    {"Key": "DataOwner", "Value": os.environ["DATA_OWNER"]},
    {"Key": "KeyOwner", "Value": os.environ["KEY_OWNER"]},
    {"Key": "CDSProfile", "Value": os.environ["CDS_PROFILE"]}
]

config = Config(retries={"max_attempts": 5, "mode": "standard"})
S3_CLIENT = boto3.client("s3", config=config)
SQS_CLIENT = boto3.client("sqs", config=config)


def lambda_handler(event, context):
    bucket = event["Records"][0]["s3"]["bucket"]["name"]
    key = unquote_plus(event["Records"][0]["s3"]["object"]["key"])

    logger.info(
        f"Adding tags and sending a message to the SQS queue for Bucket: {bucket}, Key: {key}"  # noqa: E501
    )
    add_tags(bucket, key)
    send_to_sqs(bucket, key)
    logger.info("SUCCESS")


def add_tags(bucket: str, key: str):
    S3_CLIENT.put_object_tagging(
        Bucket=bucket,
        Key=key,
        Tagging={
            "TagSet": TAGS
        },

        # TODO: We should add this for enhanced security
        # ExpectedBucketOwner
    )


def send_to_sqs(bucket, key):
    SQS_CLIENT.send_message(
        QueueUrl=QUEUE_URL,
        MessageBody=json.dumps({
            "detail": {
                "requestParameters": {
                    "bucketName": bucket,
                    "key": key
                }
            }
        })
    )
