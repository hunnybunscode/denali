import json
import logging
import random
import subprocess  # nosec B404

import boto3  # type: ignore
from botocore.config import Config  # type: ignore
from botocore.exceptions import ClientError  # type: ignore
from utils import empty_dir
from utils import get_param_value
from utils import delete_sqs_message

logging.basicConfig(format="%(message)s", filename="/var/log/messages", level=logging.INFO)  # noqa: E501
logger = logging.getLogger()

# TODO: Set the region via environment variable or config file (https://boto3.amazonaws.com/v1/documentation/api/latest/guide/configuration.html)
region = "us-gov-west-1"
config = Config(retries={"max_attempts": 5, "mode": "standard"})
SSM_CLIENT = boto3.client("ssm", config=config, region_name=region)
S3_CLIENT = boto3.client("s3", config=config, region_name=region)
SQS_CLIENT = boto3.client("sqs", config=config, region_name=region)
SNS_CLIENT = boto3.client("sns", config=config, region_name=region)

INGESTION_DIR = "/usr/bin/files"


def scanner(bucket, key, receipt_handle):

    try:
        # perform AV scan and capture result
        # exitstatus = subprocess.run(["clamdscan", "/usr/bin/files"]).returncode

        logger.info("Performing Fake clamdscan")
        exitstatus = random.choice(([0] * 18) + [1, 512])  # nosec B311

        logger.info(f"File {key} ClamAV Scan Exit Code: {exitstatus}")
        if exitstatus == 0:
            file_status = "CLEAN"
            logger.info(f"{key} is clean")
            logger.info({"eventName": "ObjectTagged", "TagValue": [{"Key": "FILE_STATUS"}, {"Value": "CLEAN"}]})  # noqa: E501
            msg = f"Moving file: {key} to Data Transfer bucket..."
            tag_file(bucket, key, file_status, msg, exitstatus, receipt_handle)
        # If file does not exist
        elif exitstatus == 512:
            logger.info(f"File {key} not found. Unable to scan.")
            queue_url = get_param_value("/pipeline/AvScanQueueUrl")
            delete_sqs_message(queue_url, receipt_handle)

        # TODO: Handle exit statuses other than 0 and 512
        # If scan does not return a "CLEAN" result
        else:
            file_status = "INFECTED"
            exit_status = 999
            logger.warning(f"{key} is infected")
            quarantine_bucket = get_param_value("/pipeline/QuarantineBucketName")  # noqa: E501
            msg = f"Quarantined File: {key} stored in {bucket}"
            tag_file(bucket, key, file_status, msg, exitstatus, receipt_handle)
            publish_quarantine_notification(quarantine_bucket, key, file_status, exit_status)  # noqa: E501
    except Exception as e:
        logger.error(f"Exception ocurred scanning file: {e}")


# Function to tag file depending on scan result
def tag_file(bucket, key, file_status, msg, exitstatus, receipt_handle):
    try:
        get_tags_response = S3_CLIENT.get_object_tagging(
            Bucket=bucket,
            Key=key
        )
        existing_tags = get_tags_response["TagSet"]
        logger.info(f"Existing Object TagSet: {existing_tags}")
        new_tags = {
            "AV_SCAN_STATUS": file_status,
            "CLAM_AV_EXIT_CODE": str(exitstatus)
        }
        combined_tags = existing_tags + \
            [{"Key": k, "Value": v} for k, v in new_tags.items()]
        logger.info(f"Tagging {key} in Bucket {bucket}")
        response = S3_CLIENT.put_object_tagging(
            Bucket=bucket,
            Key=key,
            Tagging={
                "TagSet": combined_tags
            },
        )
        tag_status_code = response["ResponseMetadata"]["HTTPStatusCode"]
        if tag_status_code == 200:
            logger.info(f"SUCCESS: {key} Successfully Tagged with HTTPStatusCode {tag_status_code}")  # noqa: E501
        else:
            logger.info(f"FAILURE: Unable to tag {key}.  HTTPStatusCode: {tag_status_code}")  # noqa: E501
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
        response = S3_CLIENT.copy_object(
            Bucket=dest_bucket,
            CopySource=f"{bucket}/{key}",
            Key=key,
        )
        copy_status_code = response["ResponseMetadata"]["HTTPStatusCode"]
        logger.info(f"Copy Object Response {response}")
        if copy_status_code == 200:
            logger.info(f"SUCCESS: {key} successfully transferred to {dest_bucket} with HTTPStatusCode: {copy_status_code}")  # noqa: E501
            queue_url = get_param_value("/pipeline/AvScanQueueUrl")
            delete_sqs_message(queue_url, receipt_handle)
            # send_sqs(dest_bucket,key)
            delete_file(bucket, key)
        else:
            logger.error(f"FAILURE: Unable to Copy Object: {key} to {dest_bucket}.  StatusCode: {copy_status_code}")  # noqa: E501
    except Exception as e:
        logger.error(f"Exception ocurred copying object to {dest_bucket}: {e}")  # noqa: E501


