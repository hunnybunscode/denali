import logging

import boto3  # type: ignore
import clamscan
import puremagic  # type: ignore
from botocore.exceptions import ClientError  # type: ignore
from utils import delete_object
from utils import copy_object
from utils import create_tags_for_file_validation
from utils import send_file_quarantined_sns_msg
from utils import delete_sqs_message
from utils import empty_dir
from utils import get_param_value
from utils import add_tags

s3_client = boto3.client("s3", region_name="us-gov-west-1")
logging.basicConfig(format="%(message)s", filename="/var/log/messages", level=logging.INFO)  # noqa: E501
logger = logging.getLogger()

INGESTION_DIR = "/usr/bin/files"


def validator(bucket: str, key: str, receipt_handle: str, approved_filetypes: list, mime_mapping: dict[str, list]):
    logger.info("Attempting to validate file")
    new_tags = {}
    content_check = "FAILURE"

    try:
        ext = key.split(".")[-1]
        logger.info(ext)
        file_data_list: list = puremagic.magic_file(f"{INGESTION_DIR}/file_to_scan.{ext}")  # noqa: E501
        logger.info(f"File Data: {file_data_list}")
        # The first one has the highest confidence
        file_data = file_data_list[0]
        # File type (or extension) without the dot
        file_type = file_data[2].replace(".", "")
        mime_type = file_data[3]
        logger.info("Attempting to validate filetype")

        if file_type.endswith("xml"):
            logger.info(f"File Processed Through DFDL. File Extension: {ext}")
            if mime_type == "application/xml":
                logger.info(f"File: {key} validated successfully")
                content_check = "SUCCESS"
                new_tags = create_tags_for_file_validation("None", mime_type)
            else:
                logger.info(f"MIME type validation Failed for {key}.  MIME Type is: {mime_type}")  # noqa: E501
                new_tags = create_tags_for_file_validation("File Validation Failed", mime_type)  # noqa: E501

        elif file_type.endswith(ext):
            logger.info(f"File Extension: {ext}")
            if file_type in approved_filetypes:
                logger.info(f"File Type: {file_type} included in approved list")  # noqa: E501
                if mime_type in mime_mapping.get(file_type, []):
                    logger.info(f"File: {key} validated successfully")
                    content_check = "SUCCESS"
                    new_tags = create_tags_for_file_validation("None", mime_type)  # noqa: E501
                else:
                    new_tags = create_tags_for_file_validation("File Validation Failed", mime_type)  # noqa: E501

            else:
                logger.info(f"File Type ({file_type}) is not approved.")
                new_tags = create_tags_for_file_validation("File Type is not approved", mime_type)  # noqa: E501
        else:
            logger.info(f"File Type ({file_type}) does not match file extension ({ext}).")  # noqa: E501
            new_tags = create_tags_for_file_validation("FileType does not match File Extension", mime_type)  # noqa: E501

        add_tags(bucket, key, new_tags)

        if content_check == "SUCCESS":
            logger.info(f"Content Check: {new_tags}")
            clamscan.scanner(bucket, key, receipt_handle)
        else:
            logger.error(f"Content Check: {new_tags}")
            ssm_client = boto3.client("ssm", region_name="us-gov-west-1")
            quarantine_bucket_parameter = ssm_client.get_parameter(
                Name="/pipeline/QuarantineBucketName"
            )
            quarantine_bucket = quarantine_bucket_parameter["Parameter"]["Value"]
            dest_bucket = quarantine_bucket
            quarantine_file(bucket, dest_bucket, key, receipt_handle)
    except Exception as e:
        logger.error(f"Exception ocurred validating file: {e}")
        ssm_client = boto3.client("ssm", region_name="us-gov-west-1")
        quarantine_bucket_parameter = ssm_client.get_parameter(
            Name="/pipeline/QuarantineBucketName"
        )
        quarantine_bucket = quarantine_bucket_parameter["Parameter"]["Value"]
        quarantine_file(bucket, quarantine_bucket, key, receipt_handle)


def quarantine_file(src_bucket: str, dest_bucket: str, key: str, receipt_handle: str):
    # Delete the `key` from local storage by emptying the ingestion directory
    empty_dir(INGESTION_DIR)

    logger.info(f"Content-Type validation failed for {key}. Quarantining the file")  # noqa: E501

    try:
        copy_object(src_bucket, dest_bucket, key)
        delete_object(src_bucket, key)
        obj_location = dest_bucket
    except ClientError:
        obj_location = src_bucket

    try:
        av_scan_queue_url = get_param_value("/pipeline/AvScanQueueUrl")
        delete_sqs_message(av_scan_queue_url, receipt_handle)
        send_file_quarantined_sns_msg(obj_location, key, "Content-Type Validation Failure")  # noqa: E501
    except ClientError:
        pass
