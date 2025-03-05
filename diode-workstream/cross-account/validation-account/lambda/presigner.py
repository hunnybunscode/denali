import json
import logging

import boto3  # type: ignore
from botocore.config import Config  # type: ignore

logger = logging.getLogger()
logger.setLevel(logging.INFO)

config = Config(
    retries={"max_attempts": 5, "mode": "standard"},
    signature_version="s3v4",
)
S3_CLIENT = boto3.client("s3", config=config)


def lambda_handler(event, context):
    logger.info(f"Event: {json.dumps(event, default=str)}")

    bucket = event["queryStringParameters"]["bucket"]
    key = event["queryStringParameters"]["key"]
    kms_key_id = event["queryStringParameters"]["kms_key_id"]

    logger.info(f"Bucket: {bucket}")
    logger.info(f"Key: {key}")
    logger.info(f"KMS Key ID: {kms_key_id}")

    # Default encryption is the AWS-managed KMS key
    fields = {"x-amz-server-side-encryption": "aws:kms"}
    # If a CMK was specified, the customer-managed KMS key will be used
    if kms_key_id:
        fields |= {"x-amz-server-side-encryption-aws-kms-key-id": kms_key_id}

    params = dict(
        Bucket=bucket,
        Key=key,
        Fields=fields,
        Conditions=[{k: v} for k, v in fields.items()],
    )
    response = S3_CLIENT.generate_presigned_post(**params)

    logger.info(f"Response Body: {response}")

    response = {
        "statusCode": 200,
        "body": json.dumps(response),
        "isBase64Encoded": False,
    }

    return response
