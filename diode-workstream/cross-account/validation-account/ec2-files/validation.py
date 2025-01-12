import logging
from pathlib import Path
import tempfile

import clamscan
from config import approved_filetypes
from config import ssm_params
from utils import add_tags
from utils import copy_object
from utils import create_tags_for_file_validation
from utils import delete_object
from utils import delete_sqs_message
from utils import download_file
from utils import extract_zipfile
from utils import get_file_ext
from utils import publish_sns_message
from utils import validate_filetype


logger = logging.getLogger()


def validate_file(bucket: str, key: str, receipt_handle: str):
    logger.info(f"Validating \"{key}\" object uploaded to \"{bucket}\" bucket")

    file_ext = get_file_ext(key)
    logger.info(f"File extension: {file_ext}")

    if file_ext not in approved_filetypes:
        logger.warning(f"File extension \"{file_ext}\" is NOT approved")
        tags = create_tags_for_file_validation("FileTypeNotApproved", file_ext, "")  # noqa: E501
        add_tags(bucket, key, tags)
        _send_to_invalid_files_bucket(bucket, key, receipt_handle)
        return

    with tempfile.TemporaryDirectory() as tmpdir:
        file_path = f"{tmpdir}/{key}"
        download_file(bucket, key, file_path)
        valid = _validate_file(bucket, key, file_path, receipt_handle)
        # TODO: Should we scan the file for virus first, before doing the content type check?
        if valid:
            clamscan.scan(bucket, key, file_path, receipt_handle)


def _validate_file(bucket: str, key: str, file_path: str, receipt_handle: str):
    try:
        file_ext = get_file_ext(file_path)
        valid, tags = validate_filetype(file_path, file_ext)
        add_tags(bucket, key, tags)

        if not valid:
            _send_to_invalid_files_bucket(bucket, key, receipt_handle)
            return False

        if not get_file_ext(file_path) == "zip":
            return True

        # TODO: What files are allowed to be in a zip file? For example, is an XML allowed?
        logger.info(f"The file is a ZIP file. Validating its contents")

        with tempfile.TemporaryDirectory() as tmpdir:
            extract_zipfile(file_path, tmpdir)
            file_paths = [str(item) for item in Path(tmpdir).rglob("*") if item.is_file()]  # noqa: E501
            for _file_path in file_paths:
                # Nested zip files are not allowed, for now
                _file_ext = get_file_ext(_file_path)
                if _file_ext == "zip":
                    logger.warning(f"Nested zip files are not allowed: {_file_path}")  # noqa: E501
                    error_tags = create_tags_for_file_validation("NestedZipFileNotAllowed", "zip", "")  # noqa: E501
                    add_tags(bucket, key, error_tags)
                    _send_to_invalid_files_bucket(bucket, key, receipt_handle)  # noqa: E501
                    return False

                valid, _ = validate_filetype(_file_path, _file_ext)
                if not valid:
                    # If one file fails validation, move the entire zip file to quarantine bucket
                    error_tags = create_tags_for_file_validation("ZipFileWithInvalidFile", "zip", "")  # noqa: E501
                    add_tags(bucket, key, error_tags)
                    _send_to_invalid_files_bucket(bucket, key, receipt_handle)  # noqa: E501
                    return False

        return True

    except Exception as e:
        # TODO: What should happen in case of errors? Is logging it out enough? That means the SQS message will be processed again
        logger.error(f"Could not validate the file: {e}")
        raise
        # _send_to_invalid_files_bucket(bucket, key, receipt_handle)  # noqa: E501


# TODO: Break up this function
def _send_to_invalid_files_bucket(src_bucket: str, key: str, receipt_handle: str):
    reject_reason = "Content-Type Validation Failure"
    logger.warning(f"Rejecting the file, {key}: {reject_reason}")

    invalid_files_bucket = ssm_params["/pipeline/InvalidFilesBucketName"]
    copied = copy_object(src_bucket, invalid_files_bucket, key, raise_error=False)  # noqa: E501
    obj_location = invalid_files_bucket if copied else src_bucket
    delete_object(src_bucket, key, raise_error=False)

    try:
        logger.info("Deleting the message from SQS queue and sending notification")  # noqa: E501
        queue_url = ssm_params["/pipeline/AvScanQueueUrl"]
        delete_sqs_message(queue_url, receipt_handle)
        topic_arn = ssm_params["/pipeline/InvalidFilesTopicArn"]
        _send_file_rejected_sns_msg(obj_location, key, topic_arn, reject_reason)  # noqa: E501
    except Exception as e:
        logger.warning(e)


def _send_file_rejected_sns_msg(bucket: str, key: str, topic_arn: str, reject_reason: str):
    logger.info(f"Sending an SNS message regarding the rejected file: {key}")  # noqa: E501
    message = (
        "A file has been rejected.\n\n"
        f"File: {key}\n"
        f"File Location: {bucket}/{key}\n"
        f"Reject Reason: {reject_reason}\n"
    )
    publish_sns_message(topic_arn, message, reject_reason)
    logger.info("Successfully sent the SNS message")
