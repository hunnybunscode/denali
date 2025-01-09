import logging
import os

import clamscan
from utils import get_param_value
from utils import send_to_quarantine_bucket
from utils import get_file_extension
from utils import validate_filetype
from utils import add_tags
from utils import create_tags_for_file_validation


logger = logging.getLogger()

INGESTION_DIR = "/usr/bin/files"
ZIP_INGESTION_DIR = "/usr/bin/zipfiles"


# TODO: What bucket should be used when a file is determined to be invalid?


def validate_zipfile(bucket: str, key: str, receipt_handle: str, approved_filetypes: list, mime_mapping: dict[str, list]):
    try:
        zipfile_path = f"{ZIP_INGESTION_DIR}/zipfile.zip"
        valid, tags = validate_filetype(zipfile_path, approved_filetypes, mime_mapping)  # noqa: E501
        if not valid:
            add_tags(bucket, key, tags)
            quarantine_bucket = get_param_value("/pipeline/QuarantineBucketName")  # noqa: E501
            send_to_quarantine_bucket(bucket, quarantine_bucket, key, receipt_handle)  # noqa: E501
            return

        logger.info("Validating the zip file contents")

        # TODO: What files are allowed to be in a zip file? For example, is an XML allowed?

        # TODO: Use pathlib to list files
        files = os.listdir(f"{INGESTION_DIR}/")
        for file in files:
            # Do not allow nested zip files (at least for now)
            if get_file_extension(file) == "zip":
                logger.warning("Nested zip files are not allowed")
                error_tags = create_tags_for_file_validation("NestedZipFileNotAllowed", "zip", "application/zip")  # noqa: E501
                add_tags(bucket, key, error_tags)
                quarantine_bucket = get_param_value("/pipeline/QuarantineBucketName")  # noqa: E501
                send_to_quarantine_bucket(bucket, quarantine_bucket, key, receipt_handle)  # noqa: E501
                return

            file_path = f"{INGESTION_DIR}/{file}"
            valid, _ = validate_filetype(file_path, approved_filetypes, mime_mapping)  # noqa: E501
            if not valid:
                # If one file fails validation, move the entire zip file to quarantine bucket
                error_tags = create_tags_for_file_validation("ZipFileWithInvalidFile", "zip", "application/zip")  # noqa: E501
                add_tags(bucket, key, error_tags)
                quarantine_bucket = get_param_value("/pipeline/QuarantineBucketName")  # noqa: E501
                send_to_quarantine_bucket(bucket, quarantine_bucket, key, receipt_handle)  # noqa: E501
                return

        add_tags(bucket, key, tags)

        # Zip file has been validated, scan it for viruses
        clamscan.scan(bucket, key, receipt_handle)

    except Exception as e:
        # TODO: What should happen in case of errors? Is logging it out enough? That means the SQS message will be processed again
        logger.error(f"Could not validate the zipfile: {e}")
        # quarantine_bucket = get_param_value("/pipeline/QuarantineBucketName")  # noqa: E501
        # send_to_quarantine_bucket(bucket, quarantine_bucket, key, receipt_handle)  # noqa: E501


def validate_file(bucket: str, key: str, receipt_handle: str, approved_filetypes: list, mime_mapping: dict[str, list]):
    try:
        file_ext = get_file_extension(key)
        file_path = f"{INGESTION_DIR}/file_to_scan.{file_ext}"
        valid, tags = validate_filetype(file_path, approved_filetypes, mime_mapping)  # noqa: E501
        add_tags(bucket, key, tags)

        if not valid:
            quarantine_bucket = get_param_value("/pipeline/QuarantineBucketName")  # noqa: E501
            send_to_quarantine_bucket(bucket, quarantine_bucket, key, receipt_handle)  # noqa: E501
            return

        # File has been validated, scan it for viruses
        clamscan.scan(bucket, key, receipt_handle)

    except Exception as e:
        # TODO: What should happen in case of errors? Is logging it out enough? That means the SQS message will be processed again
        logger.error(f"Could not validate the file: {e}")
        # quarantine_bucket = get_param_value("/pipeline/QuarantineBucketName")  # noqa: E501
        # send_to_quarantine_bucket(bucket, quarantine_bucket, key, receipt_handle)  # noqa: E501
