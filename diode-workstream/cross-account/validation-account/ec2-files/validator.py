import logging
import subprocess  # nosec B404

import boto3  # type: ignore
import clamscan
import puremagic  # type: ignore

s3_client = boto3.client("s3", region_name="us-gov-west-1")
logging.basicConfig(format="%(message)s", filename="/var/log/messages", level=logging.INFO)  # noqa: E501
logger = logging.getLogger()


def validator(bucket, key, receipt_handle, approved_filetypes, mime_mapping):
    logger.info("Attempting to validate file")
    # mime_mappings = {
    #   ".wav": "audio/x-wav",
    #  ".wav": "audio/wav",
    #  ".mp4": "video/mp4",
    #  ".flac": "audio/flac",
    #  ".txt": "text/plain",
    #  ".json": "application/json"
    #  }
    new_tags = {}
    content_check = "FAILURE"
    ingested_file = "/usr/bin/files/file_to_scan"
    try:
        ext = key.split(".")[-1]
        logger.info(ext)
        file_data_list: list = puremagic.magic_file(f"/usr/bin/files/file_to_scan.{ext}")  # noqa: E501
        logger.info(f"File Data: {file_data_list}")
        # The first one has the highest confidence
        file_data = file_data_list[0]
        # File type (or extension) without the dot
        file_type = file_data[2].replace(".", "")
        mime = file_data[3]
        logger.info("Attempting to validate filetype")

        if file_type.endswith("xml"):
            logger.info(f"File Processed Through DFDL. File Extension: {ext}")
            if mime == "application/xml":
                logger.info(f"File: {key} validated successfully")
                content_check = "SUCCESS"
                new_tags = {
                    "ERROR_STATUS": "None",
                    "MIME_TYPE": mime
                }
            else:
                logger.info(f"MIME type validation Failed for {key}.  MIME Type is: {mime}")  # noqa: E501
                new_tags = {
                    "ERROR_STATUS": "File Validation Failed",
                    "MIME_TYPE": mime
                }

        elif file_type.endswith(ext):
            logger.info(f"File Extension: {ext}")
            if file_type in approved_filetypes:
                logger.info(f"File Type: {file_type} included in approved list")  # noqa: E501
                for k, v in mime_mapping.items():
                    logger.info(f"Validating MIME Type: {mime}")
                    if k == f".{file_type}" and v == mime:
                        logger.info(f"File: {key} validated successfully")
                        content_check = "SUCCESS"
                        new_tags = {
                            "ERROR_STATUS": "None",
                            "MIME_TYPE": mime
                        }
                        break
                    else:
                        new_tags = {
                            "ERROR_STATUS": "File Validation Failed",
                            "MIME_TYPE": mime
                        }

            else:
                logger.info(f"File Type ({file_type}) is not approved.")
                new_tags = {
                    "ERROR_STATUS": "File Type is not approved",
                    "MIME_TYPE": mime
                }
        else:
            logger.info(f"File Type ({file_type}) does not match file extension ({ext}).")  # noqa: E501
            new_tags = {
                "ERROR_STATUS": "FileType does not match File Extension",
                "MIME_TYPE": mime
            }
        add_tags(bucket, key, new_tags)
        if content_check == "SUCCESS":
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
    except Exception as e:
        logger.error(f"Exception ocurred validating file: {e}")
        ssm_client = boto3.client("ssm", region_name="us-gov-west-1")
        quarantine_bucket_parameter = ssm_client.get_parameter(
            Name="/pipeline/QuarantineBucketName"
        )
        quarantine_bucket = quarantine_bucket_parameter["Parameter"]["Value"]
        quarantine_file(bucket, key, quarantine_bucket, receipt_handle)


def add_tags(bucket, key, new_tags):
    try:
        get_tags_response = s3_client.get_object_tagging(
            Bucket=bucket,
            Key=key
        )
        existing_tags = get_tags_response["TagSet"]
        combined_tags = existing_tags + \
            [{"Key": k, "Value": v} for k, v in new_tags.items()]

        logger.info(f"Tagging {key} with content-type data")
        response = s3_client.put_object_tagging(
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
            logger.error(f"FAILURE: Unable to tag {key}.  HTTPStatusCode: {tag_status_code}")  # noqa: E501
    except Exception as e:
        logger.error(f"Exception ocurred Tagging file with Content-Type Data: {e}")  # noqa: E501


def quarantine_file(bucket, key, dest_bucket, receipt_handle):
    logger.info(f"Content-Type validation failed for {key}.  Quarantining File.")  # noqa: E501
    logger.info(f"Deleting {key} from Local Storage")
    subprocess.run(["rm", "-r", "/usr/bin/files/*"])
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
            send_sns(dest_bucket, key)
            delete_file(bucket, key)

        else:
            logger.error(f"FAILURE: Unable to Copy Object: {key} to {dest_bucket}.  StatusCode: {copy_status_code}")  # noqa: E501
            logger.info(f"File: {key} remains located at {bucket}/{key}")
            send_sns(bucket, key)
    except Exception as e:
        logger.error(f"Exception ocurred copying object to {dest_bucket}: {e}")  # noqa: E501
        logger.info(f"File: {key} remains located at {bucket}/{key}")


def send_sns(bucket, key):
    ssm_client = boto3.client("ssm", region_name="us-gov-west-1")
    sns_topic_parameter = ssm_client.get_parameter(
        Name="/pipeline/QuarantineTopicArn"
    )
    quarantine_topic = sns_topic_parameter["Parameter"]["Value"]
    try:
        logger.info("Publishing SNS Message for Quarantined file")
        sns_client = boto3.client("sns", region_name="us-gov-west-1")
        message = f"A File has been quarantined due to Content-Type Validation Failure.\nFile: {key}\nFile Location: {bucket}/{key}"  # noqa: E501
        response = sns_client.publish(
            TopicArn=quarantine_topic,
            Message=message,
            MessageStructure="text",
            Subject=f"Content-Type Validation Failure"
        )
        sns_publish_status_code = response["ResponseMetadata"]["HTTPStatusCode"]
        if sns_publish_status_code == 200:
            logger.info(f"SUCCESS:  SNS Message Successfully published.  StatusCode: {sns_publish_status_code}")  # noqa: E501
        else:
            logger.error(f"FAILURE: Unable to Publish SNS Message.  StatusCode: {sns_publish_status_code}")  # noqa: E501
    except Exception as e:
        logger.error(f"An Exception ocurred publishing SNS: {e}")


def delete_file(bucket, key):
    try:
        logger.info(f"Deleting file: {key} from Bucket: {bucket}")
        response = s3_client.delete_object(
            Bucket=bucket,
            Key=key
        )
        delete_object_status_code = response["ResponseMetadata"]["HTTPStatusCode"]
        if delete_object_status_code == 204:
            logger.info(f"SUCCESS:  {key} successfully deleted from {bucket}.  StatusCode: {delete_object_status_code}")  # noqa: E501
        else:
            logger.error(f"FAILURE: Unable to delete {key} from {bucket}.  StatusCode: {delete_object_status_code}")  # noqa: E501
        logger.info(f"Delete Object Response: {response}")
    except Exception as e:
        logger.error(f"Exception ocurred deleting object: {e}")
