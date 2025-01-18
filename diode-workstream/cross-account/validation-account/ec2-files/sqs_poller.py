import json
import logging
import time
from logging.handlers import TimedRotatingFileHandler

from config import approved_filetypes
from config import file_handler_config
from config import resource_suffix
from config import ssm_params
from utils import get_params_values
from utils import receive_sqs_message
from validation import validate_file

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger()
file_handler = TimedRotatingFileHandler(**file_handler_config)
formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)


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
                approved_filetypes.extend(
                    [
                        *(
                            ssm_params[f"/pipeline/ApprovedFileTypes-{resource_suffix}"]
                            .replace(".", "")
                            .replace(" ", "")
                            .split(",")
                        ),
                        *(
                            ssm_params[
                                f"/pipeline/DfdlApprovedFileTypes-{resource_suffix}"
                            ]
                            .replace(".", "")
                            .replace(" ", "")
                            .split(",")
                        ),
                    ],
                )
                clock = time.perf_counter()

            messages = receive_sqs_message(
                ssm_params[f"/pipeline/AvScanQueueUrl-{resource_suffix}"],
                1,
            )
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
            logger.info(
                "Sleeping for 3 seconds, before proceeding to receive the next message",
            )
            time.sleep(3)  # nosemgrep arbitrary-sleep


if __name__ == "__main__":
    main()
