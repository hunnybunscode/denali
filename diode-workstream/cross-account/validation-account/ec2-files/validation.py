import logging
import tempfile
from pathlib import Path

import clamscan
from config import approved_filetypes
from config import resource_suffix
from config import ssm_params
from utils import add_tags
from utils import copy_object
from utils import create_tags_for_file_validation
from utils import delete_av_scan_message
from utils import delete_object
from utils import download_file
from utils import extract_zipfile
from utils import get_file_ext
from utils import publish_sns_message
from utils import validate_filetype


logger = logging.getLogger()


def validate_file(bucket: str, key: str, receipt_handle: str):
    logger.info(f'Validating "{key}" object uploaded to "{bucket}" bucket')

    file_ext = get_file_ext(key)
    logger.info(f"File extension: {file_ext}")

    if file_ext not in approved_filetypes:
        logger.warning(f'File extension "{file_ext}" is NOT approved')
        tags = create_tags_for_file_validation(
            "FileTypeNotApproved",
            file_ext,
        )
        add_tags(bucket, key, tags)
        _process_invalid_file(bucket, key, receipt_handle)
        return

    with tempfile.TemporaryDirectory() as tmpdir:
        # If key includes prefixes, split it and take the last element
        file_path = f'{tmpdir}/{key.split("/")[-1]}'

        downloaded = download_file(bucket, key, file_path)
        if not downloaded:
            logger.warning(f"File {key} NOT found; unable to validate")
            delete_av_scan_message(receipt_handle)
            return

        valid = _validate_file(bucket, key, file_path, receipt_handle)
        if valid:
            clamscan.scan(bucket, key, file_path, receipt_handle)


def _validate_file(bucket: str, key: str, file_path: str, receipt_handle: str):
    try:
        file_ext = get_file_ext(file_path)
        valid, tags = validate_filetype(file_path, file_ext)
        add_tags(bucket, key, tags)

        if not valid:
            _process_invalid_file(bucket, key, receipt_handle)
            return False

        if not get_file_ext(file_path) == "zip":
            return True

        # TODO: What files are allowed to be in a zip file?
        # For example, should files destined for DFDL be allowed?
        logger.info("The file is a ZIP file. Validating its contents")

        with tempfile.TemporaryDirectory() as tmpdir:
            extract_zipfile(file_path, tmpdir)
            file_paths = [
                str(item) for item in Path(tmpdir).rglob("*") if item.is_file()
            ]
            for _file_path in file_paths:
                # Nested zip files are not allowed
                _file_ext = get_file_ext(_file_path)
                if _file_ext == "zip":
                    logger.warning(
                        f"Nested zip files are not allowed: {_file_path}",
                    )
                    error_tags = create_tags_for_file_validation(
                        "NestedZipFileNotAllowed",
                        "zip",
                    )
                    add_tags(bucket, key, error_tags)
                    _process_invalid_file(bucket, key, receipt_handle)
                    return False

                valid, _ = validate_filetype(_file_path, _file_ext)
                if not valid:
                    # If one file fails validation, reject the entire zip file
                    error_tags = create_tags_for_file_validation(
                        "ZipFileWithInvalidFile",
                        "zip",
                    )
                    add_tags(bucket, key, error_tags)
                    _process_invalid_file(bucket, key, receipt_handle)
                    return False

        return True

    except Exception as e:
        # TODO: What should happen in case of errors? Is logging it out enough?
        # That means the SQS message will be processed again
        logger.error(f"Could not validate the file: {e}")


def _process_invalid_file(bucket: str, key: str, receipt_handle: str):
    invalid_files_bucket = ssm_params[
        f"/pipeline/InvalidFilesBucketName-{resource_suffix}"
    ]
    logger.info(
        f"Copying {key} file to Invalid Files bucket: {invalid_files_bucket}",
    )
    copy_object(bucket, invalid_files_bucket, key)

    # Delete it from the ingestion bucket
    delete_object(bucket, key)

    delete_av_scan_message(receipt_handle)

    _send_file_rejected_sns_msg(invalid_files_bucket, key)


def _send_file_rejected_sns_msg(bucket: str, key: str):
    logger.info(
        f"Sending an SNS message regarding the rejected file: {key}",
    )
    try:
        topic_arn = ssm_params[f"/pipeline/InvalidFilesTopicArn-{resource_suffix}"]
        subject = "Content-Type Validation Failure"
        message = (
            "A file has been rejected.\n\n"
            f"File: {key}\n"
            f"File Location: {bucket}/{key}\n"
            f"Reject Reason: {subject}\n"
        )
        publish_sns_message(topic_arn, message, subject)
        # logger.info("Successfully sent the SNS message")
    except Exception as e:
        logger.error(f"Could not publish an SNS message: {e}")
