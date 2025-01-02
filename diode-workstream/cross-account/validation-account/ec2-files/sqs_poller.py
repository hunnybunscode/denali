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
    queue_url = get_param_value("/pipeline/AvScanQueueUrl")
    approved_filetypes = get_param_value("/pipeline/ApprovedFileTypes")
    dfdl_approved_filetypes = get_param_value("/pipeline/DfdlApprovedFileTypes")  # noqa: E501

    # TODO: File extensions should not have any dots--why call `replace` method on them?
    all_approved_filetypes = f"{approved_filetypes.replace('.', '')}, {dfdl_approved_filetypes.replace('.', '')}"  # noqa: E501

    # TODO: There are three keys that are the same in mime mapping, so `mime_mapping` will only keep the last one
    # Turn the mime_list.json into a dict (from a list), with `str` keys and `list` values
    # What kind of checks do we do with mime mapping? It seems to check for keys only, not values
    # Should this be stored in parameter store?
    mime_mapping = get_mime_mapping("/usr/bin/validation-pipeline/mime_list.json")  # noqa: E501
    logger.info(mime_mapping)

    # TODO: If there are any changes to the Parameter Store values, approved filetypes would not be updated until this script/service is re-started
    # Figure out how to check and pull down the latest values (e.g. caching or nested loop or during sleep)
    while True:
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
            get_file.get_file(bucket, key, receipt_handle, all_approved_filetypes, mime_mapping)  # noqa: E501

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
        mime_list: list[dict] = json.load(file)
    return {k: v for d in mime_list for k, v in d.items()}


main()
