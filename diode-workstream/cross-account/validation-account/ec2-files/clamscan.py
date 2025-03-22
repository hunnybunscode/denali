import logging
import subprocess  # nosec B404

from config import resource_suffix
from config import ssm_params
from utils import add_tags
from utils import copy_object
from utils import create_tags_for_av_scan
from utils import delete_av_scan_message
from utils import delete_object
from utils import publish_sns_message

logger = logging.getLogger()


def scan(bucket: str, key: str, file_path: str, receipt_handle: str):
    # RETURN CODES from man page
    # 0 : No virus found.
    # 1 : Virus(es) found.
    # 2 : An error occurred.
    try:
        exit_status = _run_av_scan(key, file_path)

        if exit_status == 0:
            _process_clean_file(bucket, key, exit_status, receipt_handle)
        elif exit_status == 1:
            _process_infected_file(bucket, key, exit_status, receipt_handle)
        else:
            _process_error_file(bucket, key, exit_status, receipt_handle)

    except Exception as e:
        logger.error(f"Exception occurred scanning file: {e}")


def _run_av_scan(key: str, file_path: str):
    """
    Returns the exit status after running clamdscan on file_path
    """
    logger.info(f"Scanning {key}")

    scan_result = subprocess.run(
        ["clamdscan", "--fdpass", "-v", "--stdout", file_path],
        capture_output=True,
        text=True,
    )  # nosec B603, B607

    logger.info(f"ClamAV Scan Exit Code: {scan_result.returncode}")
    logger.info(f"ClamAV Scan Output: {scan_result.stdout}")
    if scan_result.stderr:
        logger.warning(f"ClamAV Scan Error: {scan_result.stderr}")
    return scan_result.returncode


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

    # Delete it from the ingestion bucket
    delete_object(bucket, key)

    delete_av_scan_message(receipt_handle)


def _process_error_file(bucket: str, key: str, exit_status: int, receipt_handle: str):
    file_status = "AV_SCAN_ERROR"
    logger.warning(f"{key} is {file_status}")

    tags = create_tags_for_av_scan(file_status, exit_status)
    add_tags(bucket, key, tags)

    invalid_files_bucket = ssm_params[
        f"/pipeline/InvalidFilesBucketName-{resource_suffix}"
    ]
    logger.info(
        f"Copying {key} file to Invalid Files bucket: {invalid_files_bucket}",
    )
    copy_object(bucket, invalid_files_bucket, key)

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
