import json
import logging
import os
from urllib.parse import unquote_plus

import boto3  # type: ignore
from botocore.config import Config  # type: ignore
from botocore.exceptions import ClientError  # type: ignore

logger = logging.getLogger()
logger.setLevel(logging.INFO)


AV_SCAN_QUEUE_URL = os.environ["AV_SCAN_QUEUE_URL"]

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
    add_tags_to_key(bucket, key, tagset)
    send_to_sqs(bucket, key)
    logger.info("SUCCESS")


def get_bucket_tags(bucket: str):
    logger.info(f"Getting tags for {bucket}")
    try:
        tagset: list[dict[str, str]] = S3_CLIENT.get_bucket_tagging(Bucket=bucket)[
            "TagSet"
        ]
        # ExpectedBucketOwner='string'
        user_tagset = [tag for tag in tagset if not tag["Key"].startswith("aws:")]

        logger.info(f"Retrieved the tags: {user_tagset}")
        return user_tagset
    except Exception as e:
        logger.error(f"Could not get tags for {bucket}: {e}")
        raise


def add_tags_to_key(bucket: str, key: str, tagset: list[dict[str, str]]):
    logger.info(f"Adding tags to {bucket}/{key}")
    try:
        S3_CLIENT.put_object_tagging(
            Bucket=bucket,
            Key=key,
            Tagging={"TagSet": tagset},
            # TODO: We should add this for enhanced security
            # ExpectedBucketOwner
        )
    except ClientError as e:
        logger.error(f"Could not add tags: {e}")
        raise


def send_to_sqs(bucket, key):
    logger.info(f"Sending a message to the SQS queue for {bucket}/{key}")
    try:
        SQS_CLIENT.send_message(
            QueueUrl=AV_SCAN_QUEUE_URL,
            MessageBody=json.dumps(
                {"detail": {"requestParameters": {"bucketName": bucket, "key": key}}},
            ),
        )
        logger.info("Sent the message")
    except ClientError as e:
        logger.error(f"Could not send message to SQS: {e}")
        raise
