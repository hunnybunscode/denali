import logging
from pathlib import Path

import clamscan
from config import INGESTION_DIR
from utils import get_param_value
from utils import send_to_quarantine_bucket
from utils import get_file_extension
from utils import validate_filetype
from utils import add_tags
from utils import create_tags_for_file_validation


logger = logging.getLogger()


# TODO: What bucket should be used when a file is determined to be invalid?


def validate_zipfile(bucket: str, key: str, file_path: str, receipt_handle: str, approved_filetypes: list):
    try:
        valid, tags = validate_filetype(file_path, approved_filetypes)
        add_tags(bucket, key, tags)

        if not valid:
            quarantine_bucket = get_param_value("/pipeline/QuarantineBucketName")  # noqa: E501
            send_to_quarantine_bucket(bucket, quarantine_bucket, key, receipt_handle)  # noqa: E501
            return

        logger.info("Validating the zip file contents")

        # TODO: What files are allowed to be in a zip file? For example, is an XML allowed?
        # TODO: Unzip the file here, which would allow nested zip files, if supported

        file_paths = [str(item) for item in Path(INGESTION_DIR).rglob("*") if item.is_file()]  # noqa: E501
        for _file_path in file_paths:
            # Nested zip files are not allowed, for now
            if get_file_extension(_file_path) == "zip":
                logger.warning("Nested zip files are not allowed")
                error_tags = create_tags_for_file_validation("NestedZipFileNotAllowed", "zip", "application/zip")  # noqa: E501
                add_tags(bucket, key, error_tags)
                quarantine_bucket = get_param_value("/pipeline/QuarantineBucketName")  # noqa: E501
                send_to_quarantine_bucket(bucket, quarantine_bucket, key, receipt_handle)  # noqa: E501
                return

            valid, _ = validate_filetype(_file_path, approved_filetypes)
            if not valid:
                # If one file fails validation, move the entire zip file to quarantine bucket
                error_tags = create_tags_for_file_validation("ZipFileWithInvalidFile", "zip", "application/zip")  # noqa: E501
                add_tags(bucket, key, error_tags)
                quarantine_bucket = get_param_value("/pipeline/QuarantineBucketName")  # noqa: E501
                send_to_quarantine_bucket(bucket, quarantine_bucket, key, receipt_handle)  # noqa: E501
                return

        # Zip file has been validated, scan it for viruses
        clamscan.scan(bucket, key, receipt_handle)

    except Exception as e:
        # TODO: What should happen in case of errors? Is logging it out enough? That means the SQS message will be processed again
        logger.error(f"Could not validate the zipfile: {e}")
        # quarantine_bucket = get_param_value("/pipeline/QuarantineBucketName")  # noqa: E501
        # send_to_quarantine_bucket(bucket, quarantine_bucket, key, receipt_handle)  # noqa: E501


def validate_file(bucket: str, key: str, file_path: str, receipt_handle: str, approved_filetypes: list):
    try:
        valid, tags = validate_filetype(file_path, approved_filetypes)
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
