import json
import logging
import time

import get_file
from utils import get_param_value
from utils import receive_sqs_message

logging.basicConfig(format="[%(levelname)s] %(message)s", filename="/var/log/messages", level=logging.INFO)  # noqa: E501
logger = logging.getLogger()


def main():
    # TODO: Should this be stored in parameter store?
    mime_mapping = get_mime_mapping("/usr/bin/validation-pipeline/mime_list.json")  # noqa: E501
    logger.info(mime_mapping)

    # TODO: Implement a way to get updated values, without restarting the service
    queue_url = get_param_value("/pipeline/AvScanQueueUrl")
    approved_filetypes = get_param_value("/pipeline/ApprovedFileTypes").replace(".", "").replace(" ", "").split(",")  # noqa: E501
    dfdl_approved_filetypes = get_param_value("/pipeline/DfdlApprovedFileTypes").replace(".", "").replace(" ", "").split(",")  # noqa: E501
    approved_filetypes.extend(dfdl_approved_filetypes)
    sleep_period = 5

    while True:
        try:
            messages = receive_sqs_message(queue_url, 1)
            if not messages:
                continue

            logger.info("A message has been received")
            message = messages[0]
            receipt_handle = message["ReceiptHandle"]
            message_body = json.loads(message["Body"])
            bucket = message_body["detail"]["requestParameters"]["bucketName"]
            key = message_body["detail"]["requestParameters"]["key"]
            get_file.get_file(bucket, key, receipt_handle, approved_filetypes, mime_mapping)  # noqa: E501

        except Exception as e:
            logger.exception(e)
            logger.warning(f"Exception encountered. Sleeping for {sleep_period}...")  # noqa: E501
            time.sleep(sleep_period)


def get_mime_mapping(filepath: str):
    logger.info("Loading Mime Mapping")
    with open(filepath, "r", encoding="utf-8") as file:
        mime_list: dict = json.load(file)
    return mime_list


main()
