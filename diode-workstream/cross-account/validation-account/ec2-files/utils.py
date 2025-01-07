import logging
from pathlib import Path

import boto3  # type: ignore
from botocore.config import Config  # type: ignore

logging.basicConfig(format="%(message)s", filename="/var/log/messages", level=logging.INFO)  # noqa: E501
logger = logging.getLogger()


# TODO: Do not hard-code the region
region = "us-gov-west-1"
config = Config(retries={"max_attempts": 5, "mode": "standard"})
S3_CLIENT = boto3.client("s3", config=config, region_name=region)
SSM_CLIENT = boto3.client("ssm", config=config, region_name=region)
SNS_CLIENT = boto3.client("sns", config=config, region_name=region)
SQS_CLIENT = boto3.client("sqs", config=config, region_name=region)


def delete_object(bucket: str, key: str, bucket_owner: str | None = None):
    logger.info(f"Deleting {bucket}/{key}")
    params = dict(
        Bucket=bucket,
        Key=key
    )
    if bucket_owner:
        params["ExpectedBucketOwner"] = bucket_owner

    S3_CLIENT.delete_object(**params)
    logger.info("Successfully deleted the object")


def copy_object(src_bucket: str, dest_bucket: str, key: str, src_bucket_owner: str | None = None, dest_bucket_owner: str | None = None):
    logger.info(f"Copying {src_bucket}/{key} to {dest_bucket}/{key}")
    params = dict(
        CopySource={"Bucket": src_bucket, "Key": key},
        Bucket=dest_bucket,
        Key=key,
    )
    if src_bucket_owner:
        params["ExpectedSourceBucketOwner"] = src_bucket_owner
    if dest_bucket_owner:
        params["ExpectedBucketOwner"] = dest_bucket_owner

    S3_CLIENT.copy_object(**params)
    logger.info("Successfully copied the object")


def publish_sns_message(topic_arn: str, message: str, subject: str | None = None):
    logger.info(f"Publishing a message to {topic_arn.split(':')[5]} SNS topic")  # noqa: E501
    params = dict(
        TopicArn=topic_arn,
        Message=message
    )
    if subject:
        params["Subject"] = subject

    SNS_CLIENT.publish(**params)
    logger.info("Successfully published the message")


def delete_sqs_message(queue_url: str, receipt_handle: str):
    logger.info(f"Deleting a message from {queue_url} SQS queue with {receipt_handle}")  # noqa: E501
    SQS_CLIENT.delete_message(
        QueueUrl=queue_url,
        ReceiptHandle=receipt_handle
    )
    logger.info("Successfully deleted the message")


def get_param_value(name: str, with_decryption=False) -> str:
    logger.info(f"Getting the value of {name} parameter")
    value = SSM_CLIENT.get_parameter(
        Name=name,
        WithDecryption=with_decryption
    )["Parameter"]["Value"]
    logger.info("Successfully retrieved the value")
    return value


def send_file_quarantined_sns_msg(bucket: str, key: str, quarantine_reason: str):
    logger.info(f"Sending a message regarding the quarantined file, {key}")
    topic_arn = get_param_value("/pipeline/QuarantineTopicArn")
    message = (
        "A file has been quarantined.\n\n"
        f"Quarantine Reason: {quarantine_reason}.\n"
        f"File: {key}\n"
        f"File Location: {bucket}/{key}"
    )
    publish_sns_message(topic_arn, message, quarantine_reason)
    logger.info("Successfully sent the message")


def create_tags_for_file_validation(error_status: str, mime_type: str):
    """
    Returns: {
        "ERROR_STATUS": error_status,
        "MIME_TYPE": mime_type
    }
    """
    return {
        "ERROR_STATUS": error_status,
        "MIME_TYPE": mime_type
    }


def empty_dir(dir: str):
    """
    Deletes all files and subdirectories in the given directory.\n
    Errors are logged, but ignored.
    """
    try:
        dir_path = Path(dir)

        if not dir_path.exists():
            logger.warning(f"{dir} directory does NOT exist")
            return
        if not dir_path.is_dir():
            logger.warning(f"{dir} is NOT a directory")
            return

        logger.info(f"Emptying directory: {dir}")
        for path in dir_path.iterdir():
            if path.is_file():
                path.unlink(missing_ok=True)
            if path.is_dir():
                empty_dir(path)
                path.rmdir()
        logger.info("Successfully emptied the directory")
    except Exception as e:
        logger.error(f"Could not empty the directory: {e}")
