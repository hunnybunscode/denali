import logging
import os

import clamscan
from utils import create_tags_for_file_validation
from utils import add_tags
from utils import get_param_value
from utils import get_file_identity
from utils import quarantine_file

logger = logging.getLogger()

INGESTION_DIR = "/usr/bin/files"


def validate(bucket: str, key: str, receipt_handle: str, approved_filetypes: list, mime_mapping: dict[str, list]):
    logger.info("Validating Zip File Contents")

    new_tags = {}
    valid = True

    files = os.listdir(f"{INGESTION_DIR}/")

    for file in files:
        logger.info(f"Validating file, {file}")

        ext = file.split(".")[-1]
        file_type, mime_type = get_file_identity(f"{INGESTION_DIR}/{file}")  # noqa: E501

        try:
            if file_type.endswith(ext):
                logger.info(f"File Type: {file_type} matches File Extension {ext}")  # noqa: E501
                if file_type in approved_filetypes:
                    logger.info(f"File Type {file_type} is an approved Type")
                    if mime_type in mime_mapping.get(file_type, []):
                        logger.info(f"File: {key} validated successfully")
                        new_tags = create_tags_for_file_validation("None", mime_type)  # noqa: E501
                        logger.info(f"Content Check: {new_tags}")
                        valid = True
                    else:
                        new_tags = create_tags_for_file_validation("File Validation Failed", mime_type)  # noqa: E501
                        valid = False
                else:
                    logger.warning(f"File Type ({file_type}) is not approved.")
                    new_tags = create_tags_for_file_validation("File Type Not Supported", mime_type)  # noqa: E501
                    logger.warning(f"Content Check: {new_tags}")
                    valid = False

            else:
                logger.warning(f"File Type ({file_type}) does not match file extension ({ext}).")  # noqa: E501
                new_tags = create_tags_for_file_validation("FileType does not match File Extension", mime_type)  # noqa: E501
                valid = False
                logger.warning(f"Content Check: {new_tags}")
                break
        except Exception as e:
            logger.error(f"Exception ocurred validating file: {e}")

    if valid:
        logger.info("Validating Zip File")
        try:
            my_zipfile = "/usr/bin/zipfiles/zipfile.zip"
            ext = my_zipfile.split(".")[-1]
            file_type, mime_type = get_file_identity(my_zipfile)
            if file_type.endswith(ext):
                logger.info(f"File Type: {file_type} matches File Extension {ext}")  # noqa: E501
                if file_type in approved_filetypes:
                    logger.info(f"File Type {file_type} is an approved Type")  # noqa: E501
                    if mime_type in mime_mapping.get(file_type, []):
                        logger.info(f"File: {key} validated successfully")
                        new_tags = create_tags_for_file_validation("None", mime_type)  # noqa: E501
                        valid = True
                    else:
                        logger.warning(f"File: {key} NOT validated successfully")  # noqa: E501
                        new_tags = create_tags_for_file_validation("File Validation Failed", mime_type)  # noqa: E501
                        valid = False

                else:
                    logger.warning(f"File Type ({file_type}) is not approved.")  # noqa: E501
                    new_tags = create_tags_for_file_validation("File Type Not Supported", mime_type)  # noqa: E501
                    valid = False
            else:
                logger.warning(f"File Type ({file_type}) does not match file extension ({ext}).")  # noqa: E501
                new_tags = create_tags_for_file_validation("FileType does not match File Extension", mime_type)  # noqa: E501
                valid = False

        except Exception as e:
            logger.error(f"Exception ocurred validating zipfile: {e}")

    add_tags(bucket, key, new_tags)

    if valid:
        logger.info(f"Content Check: {new_tags}")
        clamscan.scan(bucket, key, receipt_handle)
    else:
        logger.warning(f"Content Check: {new_tags}")
        quarantine_bucket = get_param_value("/pipeline/QuarantineBucketName")
        quarantine_file(bucket, quarantine_bucket, key, receipt_handle)
