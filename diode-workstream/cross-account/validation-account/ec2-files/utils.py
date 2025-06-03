import logging
import os
import re
import subprocess  # nosec B404
import urllib.request
import zipfile
from datetime import datetime
from functools import lru_cache
from functools import reduce
from pathlib import Path
from time import sleep
from time import time

import boto3  # type: ignore
import puremagic  # type: ignore
from botocore.config import Config  # type: ignore
from botocore.exceptions import ClientError  # type: ignore
from config import approved_filetypes
from config import exempt_file_types
from config import mime_mapping
from config import resource_suffix
from config import ssm_params

logger = logging.getLogger()

region = os.environ["region"]
config = Config(retries={"max_attempts": 5, "mode": "standard"})
S3_CLIENT = boto3.client("s3", config=config, region_name=region)
SSM_CLIENT = boto3.client("ssm", config=config, region_name=region)
SNS_CLIENT = boto3.client("sns", config=config, region_name=region)
SQS_CLIENT = boto3.client("sqs", config=config, region_name=region)
AUTOSCALING_CLIENT = boto3.client("autoscaling", config=config, region_name=region)

KEYS_TO_COMBINE = {"DataOwner", "DataSteward", "KeyOwner", "GovPOC"}
UNKNOWN = "Unknown"
ERROR = "Error"


def head_object(bucket: str, key: str, etag: str, bucket_owner: str | None = None):
    try:
        params = dict(Bucket=bucket, Key=key, IfMatch=etag)
        if bucket_owner:
            params["ExpectedBucketOwner"] = bucket_owner
        S3_CLIENT.head_object(**params)
        return True
    except ClientError as e:
        error_code = e.response["Error"]["Code"]
        if error_code in ("404", "NoSuchKey"):
            logger.warning(f"Object not found: {bucket}/{key}")
            return False
        elif error_code == "412":
            logger.warning(f"ETag mismatch: {bucket}/{key} (ETag: {etag})")
            return False
        else:
            raise e


def delete_object(
    bucket: str,
    key: str,
    bucket_owner: str | None = None,
    raise_error=True,
):
    try:
        logger.info(f"Deleting {bucket}/{key}")
        params = dict(Bucket=bucket, Key=key)
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


@lru_cache(maxsize=100)
def get_user_tags_from_bucket(bucket: str, ttl: int, bucket_owner: str | None = None):
    logger.info(f"Getting user-defined tags from {bucket}")

    params = dict(Bucket=bucket)
    if bucket_owner:
        params["ExpectedBucketOwner"] = bucket_owner

    tagset: list[dict[str, str]] = S3_CLIENT.get_bucket_tagging(**params)["TagSet"]
    user_tagset = [tag for tag in tagset if not tag["Key"].startswith("aws:")]

    logger.info(f"Retrieved the user-defined tags: {user_tagset}")

    tag_indexes_to_remove = sorted(
        [
            index
            for index, tag in enumerate(user_tagset)
            if tag["Key"] in KEYS_TO_COMBINE
        ],
        reverse=True,
    )

    tags_to_combine = sorted(
        [user_tagset.pop(index) for index in tag_indexes_to_remove],
        key=lambda x: x["Key"],
    )

    user_tagset.append(
        reduce(
            lambda t1, t2: {
                "Key": f'{t1["Key"]} / {t2["Key"]}',
                "Value": f'{t1["Value"]} / {t2["Value"]}',
            },
            tags_to_combine,
        ),
    )

    user_tags = {tag["Key"]: tag["Value"] for tag in user_tagset}
    logger.info(f"Processed the user-defined tags: {user_tags}")
    return user_tags


def get_ttl(seconds=60):
    """Returns a new value every `seconds`"""
    return int(time() / seconds)


def get_origin_tags(s3_event: dict):
    principal_id = s3_event["userIdentity"]["principalId"]
    source_ip = s3_event["requestParameters"]["sourceIPAddress"]
    event_time = datetime.fromisoformat(s3_event["eventTime"]).strftime(
        "%Y-%m-%d %H%M UTC",
    )

    return {
        "PrincipalId / SourceIp": f"{principal_id} / {source_ip}",
        "DataItemCreateDateTime": event_time,
    }


def download_file(
    bucket: str,
    key: str,
    file_path: str,
    bucket_owner: str | None = None,
):
    """
    Returns True if download was successful; returns False if object was not found
    """
    logger.info(f"Downloading {bucket}/{key} to {file_path}")
    params: dict[str, str | dict] = dict(Bucket=bucket, Key=key, Filename=file_path)
    if bucket_owner:
        params["ExtraArgs"] = {"ExpectedBucketOwner": bucket_owner}

    try:
        S3_CLIENT.download_file(**params)
        logger.info("Successfully downloaded the object")
        return True
    except ClientError as e:
        if e.response["Error"]["Code"] in ("404", "NoSuchKey"):
            logger.error(f"Object not found: {bucket}/{key}")
            return False
        raise
    except NotADirectoryError:
        # This can be raised if a folder was created in the ingestion bucket
        logger.exception(f"Object not a valid file: {bucket}/{key}")
        return False


