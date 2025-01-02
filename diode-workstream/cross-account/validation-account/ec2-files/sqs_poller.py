import json
import logging
import time

import boto3  # type: ignore
from botocore.config import Config  # type: ignore
import get_file

logging.basicConfig(format="%(message)s", filename="/var/log/messages", level=logging.INFO)  # noqa: E501
logger = logging.getLogger()

# TODO: Should not have to hard-code the region
region = "us-gov-west-1"
config = Config(retries={"max_attempts": 5, "mode": "standard"})
SSM_CLIENT = boto3.client("ssm", config=config, region_name=region)
SQS_CLIENT = boto3.client("sqs", config=config, region_name=region)


def main():
    # TODO: Should this be stored in parameter store?
    mime_mapping = get_mime_mapping("/usr/bin/validation-pipeline/mime_list.json")  # noqa: E501
    logger.info(mime_mapping)

    while True:
        queue_url = get_param_value("/pipeline/AvScanQueueUrl")
        approved_filetypes = get_param_value("/pipeline/ApprovedFileTypes").replace(".", "").replace(" ", "").split(",")  # noqa: E501
        dfdl_approved_filetypes = get_param_value("/pipeline/DfdlApprovedFileTypes").replace(".", "").replace(" ", "").split(",")  # noqa: E501
        approved_filetypes.extend(dfdl_approved_filetypes)

        try:
            response: dict = SQS_CLIENT.receive_message(
                QueueUrl=queue_url,
                MaxNumberOfMessages=1
            )

            messages = response.get("Messages")

            if not messages:
                logger.info("No messages were received")
                continue

            message = messages[0]
            receipt_handle = message["ReceiptHandle"]
            # load message for parsing to obtain bucket and key
            message_body = json.loads(message["Body"])
            bucket = message_body["detail"]["requestParameters"]["bucketName"]
            key = message_body["detail"]["requestParameters"]["key"]
            logger.info(f"Found file: {key}")
            get_file.get_file(bucket, key, receipt_handle, approved_filetypes, mime_mapping)  # noqa: E501

        except Exception as e:
            logger.exception(e)
            time.sleep(10)  # nosemgrep (Try again after 10 seconds)


def get_param_value(name: str, with_decryption=False) -> str:
    return SSM_CLIENT.get_parameter(
        Name=name,
        WithDecryption=with_decryption
    )["Parameter"]["Value"]


def get_mime_mapping(filepath: str):
    logger.info("Loading Mime Mapping")
    with open(filepath, "r", encoding="utf-8") as file:
        mime_list: dict = json.load(file)
    return mime_list


main()
