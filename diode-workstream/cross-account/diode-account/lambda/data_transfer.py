import json
import logging
import os
from urllib.parse import unquote_plus

import boto3  # type: ignore
from botocore.config import Config  # type: ignore
from botocore.exceptions import ClientError  # type: ignore


# REGION = os.environ["AWS_REGION"]
# DIODE_ID = os.environ["diode_mapping_id"]

CDS1_MAPPING = os.environ["CDS1_MAPPING"]
CDS2_MAPPING = os.environ["CDS2_MAPPING"]
CDS3_MAPPING = os.environ["CDS3_MAPPING"]

os.environ["AWS_DATA_PATH"] = "./models"
logger = logging.getLogger()
logger.setLevel(logging.INFO)

config = Config(retries={"max_attempts": 5, "mode": "standard"})
# diode = boto3.Session().client("diode", endpoint_url="https://diode.us-gov-west-1.amazonaws.com")
DIODE_CLIENT = boto3.client("diode", endpoint_url="http://3.31.0.208:80")
# os.environ["AWS_DATA_PATH"] = "./models"

S3_CLIENT = boto3.client("s3", config=config)


def lambda_handler(event, context):
    logger.info(f"Event: {event}")

    msg = json.loads(event["Records"][0]["body"])

    src_bucket = msg["Records"][0]["s3"]["bucket"]["name"]
    key = msg["Records"][0]["s3"]["object"]["key"]

    # After we've obtained the key name, perform the unquote_plus operation on it to handle any whitespace in the key name
    key = unquote_plus(key)
    diode_id = get_mapping(src_bucket, key)
    logger.info(f"Mapping ID: {diode_id}")
    logger.info(f"Bucket: {src_bucket}, Key: {key}")

    filename = key.split("/")[-1]
    if len(filename) > 99:
        filename = filename[-99:]

    try:
        logger.info("AttemptingTransfer")
        transfer_response = DIODE_CLIENT.create_transfer(
            description=f"{filename}",
            mappingId=diode_id,
            s3Bucket=src_bucket,
            s3Key=key,
            includeS3ObjectTags=True
        )

        diodeStatusCode = transfer_response["ResponseMetadata"]["HTTPStatusCode"]
    except Exception as e:
        logger.error(f"TRANSFER FAILURE - ERROR {key} -- {e}")
        transfer_response = {"ResponseMetadata": {"HTTPStatusCode": 499}, "transfer": {
            "mappingId": diode_id, "transferId": "FailedTransfer", "s3Uri": key}}
        diodeStatusCode = 499
    logger.info(f"Diode transfer response: {transfer_response}")

    if diodeStatusCode == 200:
        logger.info("successful transfer of key")
        status = "SUCCESS"
        return_status(src_bucket, key, diodeStatusCode,
                      status, transfer_response)
    else:
        logger.error(f"Failed transfer of {key}")
        status = "FAILURE"
        return_status(src_bucket, key, diodeStatusCode,
                      status, transfer_response)


def return_status(src_bucket, key, diodeStatusCode, status, transfer_response):
    logger.info("sending sqs")
    sqs_client = boto3.client("sqs")
    response = sqs_client.send_message(
        QueueUrl=os.getenv("TRANSFER_RESULT_QUEUE_URL"),
        MessageBody=json.dumps({
            "bucket": src_bucket,
            "key": key,
            "TransferStatusCode": diodeStatusCode,
            "Status": status,
            "mappingId": transfer_response["transfer"]["mappingId"],
            "transferId": transfer_response["transfer"]["transferId"],
        })
    )
    logger.info(response)


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
