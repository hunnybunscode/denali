import json
import logging
import time

from config import approved_filetypes
from config import ssm_params
from utils import get_params_values
from utils import receive_sqs_message
from validation import validate_file

logging.basicConfig(format="[%(levelname)s] %(message)s", filename="/var/log/messages", level=logging.INFO)  # noqa: E501
logger = logging.getLogger()


def main():
    logger.info("Starting SQS Poller")

    # TODO: Explore using SSM Document to update the values when changes occur
    # TODO: Use signal to gracefully exit in case of instance termination
    # TODO: Implement a health check

    ttl = 60
    clock = -ttl  # To enable the first run within the while loop

    while True:
        try:
            # Refresh SSM parameters every `ttl` seconds
            if time.perf_counter() >= clock + ttl:
                logger.info("Refreshing SSM parameters")
                get_params_values(ssm_params)
                approved_filetypes.clear()
                approved_filetypes.extend([
                    *(ssm_params["/pipeline/ApprovedFileTypes"].replace(".", "").replace(" ", "").split(",")),  # noqa: E501
                    *(ssm_params["/pipeline/DfdlApprovedFileTypes"].replace(".", "").replace(" ", "").split(","))
                ])
                clock = time.perf_counter()

            messages = receive_sqs_message(ssm_params["/pipeline/AvScanQueueUrl"], 1)  # noqa: E501
            if not messages:
                continue

            logger.info("A message has been received")
            logger.info("-" * 100)

            message = messages[0]
            receipt_handle = message["ReceiptHandle"]
            message_body = json.loads(message["Body"])
            bucket = message_body["detail"]["requestParameters"]["bucketName"]
            key = message_body["detail"]["requestParameters"]["key"]
            validate_file(bucket, key, receipt_handle)

            logger.info("-" * 100)

        except Exception as e:
            logger.exception(e)
            logger.info("Sleeping for 3 seconds, before proceeding to receive the next message")  # noqa: E501
            time.sleep(3)


if __name__ == "__main__":
    main()
