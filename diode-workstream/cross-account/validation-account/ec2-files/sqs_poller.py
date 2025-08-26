import errno
import json
import logging
import time
from logging.handlers import TimedRotatingFileHandler

from config import file_handler_config
from config import instance_info
from config import resource_suffix
from config import ssm_params
from utils import await_clamd
from utils import change_message_visibility
from utils import get_instance_id
from utils import get_params_values
from utils import mark_instance_as_unhealthy
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

    instance_info["instance_id"] = get_instance_id()

    clamd_ready = await_clamd()
    if not clamd_ready:
        logger.error("Marking the instance as unhealthy")
        mark_instance_as_unhealthy(instance_info["instance_id"])
        return

    ttl = 60
    clock = -ttl  # To enable the first run within the while loop

    while True:
        try:
            # Refresh SSM parameters every `ttl` seconds
            if time.perf_counter() >= clock + ttl:
                logger.info("Refreshing SSM parameters")
                get_params_values(ssm_params)
                clock = time.perf_counter()

            queue_url = ssm_params[f"/pipeline/AvScanQueueUrl-{resource_suffix}"]
            # Returns one message only, if any
            messages = receive_sqs_message(queue_url)
            if not messages:
                logger.info("No messages were received")
                continue

            logger.info("A message has been received")
            logger.info("-" * 100)

            message = messages[0]
            logger.info(f"Message: {message}")
            receipt_handle = message["ReceiptHandle"]
            receive_count = int(message["Attributes"]["ApproximateReceiveCount"])
            if receive_count > 1:
                logger.warning(f"This message has been received {receive_count} times")
                change_message_visibility(queue_url, receipt_handle, receive_count * 30)

            message_body: dict = json.loads(message["Body"])
            s3_event: dict = message_body["Records"][0]
            validate_file(s3_event, receipt_handle)

            logger.info("-" * 100)

        except OSError as e:
            if e.errno == errno.ENOSPC:
                logger.exception("No space left on device")
                mark_instance_as_unhealthy(instance_info["instance_id"])
                return
            else:
                logger.exception("Other OSError")
                raise

        except Exception as e:
            logger.exception(e)
            logger.info(
                "Sleeping for 3 seconds, before proceeding to receive the next message",  # noqa: E501
            )
            time.sleep(3)  # nosemgrep arbitrary-sleep


if __name__ == "__main__":
    main()
