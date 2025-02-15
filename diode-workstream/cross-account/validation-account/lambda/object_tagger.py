import json
import logging
import os
from urllib.parse import unquote_plus

import boto3  # type: ignore
from botocore.config import Config  # type: ignore

logger = logging.getLogger()
logger.setLevel(logging.INFO)


AV_SCAN_QUEUE_URL = os.environ["AV_SCAN_QUEUE_URL"]
ACCOUNT_ID = os.environ["ACCOUNT_ID"]

config = Config(retries={"max_attempts": 5, "mode": "standard"})
S3_CLIENT = boto3.client("s3", config=config)
SQS_CLIENT = boto3.client("sqs", config=config)


def lambda_handler(event, context):
    logger.info(f"Event: {json.dumps(event, default=str)}")
    record: dict = event["Records"][0]
    bucket = record["s3"]["bucket"]["name"]
    key = unquote_plus(record["s3"]["object"]["key"])
    principal_id = record.get("userIdentity", {}).get("principalId", "")
    source_ip = record.get("requestParameters", {}).get("sourceIPAddress", "")

    tagset = get_bucket_tags(bucket)
    tagset.append(
        {"Key": "PrincipalId + SourceIp", "Value": f"{principal_id} + {source_ip}"},
    )
    add_tags_to_object(bucket, key, tagset)
    send_to_sqs(bucket, key)
    logger.info("SUCCESS")


def get_bucket_tags(bucket: str):
    logger.info(f"Getting tags for {bucket}")
    params = dict(Bucket=bucket, ExpectedBucketOwner=ACCOUNT_ID)
    tagset: list[dict[str, str]] = S3_CLIENT.get_bucket_tagging(**params)["TagSet"]
    user_tagset = [tag for tag in tagset if not tag["Key"].startswith("aws:")]
    logger.info(f"Retrieved the tags: {user_tagset}")
    return user_tagset


def add_tags_to_object(bucket: str, key: str, tagset: list[dict[str, str]]):
    logger.info(f"Adding tags to {bucket}/{key}")
    S3_CLIENT.put_object_tagging(
        Bucket=bucket,
        Key=key,
        Tagging={"TagSet": tagset},
        ExpectedBucketOwner=ACCOUNT_ID,
    )


def send_to_sqs(bucket, key):
    logger.info(f"Sending a message to the SQS queue for {bucket}/{key}")
    SQS_CLIENT.send_message(
        QueueUrl=AV_SCAN_QUEUE_URL,
        MessageBody=json.dumps(
            {"detail": {"requestParameters": {"bucketName": bucket, "key": key}}},
        ),
    )
