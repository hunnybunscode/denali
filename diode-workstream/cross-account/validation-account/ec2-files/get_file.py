import logging
import zipfile

import clamscan
import validator
import zipfile_validator
from utils import empty_dir
from utils import get_param_value
from utils import download_file
from utils import quarantine_file

logger = logging.getLogger()

INGESTION_DIR = "/usr/bin/files"
ZIP_INGESTION_DIR = "/usr/bin/zipfiles"


def get_file(bucket: str, key: str, receipt_handle: str, approved_filetypes: list, mime_mapping: dict):
    logger.info(f"Getting {key} object from {bucket} bucket")

    # TODO: Is is necessary to empty the ingestion directory at this point?
    empty_dir(INGESTION_DIR)

    file_ext = key.split(".")[-1]
    logger.info(f"Extension: {file_ext}")

    if file_ext not in approved_filetypes:
        handle_non_approved_filetypes(bucket, key, receipt_handle, file_ext)
        return

    # TODO: Test if puremagic can validate CSV files
    if file_ext == "csv":
        logger.info(f"File {key} is a .csv file.  Proceeding to scanner.")
        clamscan.scan(bucket, key, receipt_handle)
        return

    if file_ext == "zip":
        try:
            download_file(bucket, key, f"{ZIP_INGESTION_DIR}/zipfile.zip")
        except Exception as e:
            logger.error(f"Exception ocurred copying file to local storage: {e}")  # noqa: E501
            # Can't proceed if download failed
            return

        logger.info(f"Attempting to unzip {key} from {bucket}...")
        try:
            with zipfile.ZipFile(f"{ZIP_INGESTION_DIR}/zipfile.zip") as zip_file:
                # extact files from zip into tmp location
                zip_file.extractall(path=f"{INGESTION_DIR}/")

            logger.info(f"{key} successfully unzipped.")
        except zipfile.BadZipFile as bzf:
            logger.error(f"BadZipFile exception ocurred: {bzf}")

        zipfile_validator.validate(bucket, key, receipt_handle, approved_filetypes, mime_mapping)  # noqa: E501
        return

    # If file extension is not zip or csv
    logger.info(f"Downloading {bucket}/{key} to local storage")
    try:
        # Download file to local storage
        download_file(bucket, key, f"{INGESTION_DIR}/file_to_scan.{file_ext}")
        validator.validate(bucket, key, receipt_handle, approved_filetypes, mime_mapping)  # noqa: E501
    except Exception as e:
        logger.error(f"Exception ocurred copying file to local storage: {e}")  # noqa: E501


def handle_non_approved_filetypes(bucket: str, key: str, receipt_handle: str, file_ext: str):
    logger.warning(f"Extension {file_ext} is NOT one of the allowed file types")  # noqa: E501

    try:
        quarantine_bucket = get_param_value("/pipeline/QuarantineBucketName")
        quarantine_file(bucket, quarantine_bucket, key, receipt_handle)  # noqa: E501
    except Exception as e:
        logger.error(f"Exception ocurred quarantining file: {e}")
