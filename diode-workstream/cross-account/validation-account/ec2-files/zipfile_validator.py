import logging
import os

import boto3  # type: ignore
import clamscan
import puremagic  # type: ignore
from utils import empty_dir
from utils import create_tags_for_file_validation
from utils import delete_object
from utils import add_tags
from utils import send_file_quarantined_sns_msg

s3_client = boto3.client("s3", region_name="us-gov-west-1")
logging.basicConfig(format="%(message)s", filename="/var/log/messages", level=logging.INFO)  # noqa: E501
logger = logging.getLogger()

INGESTION_DIR = "/usr/bin/files"


def validator(bucket: str, key: str, receipt_handle: str, approved_filetypes: list, mime_mapping: dict[str, list]):
    logger.info("Validating Zip File Contents")
    ext = ""
    file_type = ""
    mime_type = ""
    new_tags = {}
    content_check = "FAILURE"
    files = os.listdir(f"{INGESTION_DIR}/")
    valid = True
    for f in files:
        ext = f.split(".")[-1]
        file_data_list: list = puremagic.magic_file(f"{INGESTION_DIR}/{f}")
        logger.info(f"File Data: {file_data_list}")
        # The first one has the highest confidence
        file_data = file_data_list[0]
        # File type (or extension) without the dot
        file_type = file_data[2].replace(".", "")
        mime_type = file_data[3]
        logger.info(f"Attempting to validate {f}")
        try:
            if file_type.endswith(ext):
                logger.info(f"File Type: {file_type} matches File Extension {ext}")  # noqa: E501
                if file_type in approved_filetypes:
                    logger.info(f"File Type {file_type} is an approved Type")
                    if mime_type in mime_mapping.get(file_type, []):
                        logger.info(f"File: {key} validated successfully")
                        new_tags = create_tags_for_file_validation("None", mime_type)  # noqa: E501
                        logger.info(f"Content Check: {new_tags}")
                        valid = True
                    else:
                        new_tags = create_tags_for_file_validation("File Validation Failed", mime_type)  # noqa: E501
                        valid = False
                else:
                    logger.info(f"File Type ({file_type}) is not approved.")
                    new_tags = create_tags_for_file_validation("File Type Not Supported", mime_type)  # noqa: E501
                    logger.error(f"Content Check: {new_tags}")
                    valid = False

            else:
                logger.info(f"File Type ({file_type}) does not match file extension ({ext}).")  # noqa: E501
                new_tags = create_tags_for_file_validation("FileType does not match File Extension", mime_type)  # noqa: E501
                valid = False
                logger.error(f"Content Check: {new_tags}")
                break
        except Exception as e:
            logger.error(f"Exception ocurred validating file: {e}")

    if valid:
        logger.info("Validating Zip File")
        try:
            my_zipfile = "/usr/bin/zipfiles/zipfile.zip"
            zip_file_data = puremagic.magic_file(my_zipfile)
            ext = my_zipfile.split(".")[-1]
            zip_file_type = zip_file_data[0][2].replace(".", "")
            zip_mime = zip_file_data[0][3]
            if zip_file_type.endswith(ext):
                logger.info(f"File Type: {zip_file_type} matches File Extension {ext}")  # noqa: E501
                if zip_file_type in approved_filetypes:
                    logger.info(f"File Type {zip_file_type} is an approved Type")  # noqa: E501
                    if zip_mime in mime_mapping.get(zip_file_type, []):
                        logger.info(f"File: {key} validated successfully")
                        new_tags = create_tags_for_file_validation("None", zip_mime)  # noqa: E501
                        valid = True
                    else:
                        new_tags = create_tags_for_file_validation("File Validation Failed", zip_mime)  # noqa: E501
                        valid = False

                else:
                    logger.info(f"File Type ({zip_file_type}) is not approved.")  # noqa: E501
                    new_tags = create_tags_for_file_validation("File Type Not Supported", zip_mime)  # noqa: E501
                    valid = False
            else:
                logger.info(f"File Type ({zip_file_type}) does not match file extension ({ext}).")  # noqa: E501
                new_tags = create_tags_for_file_validation("FileType does not match File Extension", zip_mime)  # noqa: E501
                valid = False

        except Exception as e:
            logger.error(f"Exception ocurred validating zipfile: {e}")

    add_tags(bucket, key, new_tags)

    if valid:
        logger.info(f"Content Check: {new_tags}")
        clamscan.scanner(bucket, key, receipt_handle)
    else:
        logger.error(f"Content Check: {new_tags}")
        ssm_client = boto3.client("ssm", region_name="us-gov-west-1")
        quarantine_bucket_parameter = ssm_client.get_parameter(
            Name="/pipeline/QuarantineBucketName"
        )
        quarantine_bucket = quarantine_bucket_parameter["Parameter"]["Value"]
        dest_bucket = quarantine_bucket
        quarantine_file(bucket, key, dest_bucket, receipt_handle)


def quarantine_file(bucket, key, dest_bucket, receipt_handle):
    logger.info(f"Content-Type validation failed for {key}.  Quarantining File.")  # noqa: E501
    logger.info(f"Deleting {key} from Local Storage")
    empty_dir(INGESTION_DIR)

    try:
        response = s3_client.copy_object(
            Bucket=dest_bucket,
            CopySource=f"{bucket}/{key}",
            Key=key
        )
        copy_status_code = response["ResponseMetadata"]["HTTPStatusCode"]
        logger.info(f"Copy Object Response {response}")
        if copy_status_code == 200:
            logger.info(f"SUCCESS: {key} successfully transferred to {dest_bucket} with HTTPStatusCode: {copy_status_code}")  # noqa: E501
            clamscan.delete_sqs_message(receipt_handle)
            send_file_quarantined_sns_msg(dest_bucket, key, "Content-Type Validation Failure")  # noqa: E501
            delete_object(bucket, key)

        else:
            logger.error(f"FAILURE: Unable to Copy Object: {key} to {dest_bucket}.  StatusCode: {copy_status_code}")  # noqa: E501
            logger.info(f"File: {key} remains located at {bucket}/{key}")
            send_file_quarantined_sns_msg(bucket, key, "Content-Type Validation Failure")  # noqa: E501
    except Exception as e:
        logger.error(f"Exception ocurred copying object to {dest_bucket}: {e}")  # noqa: E501
        logger.info(f"File: {key} remains located at {bucket}/{key}")
