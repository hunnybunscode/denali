import json
import logging
import time

from get_file import get_file
from utils import get_param_value
from utils import receive_sqs_message

logging.basicConfig(format="[%(levelname)s] %(message)s", filename="/var/log/messages", level=logging.INFO)  # noqa: E501
logger = logging.getLogger()


def main():
    logger.info("Starting SQS Poller")

    # TODO: Implement a way to get updated values, without restarting the service
    # https://stackoverflow.com/questions/57260724/how-to-call-a-function-only-once-every-x-time-in-an-infinite-loop-in-python
    # TODO: Explore using SSM Document to update the values when changes occur
    # TODO: Use signal to gracefully exit in case of instance termination
    # TODO: Implement a health check

    queue_url = get_param_value("/pipeline/AvScanQueueUrl")
    approved_filetypes = get_param_value("/pipeline/ApprovedFileTypes").replace(".", "").replace(" ", "").split(",")  # noqa: E501
    dfdl_approved_filetypes = get_param_value("/pipeline/DfdlApprovedFileTypes").replace(".", "").replace(" ", "").split(",")  # noqa: E501
    approved_filetypes.extend(dfdl_approved_filetypes)
    sleep_period = 1

    while True:
        try:
            messages = receive_sqs_message(queue_url, 1)
            if not messages:
                continue

            logger.info("-" * 100)
            logger.info("A message has been received")
            message = messages[0]
            receipt_handle = message["ReceiptHandle"]
            message_body = json.loads(message["Body"])
            bucket = message_body["detail"]["requestParameters"]["bucketName"]
            key = message_body["detail"]["requestParameters"]["key"]
            get_file(bucket, key, receipt_handle, approved_filetypes)
            logger.info("-" * 100)

        except Exception as e:
            logger.exception(e)
            logger.info(f"Sleeping for {sleep_period} second(s) before retrieving the next message")  # noqa: E501
            time.sleep(sleep_period)


if __name__ == "__main__":
    main()
