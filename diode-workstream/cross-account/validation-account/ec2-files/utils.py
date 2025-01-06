import logging
from pathlib import Path

import boto3  # type: ignore
from botocore.config import Config  # type: ignore
from botocore.exceptions import ClientError  # type: ignore

logging.basicConfig(format="%(message)s", filename="/var/log/messages", level=logging.INFO)  # noqa: E501
logger = logging.getLogger()


# TODO: Do not hard-code the region
region = "us-gov-west-1"
config = Config(retries={"max_attempts": 5, "mode": "standard"})
S3_CLIENT = boto3.client("s3", config=config, region_name=region)
SSM_CLIENT = boto3.client("ssm", config=config, region_name=region)
SNS_CLIENT = boto3.client("sns", config=config, region_name=region)
SQS_CLIENT = boto3.client("sqs", config=config, region_name=region)


def delete_object(bucket: str, key: str, bucket_owner: str | None = None, raise_error=True):
    try:
        logger.info(f"Deleting {bucket}/{key}")
        params = dict(
            Bucket=bucket,
            Key=key
        )
        if bucket_owner:
            params["ExpectedBucketOwner"] = bucket_owner

        S3_CLIENT.delete_object(**params)
        logger.info("Successfully deleted the object")
    except ClientError as e:
        logger.error(f"Could not delete the object: {e}")  # nosemgrep
        if raise_error:
            raise


def copy_object(src_bucket: str, dest_bucket: str, key: str, src_bucket_owner: str | None = None, dest_bucket_owner: str | None = None, raise_error=True):
    try:
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
    except ClientError as e:
        logger.error(f"Could not copy the object: {e}")  # nosemgrep
        if raise_error:
            raise


def publish_sns_message(topic_arn: str, message: str, subject: str | None = None, raise_error=True):
    try:
        logger.info(f"Publishing a message to {topic_arn.split(':')[5]} SNS topic")  # noqa: E501
        params = dict(
            TopicArn=topic_arn,
            Message=message
        )
        if subject:
            params["Subject"] = subject

        SNS_CLIENT.publish(**params)
        logger.info("Successfully published the message")
    except ClientError as e:
        logger.error(f"Could not publish the message: {e}")  # nosemgrep
        if raise_error:
            raise


def delete_sqs_message(queue_url: str, receipt_handle: str, raise_error=True):
    try:
        logger.info(f"Deleting a message from {queue_url} SQS queue with {receipt_handle}")  # noqa: E501
        SQS_CLIENT.delete_message(
            QueueUrl=queue_url,
            ReceiptHandle=receipt_handle
        )
        logger.info("Successfully deleted the message")
    except ClientError as e:
        logger.error(f"Could not delete the message: {e}")  # nosemgrep
        if raise_error:
            raise


def get_param_value(name: str, with_decryption=False, raise_error=True) -> str:
    try:
        logger.info(f"Getting the value of {name} parameter")
        value = SSM_CLIENT.get_parameter(
            Name=name,
            WithDecryption=with_decryption
        )["Parameter"]["Value"]
        logger.info("Successfully retrieved the value")
        return value
    except ClientError as e:
        logger.error(f"Could not get the value: {e}")  # nosemgrep
        if raise_error:
            raise


def send_file_quarantined_msg(bucket: str, key: str, quarantine_reason: str, raise_error=True):
    try:
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
    except ClientError as e:
        logger.error(f"Could not send the message: {e}")  # nosemgrep
        if raise_error:
            raise


def create_tags(error_status: str, mime_type: str):
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
