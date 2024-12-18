import json
import logging
import os

import boto3  # type: ignore
from botocore.config import Config  # type: ignore

logger = logging.getLogger()
logger.setLevel(logging.INFO)


GOV_POC = os.environ["GOV_POC"]
DATA_OWNER = os.environ["DATA_OWNER"]
KEY_OWNER = os.environ["KEY_OWNER"]
CDS_PROFILE = os.environ["CDS_PROFILE"]

QUEUE_URL = os.environ["QUEUE_URL"]

config = Config(retries={"max_attempts": 5, "mode": "standard"})
S3_CLIENT = boto3.client("s3", config=config)
SQS_CLIENT = boto3.client("sqs", config=config)


def lambda_handler(event, context):
    bucket = event["Records"][0]["s3"]["bucket"]["name"]
    key = event["Records"][0]["s3"]["object"]["key"]

    add_tags(bucket, key)
    send_to_sqs(bucket, key)


def add_tags(bucket: str, key: str):
    # Amazon S3 limits the maximum number of tags to 10 tags per object
    tags = [
        {"Key": "GovPOC", "Value": GOV_POC},
        {"Key": "DataOwner", "Value": DATA_OWNER},
        {"Key": "KeyOwner", "Value": KEY_OWNER},
        {"Key": "CDSProfile", "Value": CDS_PROFILE}
    ]

    response = S3_CLIENT.put_object_tagging(
        Bucket=bucket,
        Key=key,
        Tagging={
            "TagSet": tags
        },

        # TODO: We should add this for enhanced security
        # ExpectedBucketOwner
    )

    logger.info(f"PutObjectTagging response = {response}")


def send_to_sqs(bucket, key):
    response = SQS_CLIENT.send_message(
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

    logger.info(f"SendMessage response: {response}")
