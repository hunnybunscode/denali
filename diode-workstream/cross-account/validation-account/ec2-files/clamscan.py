import json
import logging
import random
import subprocess

import boto3  # type: ignore


logging.basicConfig(format="%(message)s", filename="/var/log/messages", level=logging.INFO)  # noqa: E501
logger = logging.getLogger()

# TODO: Set the region via environment variable or config file (https://boto3.amazonaws.com/v1/documentation/api/latest/guide/configuration.html)
region = "us-gov-west-1"
SSM_CLIENT = boto3.client("ssm", region_name=region)
S3_CLIENT = boto3.client("s3", region_name=region)


def scanner(bucket, key, receipt_handle):

    try:
        # perform AV scan and capture result
        # exitstatus = subprocess.run(["clamdscan", "/usr/bin/files"]).returncode

        logger.info("Performing Fake clamdscan")
        exitstatus = random.choice(([0] * 18) + [1, 512])

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
            delete_sqs_message(receipt_handle)

        # TODO: Handle exit statuses other than 0 and 512
        # If scan does not return a "CLEAN" result
        else:
            file_status = "INFECTED"
            exit_status = 999
            logger.warning(f"{key} is infected")
            quarantine_bucket_response = SSM_CLIENT.get_parameter(
                Name="/pipeline/QuarantineBucketName")
            quarantine_bucket = quarantine_bucket_response["Parameter"]["Value"]
            msg = f"Quarantined File: {key} stored in {bucket}"
            tag_file(bucket, key, file_status, msg, exitstatus, receipt_handle)
            publish_sns(quarantine_bucket, key, file_status, exit_status)
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
        subprocess.run(["rm", "-r", "/usr/bin/files/*"])
        if file_status == "CLEAN":
            dest_bucket_response = SSM_CLIENT.get_parameter(
                Name="/pipeline/DataTransferIngestBucketName",)
            ingest_bucket = dest_bucket_response["Parameter"]["Value"]
            dest_bucket = ingest_bucket
        else:
            dest_bucket_response = SSM_CLIENT.get_parameter(
                Name="/pipeline/QuarantineBucketName",)
            quarantine_bucket = dest_bucket_response["Parameter"]["Value"]
            dest_bucket = quarantine_bucket
        move_file(bucket, key, dest_bucket, msg, receipt_handle)
    except Exception as e:
        logger.error(f"Exception ocurred Tagging file: {e}")


def quarantine_file(bucket, key, dest_bucket, msg, receipt_handle):
    logger.info(f"Quarantining {key}")
    try:
        S3_CLIENT.copy_object(
            Bucket=dest_bucket,
            CopySource=f"{bucket}/{key}",
            Key=key,
        )
        delete_sqs_message(receipt_handle)
        send_sqs(dest_bucket, key)

        S3_CLIENT.delete_object(
            Bucket=bucket,
            Key=key
        )
    except Exception as e:
        logger.error(f"Exception ocurring quarantining file ---{e}")
# Copies file to proper destination bucket


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
            delete_sqs_message(receipt_handle)
            # send_sqs(dest_bucket,key)
            delete_file(bucket, key)
        else:
            logger.error(f"FAILURE: Unable to Copy Object: {key} to {dest_bucket}.  StatusCode: {copy_status_code}")  # noqa: E501
    except Exception as e:
        logger.error(f"Exception ocurred copying object to {dest_bucket}: {e}")  # noqa: E501


def send_sqs(dest_bucket, key):
    sqs_client = boto3.client("sqs", region_name="us-gov-west-1")
    transfer_queue_response = SSM_CLIENT.get_parameter(
        Name="/pipeline/DataTransferQueueUrl")
    transfer_queue = transfer_queue_response["Parameter"]["Value"]
    try:
        logger.info("Sending SQS Message....")
        response = sqs_client.send_message(
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
    lts_bucket_response = SSM_CLIENT.get_parameter(
        Name="/pipeline/LongTermStorageBucketName")
    lts_bucket_name = lts_bucket_response["Parameter"]["Value"]
    lts_bucket = lts_bucket_name
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


def delete_sqs_message(receipt_handle):
    sqs_client = boto3.client("sqs", region_name="us-gov-west-1")
    av_scan_queue_response = SSM_CLIENT.get_parameter(
        Name="/pipeline/AvScanQueueUrl")
    av_scan_queue_url = av_scan_queue_response["Parameter"]["Value"]
    try:
        logger.info("Deleting SQS Message....")
        del_msg_response = sqs_client.delete_message(
            QueueUrl=av_scan_queue_url,
            ReceiptHandle=receipt_handle
        )
        del_msg_status_code = del_msg_response["ResponseMetadata"]["HTTPStatusCode"]
        if del_msg_status_code == 200:
            logger.info(f"SUCCESS:  SQS Message successfully deleted from Queue.  StatusCode: {del_msg_status_code}")  # noqa: E501
        else:
            logger.info(f"FAILURE: Unable to delete SQS Message from Queue.  StatusCode: {del_msg_status_code}")  # noqa: E501
    except Exception as e:
        logger.info(
            f"An Error Ocurred Deleting SQS Message queue.  Error: {e}")


def publish_sns(bucket, key, file_status, exitstatus):
    try:
        logger.info("Publishing SNS Message for Quarantined file")
        sns_client = boto3.client("sns", region_name="us-gov-west-1")
        quarantine_topic_response = SSM_CLIENT.get_parameter(
            Name="/pipeline/QuarantineTopicArn")
        quarantine_topic_arn = quarantine_topic_response["Parameter"]["Value"]
        message = f"A File has been quarantined due to the results of a ClamAV Scan.\nFile: {key}\nFile Status: {file_status}\nClamAV Exit Code: {exitstatus}\nFile Location: {bucket}/{key}"  # noqa: E501
        response = sns_client.publish(
            TopicArn=quarantine_topic_arn,
            Message=message,
            MessageStructure="text",
            Subject=f"A file  has been quarantined in the quarantin S3 Bucket following a ClamAV Scan"
        )
        sns_publish_status_code = response["ResponseMetadata"]["HTTPStatusCode"]
        if sns_publish_status_code == 200:
            logger.info(f"SUCCESS:  SNS Message Successfully published.  StatusCode: {sns_publish_status_code}")  # noqa: E501
        else:
            logger.info(f"FAILURE: Unable to Publish SNS Message.  StatusCode: {sns_publish_status_code}")  # noqa: E501
    except Exception as e:
        logger.error(f"An Exception ocurred publishing SNS: {e}")