def upload_file(
    bucket: str,
    key: str,
    file_path: str,
    tagging: str,
    bucket_owner: str | None = None,
):
    logger.info(f"Uploading {file_path} to {bucket}/{key}")
    params: dict[str, str | dict] = dict(Bucket=bucket, Key=key, Filename=file_path)
    params["ExtraArgs"] = {"Tagging": tagging}
    if bucket_owner:
        params["ExtraArgs"].update({"ExpectedBucketOwner": bucket_owner})

    S3_CLIENT.upload_file(**params)
    logger.info("Successfully uploaded the object")


def publish_sns_message(topic_arn: str, message: str, subject: str | None = None):
    logger.info(
        f"Publishing a message to SNS topic: {topic_arn.split(':')[5]}",
    )
    params = dict(TopicArn=topic_arn, Message=message)
    if subject:
        params["Subject"] = subject

    SNS_CLIENT.publish(**params)
    logger.info("Successfully published the message")


def receive_sqs_message(queue_url: str, max_num_of_messages=1) -> list:
    queue_name = queue_url.split("/")[-1]
    logger.info(f"Checking for messages from {queue_name} SQS queue")
    response: dict = SQS_CLIENT.receive_message(
        QueueUrl=queue_url,
        MaxNumberOfMessages=max_num_of_messages,
        MessageSystemAttributeNames=["ApproximateReceiveCount"],
    )
    return response.get("Messages", [])


def delete_sqs_message(queue_url: str, receipt_handle: str):
    queue_name = queue_url.split("/")[-1]
    logger.info(f"Deleting message from {queue_name} SQS queue")
    SQS_CLIENT.delete_message(QueueUrl=queue_url, ReceiptHandle=receipt_handle)
    logger.info("Successfully deleted the message")


def change_message_visibility(queue_url: str, receipt_handle: str, timeout: int):
    # Unlike with a queue, when you change the visibility timeout for a specific
    # message, the timeout value is applied immediately but isn’t saved in memory
    # for that message. If you don’t delete a message after it is received, the
    # visibility timeout for the message reverts to the original timeout value
    # (not to the value you set using the ChangeMessageVisibility action) the
    # next time the message is received.

    logger.info(f"Updating the visibility timeout to {timeout}")

    # TODO: See if we need to swallow any errors here
    SQS_CLIENT.change_message_visibility(
        QueueUrl=queue_url,
        ReceiptHandle=receipt_handle,
        VisibilityTimeout=timeout,
    )
    logger.info("Successfully updated the visibility timeout")


def get_params_values(
    ssm_params: dict[str, str],
    with_decryption=False,
) -> dict[str, str]:
    """
    Retrieves the values specified by `ssm_params` dictionary keys,
    updates their values in place, and returns it
    """
    params = [*ssm_params]
    logger.info(f"Getting the values for parameters: {params}")
    response = SSM_CLIENT.get_parameters(Names=params, WithDecryption=with_decryption)
    invalid_params = response["InvalidParameters"]
    if invalid_params:
        logger.warning(f"Invalid parameters: {invalid_params}")
    for param in response["Parameters"]:
        ssm_params[param["Name"]] = param["Value"]
    logger.info("Successfully retrieved and updated the values for parameters")
    return ssm_params


def create_tags_for_file_validation(error_status: str, file_type: str, mime_type=""):
    """
    Returns: {"ValidationError / FileType / MimeType": f"{error_status} / {file_type} / {mime_type}"}  # noqa: E501
    """
    if mime_type:
        return {
            "ValidationError / FileType / MimeType": f"{error_status} / {file_type} / {mime_type}",  # noqa: E501
        }

    return {
        "ValidationError / FileType": f"{error_status} / {file_type}",
    }


@lru_cache(maxsize=3)
def create_tags_for_av_scan(exit_status: int):
    """
    Returns: {"AvScanStatus / ClamAvExitCode": scan_status / exit_status"}
    """
    scan_status = get_scan_status(exit_status)
    return {"AvScanStatus / ClamAvExitCode": f"{scan_status} / {str(exit_status)}"}


@lru_cache(maxsize=3)
def get_scan_status(exit_status: int):
    if exit_status == 0:
        return "CLEAN"
    elif exit_status == 1:
        return "INFECTED"
    else:
        return "AV_SCAN_ERROR"


