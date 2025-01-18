import json
import logging

import boto3  # type: ignore
from botocore.config import Config  # type: ignore

logger = logging.getLogger()
logger.setLevel(logging.INFO)

config = Config(retries={"max_attempts": 5, "mode": "standard"})
S3_CLIENT = boto3.client("s3", config=config)


def lambda_handler(event, context):
    logger.info(f"Event: {json.dumps(event, default=str)}")

    bucket = event["queryStringParameters"]["bucket"]
    key = event["queryStringParameters"]["key"]

    logger.info(f"Bucket: {bucket}")
    logger.info(f"Key: {key}")

    response = S3_CLIENT.generate_presigned_post(Bucket=bucket, Key=key)

    logger.info(f"Response Body: {response}")

    response = {
        "statusCode": 200,
        "body": json.dumps(response),
        "isBase64Encoded": False,
    }

    return response
