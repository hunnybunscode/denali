import logging
import os
import subprocess  # nosec B404
import zipfile

import clamscan
import validator
import zipfile_validator

import boto3  # type: ignore
from botocore.config import Config  # type: ignore

logging.basicConfig(format="%(message)s", filename="/var/log/messages", level=logging.INFO)  # noqa: E501
logger = logging.getLogger()

# TODO: Should not have to hard-code the region
region = "us-gov-west-1"
config = Config(retries={"max_attempts": 5, "mode": "standard"})
S3_CLIENT = boto3.client("s3", config=config, region_name=region)
SSM_CLIENT = boto3.client("ssm", config=config, region_name=region)


def get_file(bucket: str, key: str, receipt_handle: str, approved_filetypes: list, mime_mapping: dict):
    logger.info("Getting File")
    file_path = "/usr/bin/files/"
    files = os.listdir(file_path)
    logger.info(f"Number of files: {len(files)}")
    if files:
        logger.info("emptying directory")
        for file in files:
            subprocess.run(["rm", "-r", f"{file_path}{file}"])

    file_ext = key.split(".")[-1]

    logger.info(f"Extension: {file_ext}")

    if file_ext not in approved_filetypes:
        handle_non_approved_filetypes(bucket, key, receipt_handle, file_ext)
        return

    if file_ext == "csv":
        logger.info(f"File {key} is a .csv file.  Proceeding to scanner.")
        clamscan.scanner(bucket, key, receipt_handle)
        return

    if file_ext == "zip":
        try:
            logger.info(f"Downloading {key} to local directory")
            S3_CLIENT.download_file(
                Bucket=bucket,
                Key=key,
                Filename="/usr/bin/zipfiles/zipfile.zip"
            )
            logger.info(f"Attempting to unzip {key} from {bucket}...")
        except Exception as e:
            logger.error(
                f"Exception ocurred copying file to local storage: {e}"
            )

        try:
            with zipfile.ZipFile("/usr/bin/zipfiles/zipfile.zip") as zip_file:
                # extact files from zip into tmp location
                zip_file.extractall(path="/usr/bin/files/")

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
        S3_CLIENT.download_file(
            Bucket=bucket,
            Key=key,
            Filename=f"/usr/bin/files/file_to_scan.{file_ext}"
        )
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
        validator.quarantine_file(bucket, key, quarantine_bucket, receipt_handle)  # noqa: E501
    except Exception as e:
        logger.error(f"Exception ocurred quarantining file: {e}")


def get_param_value(name: str, with_decryption=False) -> str:
    return SSM_CLIENT.get_parameter(
        Name=name,
        WithDecryption=with_decryption
    )["Parameter"]["Value"]
