import logging
import subprocess  # nosec B404
from urllib.parse import urlencode

from config import resource_suffix
from config import ssm_params
from utils import create_tags_for_av_scan
from utils import delete_av_scan_message
from utils import delete_object
from utils import get_origin_tags
from utils import get_scan_status
from utils import get_ttl
from utils import get_user_tags_from_bucket
from utils import head_object
from utils import publish_sns_message
from utils import upload_file

logger = logging.getLogger()


def scan(s3_event: dict, file_path: str, tags: dict, receipt_handle: str):
    # RETURN CODES from man page
    # 0 : No virus found.
    # 1 : Virus(es) found.
    # 2 : An error occurred.
    try:
        key = s3_event["s3"]["object"]["key"]
        exit_status = _run_av_scan(key, file_path)
        _process_file(s3_event, file_path, tags, exit_status, receipt_handle)
    except Exception:
        logger.exception("Exception occurred scanning file")


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


def _process_file(
    s3_event: dict,
    file_path: str,
    tags: dict,
    exit_status: int,
    receipt_handle: str,
):
    bucket = s3_event["s3"]["bucket"]["name"]
    key = s3_event["s3"]["object"]["key"]
    etag = s3_event["s3"]["object"]["eTag"]

    scan_status = get_scan_status(exit_status)
    logger.info(f"{key} is {scan_status}")

    user_tags = get_user_tags_from_bucket(bucket, get_ttl())
    origin_tags = get_origin_tags(s3_event)
    av_tags = create_tags_for_av_scan(exit_status)
    url_encoded_tags = urlencode(user_tags | origin_tags | av_tags | tags)

    # Destination buckets based on exit status
    data_transfer_bucket = ssm_params[
        f"/pipeline/DataTransferIngestBucketName-{resource_suffix}"
    ]
    quarantine_bucket = ssm_params[f"/pipeline/QuarantineBucketName-{resource_suffix}"]
    invalid_files_bucket = ssm_params[
        f"/pipeline/InvalidFilesBucketName-{resource_suffix}"
    ]

    if exit_status == 0:
        destination_bucket = user_tags.get("DestinationBucket")
        if destination_bucket:
            logger.info(f"Uploading {key} file to {destination_bucket}")
            upload_file(destination_bucket, key, file_path, url_encoded_tags)
        else:
            logger.info(f"Uploading {key} file to Data Transfer bucket")
            upload_file(data_transfer_bucket, key, file_path, url_encoded_tags)
    elif exit_status == 1:
        logger.info(f"Uploading {key} file to Quarantine bucket")
        upload_file(quarantine_bucket, key, file_path, url_encoded_tags)
    else:
        logger.info(f"Uploading {key} file to Invalid Files bucket")
        upload_file(invalid_files_bucket, key, file_path, url_encoded_tags)

    # Delete the object only if it is the same object
    if head_object(bucket, key, etag):
        delete_object(bucket, key)  # Delete it from the ingestion bucket

    delete_av_scan_message(receipt_handle)

    # Send notifications
    if exit_status == 0:
        pass
    elif exit_status == 1:
        _send_file_quarantined_msg(
            quarantine_bucket,
            key,
            scan_status,
            exit_status,
        )
    else:
        _send_file_rejected_msg(
            invalid_files_bucket,
            key,
            scan_status,
            exit_status,
        )


def _send_file_quarantined_msg(
    bucket: str,
    key: str,
    scan_status: str,
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
            f"File Location: {bucket}/{key}\n"
            f"Scan Status: {scan_status}\n"
            f"ClamAV Exit Code: {exit_status}"
        )
        publish_sns_message(topic_arn, message, subject)
    except Exception as e:
        # Not critical; allow it to fail
        logger.warning(f"Could not publish an SNS message: {e}")


def _send_file_rejected_msg(
    bucket: str,
    key: str,
    scan_status: str,
    exit_status: int,
):
    logger.info(
        f"Sending an SNS message regarding the rejected file: {key}",
    )
    try:
        topic_arn = ssm_params[f"/pipeline/InvalidFilesTopicArn-{resource_suffix}"]
        subject = "AV Scanning Error"
        message = (
            "A file has been rejected due to a ClamAV scan error:\n\n"
            f"File Name: {key}\n"
            f"File Location: {bucket}/{key}\n"
            f"Scan Status: {scan_status}\n"
            f"ClamAV Exit Code: {exit_status}"
        )
        publish_sns_message(topic_arn, message, subject)
    except Exception as e:
        # Not critical; allow it to fail
        logger.warning(f"Could not publish an SNS message: {e}")
