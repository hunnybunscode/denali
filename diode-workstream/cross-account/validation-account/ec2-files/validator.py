import logging

import clamscan
from utils import create_tags_for_file_validation
from utils import get_param_value
from utils import add_tags
from utils import get_file_identity
from utils import quarantine_file

logger = logging.getLogger()

INGESTION_DIR = "/usr/bin/files"


def validate(bucket: str, key: str, receipt_handle: str, approved_filetypes: list, mime_mapping: dict[str, list]):
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
            clamscan.scan(bucket, key, receipt_handle)
        else:
            logger.warning(f"Content Check: {new_tags}")
            quarantine_bucket = get_param_value("/pipeline/QuarantineBucketName")  # noqa: E501
            quarantine_file(bucket, quarantine_bucket, key, receipt_handle)
    except Exception as e:
        logger.error(f"Exception ocurred validating file: {e}")
        quarantine_bucket = get_param_value("/pipeline/QuarantineBucketName")  # noqa: E501
        quarantine_file(bucket, quarantine_bucket, key, receipt_handle)
