import logging

from utils import empty_dir
from utils import get_param_value
from utils import download_file
from utils import send_to_quarantine_bucket
from utils import get_file_extension
from utils import extract_zipfile
from validation import validate_file
from validation import validate_zipfile

logger = logging.getLogger()

INGESTION_DIR = "/usr/bin/files"
ZIP_INGESTION_DIR = "/usr/bin/zipfiles"


def get_file(bucket: str, key: str, receipt_handle: str, approved_filetypes: list):
    empty_dir(INGESTION_DIR)
    empty_dir(ZIP_INGESTION_DIR)

    logger.info(f"Getting {bucket}/{key} object")

    file_ext = get_file_extension(key)
    logger.info(f"Extension: {file_ext}")

    if file_ext not in approved_filetypes:
        handle_non_approved_filetypes(bucket, key, receipt_handle, file_ext)
        return

    if file_ext == "zip":
        zipfile_path = f"{ZIP_INGESTION_DIR}/zipfile.zip"
        download_file(bucket, key, zipfile_path)
        extract_zipfile(zipfile_path, INGESTION_DIR)
        validate_zipfile(bucket, key, receipt_handle, approved_filetypes)
        return

    # At this point, the file is of an approved type and is not a zip file
    file_path = f"{INGESTION_DIR}/file_to_scan.{file_ext}"
    download_file(bucket, key, file_path)
    validate_file(bucket, key, receipt_handle, approved_filetypes)


def handle_non_approved_filetypes(bucket: str, key: str, receipt_handle: str, file_ext: str):
    logger.warning(f"Extension {file_ext} is NOT one of the allowed file types")  # noqa: E501

    try:
        quarantine_bucket = get_param_value("/pipeline/QuarantineBucketName")
        send_to_quarantine_bucket(bucket, quarantine_bucket, key, receipt_handle)  # noqa: E501
    except Exception as e:
        # TODO: Should we ignore errors?
        logger.error(f"Exception ocurred quarantining file: {e}")
