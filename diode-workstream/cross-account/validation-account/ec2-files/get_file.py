import logging
import zipfile

import clamscan
import validator
import zipfile_validator
from utils import empty_dir
from utils import get_param_value
from utils import download_file

logging.basicConfig(format="[%(levelname)s] %(message)s", filename="/var/log/messages", level=logging.INFO)  # noqa: E501
logger = logging.getLogger()

INGESTION_DIR = "/usr/bin/files"


def get_file(bucket: str, key: str, receipt_handle: str, approved_filetypes: list, mime_mapping: dict):
    logger.info("Getting File")

    empty_dir(INGESTION_DIR)

    file_ext = key.split(".")[-1]
    logger.info(f"Extension: {file_ext}")

    if file_ext not in approved_filetypes:
        handle_non_approved_filetypes(bucket, key, receipt_handle, file_ext)
        return

    # TODO: Test if puremagic can validate CSV files
    if file_ext == "csv":
        logger.info(f"File {key} is a .csv file.  Proceeding to scanner.")
        clamscan.scanner(bucket, key, receipt_handle)
        return

    if file_ext == "zip":
        try:
            download_file(bucket, key, "/usr/bin/zipfiles/zipfile.zip")
        except Exception as e:
            logger.error(f"Exception ocurred copying file to local storage: {e}")  # noqa: E501
            # Can't proceed if download failed
            return

        logger.info(f"Attempting to unzip {key} from {bucket}...")
        try:
            with zipfile.ZipFile("/usr/bin/zipfiles/zipfile.zip") as zip_file:
                # extact files from zip into tmp location
                zip_file.extractall(path=f"{INGESTION_DIR}/")

            logger.info(f"{key} successfully unzipped.")
        except zipfile.BadZipFile as bzf:
            logger.error(f"BadZipFile exception ocurred: {bzf}")

        zipfile_validator.validator(
            bucket, key, receipt_handle, approved_filetypes, mime_mapping)
        return

    # If file extension is not zip or csv
    logger.info(
        f"Attempting to copy {key} to local storage from {bucket}..."
    )
    try:
        # Copy file to Local Storage
        download_file(bucket, key, f"{INGESTION_DIR}/file_to_scan.{file_ext}")
        validator.validator(bucket, key, receipt_handle, approved_filetypes, mime_mapping)  # noqa: E501
    except Exception as e:
        logger.error(
            f"Exception ocurred copying file to local storage: {e}")


def handle_non_approved_filetypes(bucket: str, key: str, receipt_handle: str, file_ext: str):
    logger.info(
        f"Extension {file_ext} is NOT one of the allowed filetypes"
    )
    try:
        quarantine_bucket = get_param_value("/pipeline/QuarantineBucketName")
        validator.quarantine_file(bucket, quarantine_bucket, key, receipt_handle)  # noqa: E501
    except Exception as e:
        logger.error(f"Exception ocurred quarantining file: {e}")
