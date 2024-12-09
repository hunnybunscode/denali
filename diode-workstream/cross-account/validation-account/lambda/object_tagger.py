import json
import logging
import os

import boto3  # type: ignore
from botocore.config import Config  # type: ignore

logger = logging.getLogger()
logger.setLevel(logging.INFO)
config = Config(retries={"max_attempts": 5, "mode": "standard"})
S3_CLIENT = boto3.client('s3', config=config)
SQS_CLIENT = boto3.client('sqs', config=config)


def add_tags(bucket, key):
    gov_poc = os.environ['GOV_POC']
    data_owner = os.environ['DATA_OWNER']
    key_owner = os.environ['KEY_OWNER']
    cds_profile = os.environ['CDS_PROFILE']

    # Amazon S3 limits the maximum number of tags to 10 tags per object
    tags = [
        {'Key': 'GovPOC', 'Value': gov_poc},
        {'Key': 'DataOwner', 'Value': data_owner},
        {'Key': 'KeyOwner', 'Value': key_owner},
        {'Key': 'CDSProfile', 'Value': cds_profile}
    ]

    response = S3_CLIENT.put_object_tagging(
        Bucket=bucket,
        Key=key,
        Tagging={
            'TagSet': tags
        },
        # TODO: We should add this for enhanced security
        # ExpectedBucketOwner
    )
    logger.info(f'Tagging Response = {response}')


def send_to_sqs(bucket, key):
    queue_url = os.environ['QUEUE_URL']

    response = SQS_CLIENT.send_message(
        QueueUrl=queue_url,
        MessageBody=json.dumps({
            'detail': {
                'requestParameters': {
                    'bucketName': bucket,
                    'key': key
                }
            }
        })

    )
    logger.info(f'sqs response: {response}')


def lambda_handler(event, context):

    bucket = event["Records"][0]["s3"]["bucket"]["name"]
    key = event["Records"][0]["s3"]["object"]["key"]

    add_tags(bucket, key)
    send_to_sqs(bucket, key)
