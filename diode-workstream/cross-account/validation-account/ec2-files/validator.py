import logging

import clamscan
from utils import delete_object
from utils import copy_object
from utils import create_tags_for_file_validation
from utils import send_file_quarantined_sns_msg
from utils import delete_sqs_message
from utils import empty_dir
from utils import get_param_value
from utils import add_tags
from utils import get_file_identity

logging.basicConfig(format="[%(levelname)s] %(message)s", filename="/var/log/messages", level=logging.INFO)  # noqa: E501
logger = logging.getLogger()

INGESTION_DIR = "/usr/bin/files"


def validator(bucket: str, key: str, receipt_handle: str, approved_filetypes: list, mime_mapping: dict[str, list]):
    logger.info(f"Validating file, {key}")

    new_tags = {}
    content_check = "FAILURE"

    try:
        ext = key.split(".")[-1]
        file_type, mime_type = get_file_identity(f"{INGESTION_DIR}/file_to_scan.{ext}")  # noqa: E501

        if file_type == "xml":
            logger.info(f"File processed through DFDL. File Extension: {ext}")
            if mime_type == "application/xml":
                logger.info("File validation successful")
                content_check = "SUCCESS"
                new_tags = create_tags_for_file_validation("None", mime_type)
            else:
                logger.warning(f"File validation failed for MIME type. MIME type is: {mime_type}")  # noqa: E501
                new_tags = create_tags_for_file_validation("File Validation Failed", mime_type)  # noqa: E501

        elif file_type == ext:
            logger.info(f"File Extension: {ext}")
            if file_type in approved_filetypes:
                logger.info(f"File Type: {file_type} included in approved list")  # noqa: E501
                if mime_type in mime_mapping.get(file_type, []):
                    logger.info("File validation successful")
                    content_check = "SUCCESS"
                    new_tags = create_tags_for_file_validation("None", mime_type)  # noqa: E501
                else:
                    logger.warning(f"File validation failed for MIME type. MIME type is: {mime_type}")  # noqa: E501
                    new_tags = create_tags_for_file_validation("File Validation Failed", mime_type)  # noqa: E501

            else:
                logger.warning(f"File Type ({file_type}) is not approved.")
                new_tags = create_tags_for_file_validation("File Type is not approved", mime_type)  # noqa: E501
        else:
            logger.warning(f"File Type ({file_type}) does not match file extension ({ext}).")  # noqa: E501
            new_tags = create_tags_for_file_validation("FileType does not match File Extension", mime_type)  # noqa: E501

        add_tags(bucket, key, new_tags)

        if content_check == "SUCCESS":
            logger.info(f"Content Check: {new_tags}")
            clamscan.scanner(bucket, key, receipt_handle)
        else:
            logger.warning(f"Content Check: {new_tags}")
            quarantine_bucket = get_param_value("/pipeline/QuarantineBucketName")  # noqa: E501
            quarantine_file(bucket, quarantine_bucket, key, receipt_handle)
    except Exception as e:
        logger.error(f"Exception ocurred validating file: {e}")
        quarantine_bucket = get_param_value("/pipeline/QuarantineBucketName")  # noqa: E501
        quarantine_file(bucket, quarantine_bucket, key, receipt_handle)


def quarantine_file(src_bucket: str, dest_bucket: str, key: str, receipt_handle: str):
    # Delete the `key` from local storage by emptying the ingestion directory
    empty_dir(INGESTION_DIR)

    logger.info(f"Content-Type validation failed for {key}. Quarantining the file")  # noqa: E501

    try:
        copy_object(src_bucket, dest_bucket, key)
        delete_object(src_bucket, key)
        obj_location = dest_bucket
    except Exception:
        obj_location = src_bucket

    try:
        av_scan_queue_url = get_param_value("/pipeline/AvScanQueueUrl")
        delete_sqs_message(av_scan_queue_url, receipt_handle)
        send_file_quarantined_sns_msg(obj_location, key, "Content-Type Validation Failure")  # noqa: E501
    except Exception:
        pass
