import json
import logging
import os
import time
from urllib.parse import unquote_plus

import boto3  # type: ignore
from botocore.config import Config  # type: ignore
from botocore.exceptions import ClientError  # type: ignore


CDS1_MAPPING = os.environ["CDS1_MAPPING"]
CDS2_MAPPING = os.environ["CDS2_MAPPING"]
CDS3_MAPPING = os.environ["CDS3_MAPPING"]
QUEUE_URL = os.environ["TRANSFER_RESULT_QUEUE_URL"]

os.environ["AWS_DATA_PATH"] = "./models"

logger = logging.getLogger()
logger.setLevel(logging.INFO)

config = Config(retries={"max_attempts": 5, "mode": "standard"})
# diode = boto3.Session().client("diode", endpoint_url="https://diode.us-gov-west-1.amazonaws.com")
DIODE_CLIENT = boto3.client("diode", config=config, endpoint_url="http://3.31.0.208:80")  # noqa: E501
S3_CLIENT = boto3.client("s3", config=config)
SQS_CLIENT = boto3.client("sqs", config=config)


def lambda_handler(event, context):
    logger.info(f"Event: {json.dumps(event, default=str)}")

    msg = json.loads(event["Records"][0]["body"])
    src_bucket = msg["Records"][0]["s3"]["bucket"]["name"]
    key = msg["Records"][0]["s3"]["object"]["key"]

    # After we've obtained the key name, handle any whitespaces in the key name
    key = unquote_plus(key)
    mapping_id = get_mapping(src_bucket, key)
    logger.info(f"Mapping ID: {mapping_id}")
    logger.info(f"Bucket: {src_bucket}, Key: {key}")

    # Extract the filename and take the last 100 characters only
    # filename is used as a description, which cannot exceed 100 in length
    filename = key.split("/")[-1][-100:]

    try:
        logger.info(f"Creating a transfer request for {key}")
        transfer_response = DIODE_CLIENT.create_transfer(
            description=f"{filename}",
            mappingId=mapping_id,
            s3Bucket=src_bucket,
            s3Key=key,
            includeS3ObjectTags=True
        )

        # TODO: Replace this with a CW event-based transfer status check
        time.sleep(10)  # nosemgrep

        logger.info(f"Transfer request created: {transfer_response}")
        status_code = transfer_response["ResponseMetadata"]["HTTPStatusCode"]
        status = "SUCCESS"
    except ClientError as e:
        logger.error(f"Transfer request could not be created for {key}: {e}")
        transfer_response = {"transfer": {
            "mappingId": mapping_id, "transferId": "FailedTransfer"
        }}
        status_code = 499
        status = "FAILURE"

    send_transfer_status(src_bucket, key, status_code,
                         status, transfer_response)


def send_transfer_status(src_bucket, key, status_code, status, transfer_response):
    logger.info("Sending a message on transfer status to SQS queue")
    SQS_CLIENT.send_message(
        QueueUrl=QUEUE_URL,
        MessageBody=json.dumps({
            "bucket": src_bucket,
            "key": key,
            "TransferStatusCode": status_code,
            "Status": status,
            "mappingId": transfer_response["transfer"]["mappingId"],
            "transferId": transfer_response["transfer"]["transferId"],
        })
    )
    logger.info("Message sent successfully")


def get_mapping(bucket, key):
    tagset = S3_CLIENT.get_object_tagging(
        Bucket=bucket,
        Key=key
    )["TagSet"]
    logger.info(tagset)

    for tags in tagset:
        if tags["Key"] == "CDSProfile":
            cds_profile = tags["Value"]
            break

    logger.info(cds_profile)
    if cds_profile == "CDS_1":
        return CDS1_MAPPING
    if cds_profile == "CDS_2":
        return CDS2_MAPPING
    if cds_profile == "CDS_3":
        return CDS3_MAPPING

    return CDS1_MAPPING