def send_sqs(dest_bucket, key):
    transfer_queue = get_param_value("/pipeline/DataTransferQueueUrl")  # noqa: E501
    try:
        logger.info("Sending SQS Message....")
        response = SQS_CLIENT.send_message(
            QueueUrl=transfer_queue,
            MessageBody=json.dumps({
                "bucket": dest_bucket,
                "key": key
            })
        )
        send_sqs_status_code = response["ResponseMetadata"]["HTTPStatusCode"]
        if send_sqs_status_code == 200:
            logger.info(f"SUCCESS: SQS Message Successfully sent to Diode Transfer Account.  HTTPStatusCode: {send_sqs_status_code}")  # noqa: E501
        else:
            logger.info(f"FAILURE: SQS Message Unable to send to Diode Transfer Account.  HTTPStatusCode: {send_sqs_status_code}")  # noqa: E501
        logger.info(f"SQS Response: {response}")
    except Exception as e:
        logger.info(f"Error Occurred sending SQS Message.  Exception: {e}")


# Function to delete file from ingest bucket
def delete_file(bucket, key):
    lts_bucket = get_param_value("/pipeline/LongTermStorageBucketName")  # noqa: E501

    try:
        logger.info(f"Moving file to {lts_bucket}")
        response = S3_CLIENT.copy_object(
            Bucket=lts_bucket,
            CopySource=f"{bucket}/{key}",
            Key=key
        )
        copy_object_status_code = response["ResponseMetadata"]["HTTPStatusCode"]
        if copy_object_status_code == 200:
            logger.info(
                f"SUCCESS: {key} successfully transferred to storage bucket: {lts_bucket}")  # noqa: E501
        else:
            logger.info(f"FAILURE: {key} transfer to {lts_bucket} received StatusCode: {copy_object_status_code}")  # noqa: E501
        logger.info(f"Deleting file: {key} from Bucket: {bucket}")
        response = S3_CLIENT.delete_object(
            Bucket=bucket,
            Key=key
        )
        delete_object_status_code = response["ResponseMetadata"]["HTTPStatusCode"]
        if delete_object_status_code == 204:
            logger.info(f"SUCCESS:  {key} successfully deleted from {bucket}.  StatusCode: {delete_object_status_code}")  # noqa: E501
        else:
            logger.info(f"FAILURE: Unable to delete {key} from {bucket}.  StatusCode: {delete_object_status_code}")  # noqa: E501
        logger.info(f"Delete Object Response: {response}")
    except Exception as e:
        logger.error(f"Exception ocurred deleting object: {e}")


def publish_quarantine_notification(bucket: str, key: str, file_status: str, exit_status: int):
    logger.info("Publishing SNS message for a quarantined file")
    try:
        quarantine_topic_arn = get_param_value("/pipeline/QuarantineTopicArn")
        subject = "A file uploaded to the quarantine S3 Bucket following a ClamAV scan"
        message = ("A file has been quarantined based on the results of a ClamAV scan:\n\n"
                   f"File Name: {key}\n"
                   f"File Status: {file_status}\n"
                   f"File Location: {bucket}/{key}\n"
                   f"ClamAV Exit Code: {exit_status}")
        publish_sns_message(quarantine_topic_arn, subject, message)
        logger.info(f"SNS message successfully published")
    except ClientError as e:
        logger.error(f"Could not publish an SNS message: {e}")


def get_param_value(name: str, with_decryption=False) -> str:
    return SSM_CLIENT.get_parameter(
        Name=name,
        WithDecryption=with_decryption
    )["Parameter"]["Value"]


def publish_sns_message(topic_arn: str, subject: str, message: str):
    SNS_CLIENT.publish(
        TopicArn=topic_arn,
        Subject=subject,
        Message=message,
    )
