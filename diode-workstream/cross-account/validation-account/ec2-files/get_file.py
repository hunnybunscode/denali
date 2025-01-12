import logging
import tempfile

import clamscan
from config import ssm_params
from utils import download_file
from utils import send_to_quarantine_bucket
from utils import get_file_extension
from validation import validate_file

logger = logging.getLogger()


def get_file(bucket: str, key: str, receipt_handle: str, approved_filetypes: list):
    logger.info(f"Getting {bucket}/{key} object")

    # TODO: Move this into the validate_file
    file_ext = get_file_extension(key)
    logger.info(f"Extension: {file_ext}")

    if file_ext not in approved_filetypes:
        handle_non_approved_filetypes(bucket, key, receipt_handle, file_ext)
        return

    with tempfile.TemporaryDirectory() as tmpdir:
        file_path = f"{tmpdir}/file_to_scan.{file_ext}"
        download_file(bucket, key, file_path)
        valid = validate_file(bucket, key, file_path, receipt_handle, approved_filetypes)  # noqa: E501
        # TODO: Should we scan the file for virus first, before doing the content type check?
        if valid:
            clamscan.scan(bucket, key, file_path, receipt_handle)


def handle_non_approved_filetypes(bucket: str, key: str, receipt_handle: str, file_ext: str):
    logger.warning(f"Extension {file_ext} is NOT one of the allowed file types")  # noqa: E501

    try:
        quarantine_bucket = ssm_params["/pipeline/QuarantineBucketName"]
        send_to_quarantine_bucket(bucket, quarantine_bucket, key, receipt_handle)  # noqa: E501
    except Exception as e:
        # TODO: Should we ignore errors?
        logger.error(f"Exception ocurred quarantining file: {e}")
