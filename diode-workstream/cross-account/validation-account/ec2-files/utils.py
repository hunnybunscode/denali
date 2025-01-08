import logging
from pathlib import Path

import boto3  # type: ignore
import puremagic  # type: ignore
from botocore.config import Config  # type: ignore
from botocore.exceptions import ClientError  # type: ignore

logger = logging.getLogger()

INGESTION_DIR = "/usr/bin/files"

# TODO: Do not hard-code the region
region = "us-gov-west-1"
config = Config(retries={"max_attempts": 5, "mode": "standard"})
S3_CLIENT = boto3.client("s3", config=config, region_name=region)
SSM_CLIENT = boto3.client("ssm", config=config, region_name=region)
SNS_CLIENT = boto3.client("sns", config=config, region_name=region)
SQS_CLIENT = boto3.client("sqs", config=config, region_name=region)


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
        return True
    except Exception as e:
        if raise_error:
            raise e

        logger.error(f"Failed to copy the object: {e}")
        return False


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
        return True
    except Exception as e:
        if raise_error:
            raise e

        logger.error(f"Failed to delete the object: {e}")
        return False


def get_object_tagging(bucket: str, key: str, bucket_owner: str | None = None) -> dict[str, str]:
    logger.info(f"Getting tags for {bucket}/{key}")
    params = dict(
        Bucket=bucket,
        Key=key
    )
    if bucket_owner:
        params["ExpectedBucketOwner"] = bucket_owner

    tag_set = S3_CLIENT.get_object_tagging(**params)["TagSet"]
    logger.info("Successfully retrieved the tags")
    return {tag["Key"]: tag["Value"] for tag in tag_set}


def put_object_tagging(bucket: str, key: str, tags: dict[str, str], bucket_owner: str | None = None) -> dict[str, str]:
    logger.info(f"Putting tags for {bucket}/{key}")
    tag_set = [{"Key": k, "Value": v} for k, v in tags.items()]
    params = dict(
        Bucket=bucket,
        Key=key,
        Tagging={"TagSet": tag_set}
    )
    if bucket_owner:
        params["ExpectedBucketOwner"] = bucket_owner

    S3_CLIENT.put_object_tagging(**params)
    logger.info("Successfully put the tags")


def download_file(bucket: str, key: str, filename: str, bucket_owner: str | None = None):
    logger.info(f"Downloading {bucket}/{key} to {filename}")
    params = dict(
        Bucket=bucket,
        Key=key,
        Filename=filename
    )
    if bucket_owner:
        params["ExtraArgs"] = {"ExpectedBucketOwner": bucket_owner}

    S3_CLIENT.download_file(**params)
    logger.info("Successfully downloaded the file")


def add_tags(bucket: str, key: str, tags_to_add: dict[str, str], bucket_owner: str | None = None):
    """
    `ClientError`s are logged, but ignored
    """
    try:
        logger.info(f"Adding tags to {bucket}/{key}")
        existing_tags = get_object_tagging(bucket, key, bucket_owner)
        combined_tags = existing_tags | tags_to_add
        put_object_tagging(bucket, key, combined_tags, bucket_owner)
        logger.info("Successfully added the tags")
    except ClientError as e:
        logger.warning(f"ERROR: Exception ocurred while adding tags: {e}")
        pass


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


def send_sqs_message(queue_url: str, message: str, delay_seconds: int | None = None):
    queue_name = queue_url.split("/")[-1]
    logger.info(f"Sending a message to {queue_name} SQS queue")
    params = dict(
        QueueUrl=queue_url,
        MessageBody=message
    )
    if delay_seconds is not None:
        params["DelaySeconds"] = delay_seconds

    SQS_CLIENT.send_message(**params)
    logger.info("Successfully sent the message")


def receive_sqs_message(queue_url: str, max_num_of_messages=1):
    queue_name = queue_url.split("/")[-1]
    logger.info(f"Checking for messages from {queue_name} SQS queue")
    response: dict = SQS_CLIENT.receive_message(
        QueueUrl=queue_url,
        MaxNumberOfMessages=max_num_of_messages
    )
    messages: list = response.get("Messages")
    if not messages:
        logger.info("No messages were retrieved")
    return messages


def delete_sqs_message(queue_url: str, receipt_handle: str):
    queue_name = queue_url.split("/")[-1]
    logger.info(f"Deleting a message from {queue_name} SQS queue with {receipt_handle}")  # noqa: E501
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


def get_file_identity(file_path: str) -> tuple[str, str]:
    """
    Returns: (file_type, mime_type)\n
    Note: `file_type` is stripped of any dots.
    """
    logger.info(f"Getting file data for {file_path}")

    file_data_list: list = puremagic.magic_file(file_path)
    logger.info(f"File Data: {file_data_list}")

    if not file_data_list:
        logger.warning("Could not determine the file type")
        return "Unknown", "Unknown"

    # Get the first one, which has the highest confidence
    file_data = file_data_list[0]
    # File type: Remove the dot from the extension
    file_type = file_data[2].replace(".", "")
    mime_type = file_data[3]

    logger.info(f"File Type: {file_type}, MIME Type: {mime_type}")
    return file_type, mime_type


def quarantine_file(src_bucket: str, dest_bucket: str, key: str, receipt_handle: str):
    # Delete the `key` from the ingestion directory
    # TODO: Empty the Zip file ingestion dir?
    empty_dir(INGESTION_DIR)

    guarantine_reason = "Content-Type Validation Failure"
    logger.warning(f"Quarantining the file, {key}: {guarantine_reason}")  # noqa: E501

    copied = copy_object(src_bucket, dest_bucket, key, raise_error=False)
    obj_location = dest_bucket if copied else src_bucket
    delete_object(src_bucket, key, raise_error=False)

    try:
        logger.info("Deleting the message from SQS queue and sending notification")  # noqa: E501
        queue_url = get_param_value("/pipeline/AvScanQueueUrl")
        delete_sqs_message(queue_url, receipt_handle)
        send_file_quarantined_sns_msg(obj_location, key, guarantine_reason)  # noqa: E501
    except Exception as e:
        logger.warning(e)