def get_file_identity(file_path: str) -> tuple[str, str]:
    """
    Uses the puremagic library to determine file type and mime type.\n
    Returns (file_type, mime_type)\n

    If puremagic can't determine the file type and mime type,
    returns ("Unknown", "Unknown")\n

    In case of any errors, returns ("Error", "Error")\n
    Note: `file_type` is stripped of any dots.
    """
    logger.info(f"Getting file data for {file_path}")

    try:
        file_data_list: list = puremagic.magic_file(file_path)
        logger.info(f"File data: {file_data_list}")

        if not file_data_list:
            logger.warning("Could not determine the file type")
            return UNKNOWN, UNKNOWN

        # Get the first one, which has the highest confidence
        file_data = file_data_list[0]
        # File type: Remove the dot from the extension
        file_type = file_data[2].replace(".", "")
        mime_type = file_data[3]

        logger.info(f"File Type: {file_type}; MIME Type: {mime_type}")
        return file_type, mime_type
    except Exception:
        logger.exception("Could not get file data")
        return ERROR, ERROR


def validate_file_type(file_path: str, file_ext: str) -> tuple[bool, dict[str, str]]:
    """
    Validates a single file and returns the validation status and tags
    """
    logger.info(f"Validating file: {file_path}")

    file_type, mime_type = get_file_identity(file_path)

    # If puremagic can't determine the file type
    if file_type == UNKNOWN:
        dfdl_file_types = (
            ssm_params[f"/pipeline/DfdlApprovedFileTypes-{resource_suffix}"]
            .replace(".", "")
            .replace(" ", "")
            .split(",")
        )

        if file_ext in exempt_file_types + dfdl_file_types:
            logger.info(
                f"File {file_path} has the extension of {file_ext}. Performing AV scan only",  # noqa: E501
            )
            tags = create_tags_for_file_validation("None", file_ext)
            return True, tags

    if file_type != file_ext:
        logger.warning(
            f"File type ({file_type}) does NOT match file extension ({file_ext})",
        )
        tags = create_tags_for_file_validation(
            "FileTypeNotMatched",
            file_type,
            mime_type,
        )
        return False, tags

    logger.info(
        f"File type ({file_type}) matches file extension ({file_ext})",
    )
    if file_type not in approved_filetypes:
        logger.warning(f"File type ({file_type}) is NOT approved")
        tags = create_tags_for_file_validation(
            "FileTypeNotApproved",
            file_type,
            mime_type,
        )
        return False, tags

    logger.info(f"File type ({file_type}) is an approved type")
    if mime_type not in mime_mapping.get(file_type, []):
        logger.warning(f"Mime type ({mime_type}) is NOT approved")
        tags = create_tags_for_file_validation(
            "MimeTypeNotApproved",
            file_type,
            mime_type,
        )
        return False, tags

    logger.info(f"Mime type ({mime_type}) is an approved type")
    logger.info(f"Successfully validated file: {file_path}")
    tags = create_tags_for_file_validation("None", file_type, mime_type)
    return True, tags


def get_file_ext(file_path: str) -> str:
    """
    Extracts and returns the file extension (in lowercase) without the leading dot.\n
    In case of any errors, returns "Unknown".
    """
    try:
        logger.info(f"Getting file extension for {file_path}")
        file_ext = file_path.lower().split(".")[-1]
        logger.info(f"File extension: {file_ext}")
        return file_ext
    except Exception:
        logger.exception("Could not get file extension")
        return "Unknown"


def extract_zipfile(zipfile_path: str, extract_dir: str):
    """
    Extracts a zip file to a given directory.
    """
    logger.info(f"Extracting {zipfile_path} to {extract_dir}")

    try:
        with zipfile.ZipFile(zipfile_path) as zip_file:
            zip_file.extractall(extract_dir)
        logger.info("Successfully extracted the zip file")
        return True
    except zipfile.BadZipFile:
        logger.exception(f"{zipfile_path} is not a zip file")
        return False


def delete_av_scan_message(receipt_handle: str):
    """
    Deletes the message from AV Scan Queue to stop other consumers
    from processing the message
    """
    queue_url = ssm_params[f"/pipeline/AvScanQueueUrl-{resource_suffix}"]
    delete_sqs_message(queue_url, receipt_handle)


def mark_instance_as_unhealthy(instance_id: str):
    response = AUTOSCALING_CLIENT.set_instance_health(
        InstanceId=instance_id,
        HealthStatus="Unhealthy",
        ShouldRespectGracePeriod=False,
    )
    logger.info(response)


