import json
import logging
import os

import boto3  # type: ignore
from botocore.config import Config  # type: ignore

logger = logging.getLogger()
logger.setLevel(logging.INFO)


AV_SCAN_QUEUE_URL = os.environ["AV_SCAN_QUEUE_URL"]

config = Config(retries={"max_attempts": 5, "mode": "standard"})
SQS_CLIENT = boto3.client("sqs", config=config)


def lambda_handler(event, context):
    logger.info(f"Event: {json.dumps(event, default=str)}")
    send_to_sqs(event)
    logger.info("SUCCESS")


def send_to_sqs(event: dict):
    logger.info("Sending a message to the SQS queue")
    SQS_CLIENT.send_message(
        QueueUrl=AV_SCAN_QUEUE_URL,
        MessageBody=json.dumps(event),
    )
