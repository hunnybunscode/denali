import logging
import random
import subprocess  # nosec B404

from config import resource_suffix
from config import simulate_av_scan
from config import ssm_params
from utils import add_tags
from utils import copy_object
from utils import create_tags_for_av_scan
from utils import delete_av_scan_message
from utils import delete_object
from utils import publish_sns_message

logger = logging.getLogger()


def scan(bucket: str, key: str, file_path: str, receipt_handle: str):
    try:
        exit_status = _run_av_scan(key, file_path)

        # File does not exist
        if exit_status == 512:
            _process_non_existent_file(key, receipt_handle)
            return

        # File is clean
        if exit_status == 0:
            _process_clean_file(bucket, key, exit_status, receipt_handle)
            return

        # File is infected
        _process_infected_file(bucket, key, exit_status, receipt_handle)

    except Exception as e:
        logger.error(f"Exception occurred scanning file: {e}")


def _run_av_scan(key: str, file_path: str):
    """
    Returns the exit status after running clamdscan on file_path
    """
    if simulate_av_scan:
        logger.info(f"Simulating anti-virus scanning for {key}")
        exit_status = random.choice(([0] * 18) + [1, 512])  # nosec B311
    else:
        logger.info(f"Scanning {key}")
        # TODO: Get the full execution path for clamdscan
        exit_status = subprocess.run(
            ["clamdscan", file_path],
        ).returncode  # nosec B603, B607

    logger.info(f"ClamAV Scan Exit Code: {exit_status}")
    return exit_status


def _process_non_existent_file(key: str, receipt_handle: str):
    logger.warning(f"File {key} NOT FOUND. Unable to scan")
    delete_av_scan_message(receipt_handle)


def _process_clean_file(bucket: str, key: str, exit_status: int, receipt_handle: str):
    file_status = "CLEAN"
    logger.info(f"{key} is {file_status}")

    tags = create_tags_for_av_scan(file_status, exit_status)
    add_tags(bucket, key, tags)

    data_transfer_bucket = ssm_params[
        f"/pipeline/DataTransferIngestBucketName-{resource_suffix}"
    ]
    logger.info(
        f"Copying {key} file to Data Transfer bucket: {data_transfer_bucket}",
    )
    copy_object(bucket, data_transfer_bucket, key)

    lts_bucket = ssm_params[f"/pipeline/LongTermStorageBucketName-{resource_suffix}"]
    logger.info(
        f"Copying {key} file to Long-term Storage bucket: {lts_bucket}",
    )
    copy_object(bucket, lts_bucket, key)

    # Delete it from the ingestion bucket
    delete_object(bucket, key)

    delete_av_scan_message(receipt_handle)


def _process_infected_file(
    bucket: str,
    key: str,
    exit_status: int,
    receipt_handle: str,
):
    file_status = "INFECTED"
    logger.warning(f"{key} is {file_status}")

    tags = create_tags_for_av_scan(file_status, exit_status)
    add_tags(bucket, key, tags)

    quarantine_bucket = ssm_params[f"/pipeline/QuarantineBucketName-{resource_suffix}"]
    logger.info(
        f"Copying {key} file to Quarantine bucket: {quarantine_bucket}",
    )
    copy_object(bucket, quarantine_bucket, key)

    # Delete it from the ingestion bucket
    delete_object(bucket, key)

    delete_av_scan_message(receipt_handle)

    _send_file_quarantined_sns_msg(
        quarantine_bucket,
        key,
        file_status,
        exit_status,
    )


def _send_file_quarantined_sns_msg(
    bucket: str,
    key: str,
    file_status: str,
    exit_status: int,
):
    logger.info(
        f"Sending an SNS message regarding the quarantined file: {key}",
    )
    try:
        topic_arn = ssm_params[f"/pipeline/QuarantineTopicArn-{resource_suffix}"]
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