def await_clamd():
    """
    Waits for clamd to start, for up to 300 seconds
    """

    logger.info("Waiting for clamd to start")

    retry_interval = 5
    max_retries = 60

    for retry in range(max_retries):
        logger.info(f"Attempt {retry + 1} of {max_retries}")
        try:
            ping_result = subprocess.run(
                ["clamdscan", "--ping", "1"],
                capture_output=True,
                text=True,
            )  # nosec B603, B607

            if ping_result.returncode == 0:
                logger.info("clamd has started!")
                return True

            if ping_result.stderr:
                logger.warning(f"clamd ping error: {ping_result.stderr}")

        except Exception:
            logger.exception("Could not ping clamd")

        logger.info(f"Re-checking after {retry_interval} seconds")
        sleep(retry_interval)  # nosemgrep arbitrary-sleep

    logger.error("Max retries exhausted waiting for clamd to start")
    return False


def get_instance_id():
    """Get the EC2 instance ID using IMDSv2"""

    # Step 1: Generate a token
    token_req = urllib.request.Request(
        url="http://169.254.169.254/latest/api/token",
        method="PUT",
        headers={"X-aws-ec2-metadata-token-ttl-seconds": "21600"},
    )
    token = (
        urllib.request.urlopen(token_req, timeout=2)  # nosec B310
        .read()
        .decode("utf-8")
    )
    # Step 2: Use the token to get instance ID
    id_req = urllib.request.Request(
        url="http://169.254.169.254/latest/meta-data/instance-id",
        headers={"X-aws-ec2-metadata-token": token},
    )
    instance_id = (
        urllib.request.urlopen(id_req, timeout=2).read().decode("utf-8")  # nosec B310
    )

    if re.match(r"i-[a-z0-9]+", instance_id):
        logger.info(f"Instance ID: {instance_id}")
        return instance_id

    raise ValueError("Failed to get the instance ID")


#################################
#   UNUSED/OBSOLETE FUNCTIONS   #
#################################


def copy_object(
    src_bucket: str,
    dest_bucket: str,
    key: str,
    src_bucket_owner: str | None = None,
    dest_bucket_owner: str | None = None,
    raise_error=True,
):
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


def get_object_tagging(
    bucket: str,
    key: str,
    bucket_owner: str | None = None,
) -> dict[str, str]:
    logger.info(f"Getting existing tags for {bucket}/{key}")
    params = dict(Bucket=bucket, Key=key)
    if bucket_owner:
        params["ExpectedBucketOwner"] = bucket_owner

    tag_set = S3_CLIENT.get_object_tagging(**params)["TagSet"]
    logger.info(f"Successfully retrieved the existing tags: {tag_set}")
    return {tag["Key"]: tag["Value"] for tag in tag_set}


def put_object_tagging(
    bucket: str,
    key: str,
    tags: dict[str, str],
    bucket_owner: str | None = None,
):
    logger.info(f"Putting tags for {bucket}/{key}")
    tag_set = [{"Key": k, "Value": v} for k, v in tags.items()]
    params = dict(Bucket=bucket, Key=key, Tagging={"TagSet": tag_set})
    if bucket_owner:
        params["ExpectedBucketOwner"] = bucket_owner

    S3_CLIENT.put_object_tagging(**params)
    logger.info("Successfully put the tags")


def add_tags(
    bucket: str,
    key: str,
    tags_to_add: dict[str, str],
    bucket_owner: str | None = None,
):
    logger.info(f"Adding new tags to {bucket}/{key}: {tags_to_add}")
    existing_tags = get_object_tagging(bucket, key, bucket_owner)
    if not existing_tags:
        # Empty tags can be returned if an object with the same name gets
        # dropped into the ingestion bucket
        raise ValueError(f"No existing tags found for {bucket}/{key}")
    combined_tags = existing_tags | tags_to_add
    logger.info(f"Combined tags: {combined_tags}")
    put_object_tagging(bucket, key, combined_tags, bucket_owner)
    logger.info("Successfully added the new tags")


def get_param_value(name: str, with_decryption=False) -> str:
    logger.info(f"Getting the value for {name} parameter")
    value = SSM_CLIENT.get_parameter(Name=name, WithDecryption=with_decryption)[
        "Parameter"
    ]["Value"]
    logger.info("Successfully retrieved the value")
    return value


def send_sqs_message(queue_url: str, message: str, delay_seconds: int | None = None):
    queue_name = queue_url.split("/")[-1]
    logger.info(f"Sending a message to {queue_name} SQS queue")
    params: dict[str, str | int] = dict(QueueUrl=queue_url, MessageBody=message)
    if delay_seconds is not None:
        params["DelaySeconds"] = delay_seconds

    SQS_CLIENT.send_message(**params)
    logger.info("Successfully sent the message")


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
                empty_dir(str(path))
                path.rmdir()
        logger.info("Successfully emptied the directory")
    except Exception as e:
        logger.error(f"Could not empty the directory: {e}")
