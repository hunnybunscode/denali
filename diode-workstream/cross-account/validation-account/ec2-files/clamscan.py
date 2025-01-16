import logging
import random
import subprocess  # nosec B404

from config import ssm_params
from utils import add_tags
from utils import copy_object
from utils import create_tags_for_av_scan
from utils import delete_av_scan_message
from utils import delete_object
from utils import publish_sns_message

# TODO: Set this via SSM parameter store
TEST_MODE = True

logger = logging.getLogger()


def scan(bucket: str, key: str, file_path: str, receipt_handle: str):
    try:
        exit_status = _run_av_scan(key, file_path)

        # File does not exist
        if exit_status == 512:
            logger.warning(f"File {key} NOT FOUND. Unable to scan")
            delete_av_scan_message(receipt_handle)
            return

        # File is clean
        if exit_status == 0:
            file_status = "CLEAN"
            logger.info(f"{key} is {file_status}")

            new_tags = create_tags_for_av_scan(file_status, exit_status)
            add_tags(bucket, key, new_tags)

            data_transfer_bucket = ssm_params["/pipeline/DataTransferIngestBucketName"]
            logger.info(f"Copying {key} file to Data Transfer bucket: {data_transfer_bucket}")  # noqa: E501
            copy_object(bucket, data_transfer_bucket, key)

            lts_bucket = ssm_params["/pipeline/LongTermStorageBucketName"]
            logger.info(f"Copying {key} file to Long-term Storage bucket: {lts_bucket}")  # noqa: E501
            copy_object(bucket, lts_bucket, key)

            # Delete it from the ingestion bucket
            delete_object(bucket, key)

            delete_av_scan_message(receipt_handle)

            return

        # File is infected
        file_status = "INFECTED"
        logger.warning(f"{key} is {file_status}")

        new_tags = create_tags_for_av_scan(file_status, exit_status)
        add_tags(bucket, key, new_tags)

        quarantine_bucket = ssm_params["/pipeline/QuarantineBucketName"]
        logger.info(f"Copying {key} file to Quarantine bucket: {quarantine_bucket}")  # noqa: E501
        copy_object(bucket, quarantine_bucket, key)

        # Delete it from the ingestion bucket
        delete_object(bucket, key)

        delete_av_scan_message(receipt_handle)

        _send_file_quarantined_sns_msg(quarantine_bucket, key, file_status, exit_status)  # noqa: E501

    except Exception as e:
        logger.error(f"Exception ocurred scanning file: {e}")


def _run_av_scan(key: str, file_path: str):
    """
    Returns the exit status after running clamdscan on file_path
    """
    if TEST_MODE:
        logger.info(f"Testing mode enabled. Simulating clamdscan for {key}")  # noqa: E501
        exit_status = random.choice(([0] * 18) + [1, 512])  # nosec B311
    else:
        logger.info(f"Scanning {key}")
        exit_status = subprocess.run(["clamdscan", file_path]).returncode

    logger.info(f"ClamAV Scan Exit Code: {exit_status}")
    return exit_status


def _send_file_quarantined_sns_msg(bucket: str, key: str, file_status: str, exit_status: int):
    logger.info("Publishing SNS message for a quarantined file")
    try:
        topic_arn = ssm_params["/pipeline/QuarantineTopicArn"]
        subject = "AV Scanning Failure"
        message = (
            "A file has been quarantined based on the results of a ClamAV scan:\n\n"
            f"File Name: {key}\n"
            f"File Status: {file_status}\n"
            f"File Location: {bucket}/{key}\n"
            f"ClamAV Exit Code: {exit_status}"
        )
        publish_sns_message(topic_arn, message, subject)
        # logger.info(f"SNS message successfully published")
    except Exception as e:
        logger.error(f"Could not publish an SNS message: {e}")
