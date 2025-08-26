import json
import logging
import os
from urllib.parse import unquote_plus

import boto3  # type: ignore
from botocore.config import Config  # type: ignore
from botocore.exceptions import ClientError  # type: ignore

logger = logging.getLogger()
logger.setLevel(logging.INFO)

os.environ["AWS_DATA_PATH"] = "./models"

TRANSFER_BUCKET_OWNER = os.environ["TRANSFER_BUCKET_OWNER"]
TRANSFER_RESULT_QUEUE_URL = os.environ["TRANSFER_RESULT_QUEUE_URL"]
DATA_TRANSFER_QUEUE_URL = os.environ["DATA_TRANSFER_QUEUE_URL"]
TRANSFER_STATUS_QUEUE_URL = os.environ["TRANSFER_STATUS_QUEUE_URL"]
USE_DIODE_SIMULATOR = os.environ["USE_DIODE_SIMULATOR"]
DIODE_SIMULATOR_ENDPOINT = os.environ["DIODE_SIMULATOR_ENDPOINT"]
AWS_REGION = os.environ["AWS_REGION"]

config = Config(retries={"max_attempts": 3, "mode": "standard"})
diode_endpoint_url = f"https://diode.{AWS_REGION}.amazonaws.com"
if USE_DIODE_SIMULATOR == "True":
    diode_endpoint_url = DIODE_SIMULATOR_ENDPOINT

DIODE_CLIENT = boto3.client(
    "diode",
    config=config,
    endpoint_url=diode_endpoint_url,
)
S3_CLIENT = boto3.client("s3", config=config)
SQS_CLIENT = boto3.client("sqs", config=config)

CREATE_TRANSFER_FAILED = "CREATE_TRANSFER_FAILED"
# This should match the value defined in the transfer SQS queue in the validation account  # noqa: E501
MAX_RECEIVE_COUNT = 5

# https://boto3.amazonaws.com/v1/documentation/api/latest/guide/retries.html#standard-retry-mode
RETRYABLE_ERROR_CODES = [
    # Transient errors/exceptions
    "RequestTimeout",
    "RequestTimeoutException",
    "PriorRequestNotComplete",
    "ConnectionError",
    "HTTPClientError",
    # Service-side throttling/limit errors and exceptions
    "Throttling",
    "ThrottlingException",
    "ThrottledException",
    "RequestThrottledException",
    "TooManyRequestsException",
    "ProvisionedThroughputExceededException",
    "TransactionInProgressException",
    "RequestLimitExceeded",
    "BandwidthLimitExceeded",
    "LimitExceededException",
    "RequestThrottled",
    "SlowDown",
    "EC2ThrottledException",
    # CreateTransfer API specific errors
    "ResourceLimitExceededException",
    "TransientFailureException",
]

RETRYABLE_STATUS_CODES = [500, 502, 503, 504]

NO_MAPPING_ID = "None"


# NOTE: Lambda deletes the message from SQS queue if no error is raised
def lambda_handler(event, context):
    logger.info(f"Event: {json.dumps(event, default=str)}")

    message_body: dict = json.loads(event["Records"][0]["body"])
    records = message_body.get("Records")

    if records:  # event_source == "aws:s3"
        handle_create_transfer(event["Records"][0], records[0]["s3"])
    else:  # event_source == "aws:sqs"
        handle_transfer_status_event(
            message_body["detail"],
            event["Records"][0]["receiptHandle"],
        )


def handle_create_transfer(message: dict, s3: dict):
    logger.info("Processing a CreateTransfer request")

    receipt_handle = message["receiptHandle"]
    approx_rec_count = int(message["attributes"]["ApproximateReceiveCount"])
    logger.info(f"Approximate Receive Count: {approx_rec_count}")

    bucket = s3["bucket"]["name"]
    # unquote_plus for handling any whitespaces in the key name
    key = unquote_plus(s3["object"]["key"])
    logger.info(f"Bucket: {bucket}, Key: {key}")

    # Mapping ID cannot be an empty string, as it can cause an error in DDB
    mapping_id = NO_MAPPING_ID
    try:
        mapping_id = get_mapping_id(bucket, key)
        if mapping_id == NO_MAPPING_ID:
            raise NoMappingIdTagError

        logger.info(f"Mapping ID: {mapping_id}")

        create_transfer(mapping_id, bucket, key)
        delete_sqs_message(DATA_TRANSFER_QUEUE_URL, receipt_handle)

    except (ClientError, NoMappingIdTagError) as e:
        params = dict(
            bucket=bucket,
            key=key,
            mapping_id=mapping_id,
            status=CREATE_TRANSFER_FAILED,
            transfer_id="",
        )

        if isinstance(e, ClientError):
            error_code = e.response["Error"]["Code"]
            http_status_code = e.response["ResponseMetadata"]["HTTPStatusCode"]

            if (
                error_code in RETRYABLE_ERROR_CODES
                or http_status_code in RETRYABLE_STATUS_CODES
            ) and approx_rec_count < MAX_RECEIVE_COUNT:
                logger.warning(f"Retryable error: {e}")
                # Increase the visibility timeout based on the receive count
                change_message_visibility(
                    DATA_TRANSFER_QUEUE_URL,
                    message["receiptHandle"],
                    approx_rec_count * 30,
                )
                # Signal to Lambda not to delete the message by raising an error
                raise

            logger.error(f"Failed to create the transfer request for {key}: {e}")
            params.update({"error": error_code})

        elif isinstance(e, NoMappingIdTagError):
            logger.error(
                f"Failed to create the transfer request for {key}: NoMappingIdTagError",
            )
            params.update({"error": "NO_MAPPING_ID_TAG"})

        send_msg_to_transfer_result_queue(**params)
        delete_sqs_message(DATA_TRANSFER_QUEUE_URL, receipt_handle)


