import json
import logging
import random
import subprocess  # nosec B404

from utils import empty_dir
from utils import get_param_value
from utils import send_sqs_message
from utils import delete_sqs_message
from utils import publish_sns_message
from utils import copy_object
from utils import delete_object
from utils import add_tags

logger = logging.getLogger()

INGESTION_DIR = "/usr/bin/files"


def scan(bucket, key, receipt_handle):

    try:
        # perform AV scan and capture result
        # exit_status = subprocess.run(["clamdscan", "/usr/bin/files"]).returncode  # noqa: E501

        logger.info("Simulating clamdscan")
        exit_status = random.choice(([0] * 18) + [1, 512])  # nosec B311

        logger.info(f"File {key} ClamAV Scan Exit Code: {exit_status}")

        if exit_status == 0:
            file_status = "CLEAN"
            logger.info(f"{key} is clean")
            logger.info({"eventName": "ObjectTagged", "TagValue": [{"Key": "FILE_STATUS"}, {"Value": "CLEAN"}]})  # noqa: E501
            msg = f"Moving file: {key} to Data Transfer bucket..."
            tag_file(bucket, key, file_status, msg, exit_status, receipt_handle)  # noqa: E501
        # If file does not exist
        elif exit_status == 512:
            logger.info(f"File {key} not found. Unable to scan.")
            queue_url = get_param_value("/pipeline/AvScanQueueUrl")
            delete_sqs_message(queue_url, receipt_handle)

        # TODO: Handle exit statuses other than 0 and 512
        # If scan does not return a "CLEAN" result
        else:
            file_status = "INFECTED"
            # exit_status = 999
            logger.warning(f"{key} is infected")
            quarantine_bucket = get_param_value("/pipeline/QuarantineBucketName")  # noqa: E501
            msg = f"Quarantined File: {key} stored in {bucket}"
            tag_file(bucket, key, file_status, msg, exit_status, receipt_handle)  # noqa: E501
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
        # remove file from local storage
        empty_dir(INGESTION_DIR)
        if file_status == "CLEAN":
            dest_bucket = get_param_value("/pipeline/DataTransferIngestBucketName")  # noqa: E501
        else:
            dest_bucket = get_param_value("/pipeline/QuarantineBucketName")  # noqa: E501
        move_file(bucket, key, dest_bucket, msg, receipt_handle)
    except Exception as e:
        logger.error(f"Exception ocurred Tagging file: {e}")


def move_file(bucket, key, dest_bucket, msg, receipt_handle):
    logger.info(msg)
    try:
        copy_object(bucket, dest_bucket, key)
        queue_url = get_param_value("/pipeline/AvScanQueueUrl")
        delete_sqs_message(queue_url, receipt_handle)
        # send_sqs(dest_bucket,key)
        delete_file(bucket, key)
    except Exception as e:
        logger.error(f"Exception ocurred moving object to {dest_bucket}: {e}")  # noqa: E501


# TODO: This seems like a dead code
def send_sqs(dest_bucket, key):
    transfer_queue = get_param_value("/pipeline/DataTransferQueueUrl")  # noqa: E501
    message = json.dumps({"bucket": dest_bucket, "key": key})

    try:
        send_sqs_message(transfer_queue, message)
    except Exception as e:
        logger.error(f"Error Occurred sending SQS Message.  Exception: {e}")


# Function to delete file from ingest bucket
def delete_file(bucket, key):
    try:
        lts_bucket = get_param_value("/pipeline/LongTermStorageBucketName")  # noqa: E501
        logger.info(f"Moving file to {lts_bucket}")
        copy_object(bucket, lts_bucket, key)

        logger.info(f"Deleting file: {key} from Bucket: {bucket}")
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
