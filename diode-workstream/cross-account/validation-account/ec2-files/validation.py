import logging
import tempfile
from pathlib import Path
from urllib.parse import unquote_plus
from urllib.parse import urlencode

import clamscan
from config import instance_info
from config import resource_suffix
from config import ssm_params
from utils import create_tags_for_file_validation
from utils import delete_av_scan_message
from utils import delete_object
from utils import download_file
from utils import extract_zipfile
from utils import get_file_ext
from utils import get_origin_tags
from utils import get_ttl
from utils import get_user_tags_from_bucket
from utils import head_object
from utils import publish_sns_message
from utils import upload_file
from utils import validate_file_type

MAX_DEPTH = 0

logger = logging.getLogger()


def validate_file(s3_event: dict, receipt_handle: str):
    s3_event["s3"]["object"]["key"] = unquote_plus(s3_event["s3"]["object"]["key"])
    bucket = s3_event["s3"]["bucket"]["name"]
    key: str = s3_event["s3"]["object"]["key"]

    logger.info(f'Validating "{key}" object uploaded to "{bucket}" bucket')

    with tempfile.TemporaryDirectory() as tmpdir:
        # If key includes prefixes, split it and take the last element
        file_path = f'{tmpdir}/{key.split("/")[-1]}'
        downloaded = download_file(bucket, key, file_path)
        # If the object does not exist or is not a valid file path
        if not downloaded:
            delete_av_scan_message(receipt_handle)
            return

        valid, tags = _validate_file(s3_event, file_path, receipt_handle)
        if valid:
            clamscan.scan(s3_event, file_path, tags, receipt_handle)


def _validate_file(s3_event: dict, file_path: str, receipt_handle: str):
    try:
        file_ext = get_file_ext(file_path)
        valid, tags = validate_file_type(file_path, file_ext)

        if not valid:
            _process_invalid_file(s3_event, file_path, tags, receipt_handle)
            return False, {}

        if file_ext == "zip":
            _valid, _tags = _validate_zip_file(file_path)
            if not _valid:
                _process_invalid_file(s3_event, file_path, _tags, receipt_handle)
                return False, {}

        return True, tags

    except Exception:
        # TODO: What should happen in case of errors? Is logging it out enough?
        # That means the SQS message will be processed again
        logger.exception("Could not validate the file")
        return False, {}


def _validate_zip_file(file_path: str, depth=0):
    # TODO: What files are allowed to be in a zip file?
    # For example, should files destined for DFDL be allowed?

    logger.info(f"Validating the contents of the ZIP file: {file_path}")

    if depth > MAX_DEPTH:
        logger.warning(f"Nested Zip file; exceeded the max depth level of {MAX_DEPTH}")
        error_tags = create_tags_for_file_validation(
            "ZipMaxDepthExceeded",
            "zip",
        )
        return False, error_tags

    with tempfile.TemporaryDirectory() as tmpdir:
        if not extract_zipfile(file_path, tmpdir):
            error_tags = create_tags_for_file_validation(
                "InvalidZipFile",
                "zip",
            )
            return False, error_tags

        file_paths = [str(item) for item in Path(tmpdir).rglob("*") if item.is_file()]
        for _file_path in file_paths:
            _file_ext = get_file_ext(_file_path)
            valid, _ = validate_file_type(_file_path, _file_ext)

            if not valid:
                # Even if one file fails validation, reject the entire zip file
                error_tags = create_tags_for_file_validation(
                    "ZipFileWithInvalidFile",
                    "zip",
                )
                return False, error_tags

            if _file_ext == "zip":
                return _validate_zip_file(_file_path, depth + 1)

    return True, None


def _process_invalid_file(
    s3_event: dict,
    file_path: str,
    tags: dict[str, str],
    receipt_handle: str,
):
    """
    Uploads the invalid file to invalid files bucket, deletes it from ingestion bucket,
    deletes the SQS message, and sends an SNS notification
    """

    bucket = s3_event["s3"]["bucket"]["name"]
    key = s3_event["s3"]["object"]["key"]
    etag = s3_event["s3"]["object"]["eTag"]

    user_tags = get_user_tags_from_bucket(bucket, get_ttl())
    origin_tags = get_origin_tags(s3_event)
    url_encoded_tags = urlencode(user_tags | origin_tags | tags)

    invalid_files_bucket = ssm_params[
        f"/pipeline/InvalidFilesBucketName-{resource_suffix}"
    ]
    logger.info(f"Uploading {key} file to Invalid Files bucket")
    upload_file(invalid_files_bucket, key, file_path, url_encoded_tags)
    if head_object(bucket, key, etag):
        delete_object(bucket, key)  # Delete it from the ingestion bucket
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
            f"Instance ID: {instance_info['instance_id']}"
        )
        publish_sns_message(topic_arn, message, subject)
    except Exception as e:
        # Not critical; allow it to fail
        logger.warning(f"Could not publish an SNS message: {e}")