def handle_transfer_status_event(event_detail: dict, receipt_handle: str):
    logger.info("Processing a transfer status event")

    status = event_detail["status"]
    logger.info(f"Transfer Status: {status}")

    params = dict(
        bucket=event_detail["s3Bucket"],
        key=event_detail["s3Key"],
        mapping_id=event_detail["mappingId"],
        status=status,
        transfer_id=event_detail["transferId"],
    )
    logger.info(f"Transfer Detail: {params}")

    if status == "SUCCEEDED":
        send_msg_to_transfer_result_queue(**params)
        delete_sqs_message(TRANSFER_STATUS_QUEUE_URL, receipt_handle)
        return

    transfer = describe_transfer(params["transfer_id"])
    params.update({"error": transfer.get("errorMessage", "Unknown")})
    send_msg_to_transfer_result_queue(**params)
    delete_sqs_message(TRANSFER_STATUS_QUEUE_URL, receipt_handle)


def send_msg_to_transfer_result_queue(
    bucket: str,
    key: str,
    mapping_id: str,
    status: str,
    transfer_id: str,
    error="None",
):
    logger.info("Sending a message to Transfer Result SQS queue")

    SQS_CLIENT.send_message(
        QueueUrl=TRANSFER_RESULT_QUEUE_URL,
        MessageBody=json.dumps(
            {
                "bucket": bucket,
                "key": key,
                "mappingId": mapping_id,
                "status": status,
                "transferId": transfer_id,
                "error": error,
            },
        ),
    )


def change_message_visibility(queue_url: str, receipt_handle: str, timeout: int):
    # Unlike with a queue, when you change the visibility timeout for a specific
    # message, the timeout value is applied immediately but isn’t saved in memory
    # for that message. If you don’t delete a message after it is received, the
    # visibility timeout for the message reverts to the original timeout value
    # (not to the value you set using the ChangeMessageVisibility action) the
    # next time the message is received.

    logger.info(f"Updating the visibility timeout to {timeout}")

    try:
        SQS_CLIENT.change_message_visibility(
            QueueUrl=queue_url,
            ReceiptHandle=receipt_handle,
            VisibilityTimeout=timeout,
        )
    except ClientError as e:
        # Swallow any errors as this is not critical
        logger.warning(f"Could not update the visibility timeout: {e}")


def get_mapping_id(bucket, key):
    tags = get_object_tagging(bucket, key)
    return tags.get("MappingId", NO_MAPPING_ID)


def get_object_tagging(bucket: str, key: str) -> dict[str, str]:
    logger.info(f"Getting tags for {bucket}/{key}")

    tag_set = S3_CLIENT.get_object_tagging(
        Bucket=bucket,
        Key=key,
        ExpectedBucketOwner=TRANSFER_BUCKET_OWNER,
    )["TagSet"]
    tags = {tag["Key"]: tag["Value"] for tag in tag_set}

    logger.info(f"Tags: {tags}")

    return tags


def create_transfer(mapping_id: str, bucket: str, key: str, include_tags=True):
    logger.info(f"Creating a transfer request for {bucket}/{key}")

    response = DIODE_CLIENT.create_transfer(
        mappingId=mapping_id,
        s3Bucket=bucket,
        s3Key=key,
        # Take the last 100 chars of the key as description
        description=key.split("/")[-1][-100:],
        includeS3ObjectTags=include_tags,
    )["transfer"]

    logger.info(f"Transfer request created: {response}")


def describe_transfer(transfer_id: str) -> dict:
    logger.info(f"Getting details for transfer: {transfer_id}")

    try:
        transfer = DIODE_CLIENT.describe_transfer(transferId=transfer_id)["transfer"]
        logger.info(f"Transfer Details: {transfer}")
        return transfer
    except ClientError as e:
        logger.warning(f"Failed to get transfer details: {e}")
        return {}


def delete_sqs_message(queue_url: str, receipt_handle: str):
    queue_name = queue_url.split("/")[-1]
    logger.info(f"Deleting message from {queue_name} queue")
    SQS_CLIENT.delete_message(QueueUrl=queue_url, ReceiptHandle=receipt_handle)


class NoMappingIdTagError(Exception):
    pass
