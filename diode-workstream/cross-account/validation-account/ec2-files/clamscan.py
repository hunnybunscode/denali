import logging
import random
import subprocess  # nosec B404

from utils import get_param_value
from utils import delete_sqs_message
from utils import publish_sns_message
from utils import copy_object
from utils import delete_object
from utils import add_tags

logger = logging.getLogger()


def scan(bucket, key, receipt_handle):

    try:
        # perform AV scan and capture result
        # exit_status = subprocess.run(["clamdscan", "/usr/bin/files"]).returncode  # noqa: E501

        logger.info("Simulating clamdscan")
        exit_status = random.choice(([0] * 18) + [1, 512])  # nosec B311

        logger.info(f"File {key} ClamAV Scan Exit Code: {exit_status}")

        if exit_status == 0:
            file_status = "CLEAN"
            logger.info(f"{key} is {file_status}")
            msg = f"Moving {key} file to Data Transfer bucket"
            tag_file(bucket, key, file_status, msg, exit_status, receipt_handle)  # noqa: E501
            return

        # If file does not exist
        if exit_status == 512:
            logger.warning(f"File {key} NOT FOUND. Unable to scan")
            queue_url = get_param_value("/pipeline/AvScanQueueUrl")
            delete_sqs_message(queue_url, receipt_handle)
            return

        # TODO: Handle exit statuses other than 0 and 512
        file_status = "INFECTED"
        # exit_status = 999
        logger.warning(f"{key} is {file_status}")
        quarantine_bucket = get_param_value("/pipeline/QuarantineBucketName")
        msg = f"Quarantined File: {key} stored in {bucket}"
        tag_file(bucket, key, file_status, msg, exit_status, receipt_handle)
        publish_quarantine_notification(quarantine_bucket, key, file_status, exit_status)  # noqa: E501

    except Exception as e:
        logger.error(f"Exception ocurred scanning file: {e}")


# Function to tag file depending on scan result
def tag_file(bucket, key, file_status, msg, exitstatus, receipt_handle):
    try:
        new_tags = {
            "AV_SCAN_STATUS": file_status,
            "CLAM_AV_EXIT_CODE": str(exitstatus)
        }
        add_tags(bucket, key, new_tags)

        if file_status == "CLEAN":
            dest_bucket = get_param_value("/pipeline/DataTransferIngestBucketName")  # noqa: E501
        else:
            dest_bucket = get_param_value("/pipeline/QuarantineBucketName")  # noqa: E501

        move_file(bucket, dest_bucket, key, msg, receipt_handle)
    except Exception as e:
        logger.error(f"Exception ocurred Tagging file: {e}")


def move_file(bucket, dest_bucket, key, msg, receipt_handle):
    logger.info(msg)
    try:
        copy_object(bucket, dest_bucket, key)
        queue_url = get_param_value("/pipeline/AvScanQueueUrl")
        delete_sqs_message(queue_url, receipt_handle)
        move_object_to_lts_bucket(bucket, key)
    except Exception as e:
        logger.error(f"Exception ocurred moving object to {dest_bucket}: {e}")  # noqa: E501


def move_object_to_lts_bucket(bucket, key):
    """
    Moves `key` from ingestion bucket to long term storage bucket
    """
    try:
        lts_bucket = get_param_value("/pipeline/LongTermStorageBucketName")  # noqa: E501
        logger.info(f"Moving file to {lts_bucket}")
        copy_object(bucket, lts_bucket, key)
        delete_object(bucket, key)
    except Exception as e:
        logger.error(f"Exception ocurred deleting object: {e}")


def publish_quarantine_notification(bucket: str, key: str, file_status: str, exit_status: int):
    logger.info("Publishing SNS message for a quarantined file")
    try:
        topic_arn = get_param_value("/pipeline/QuarantineTopicArn")
        subject = "A file uploaded to the quarantine S3 Bucket following a ClamAV scan"
        message = (
            "A file has been quarantined based on the results of a ClamAV scan:\n\n"
            f"File Name: {key}\n"
            f"File Status: {file_status}\n"
            f"File Location: {bucket}/{key}\n"
            f"ClamAV Exit Code: {exit_status}"
        )
        publish_sns_message(topic_arn, message, subject)
        logger.info(f"SNS message successfully published")
    except Exception as e:
        logger.error(f"Could not publish an SNS message: {e}")
