"""
Copyright 2022 Amazon Web Services, Inc. All Rights Reserved. 
This AWS content is subject to the terms of 
the Basic Ordering Agreement Contract No. 2018-17120800001-008
"""

import boto3
import json
import logging
import os
import urllib
import time
from urllib.parse import unquote_plus


from botocore.exceptions import ClientError


os.environ["AWS_DATA_PATH"] = "./models"



#diode = boto3.Session().client("diode", endpoint_url="https://diode.us-gov-west-1.amazonaws.com")
diode = boto3.Session().client("diode", endpoint_url='http://3.31.0.208:80')
os.environ["AWS_DATA_PATH"] = "./models"
logger = logging.getLogger()
s3_client = boto3.client('s3')


#Reference to Resources 

#diode_id = os.getenv('diode_mapping_id')


def return_status(src_bucket, key, diodeStatusCode, status, transfer_response):
    print('sending sqs')
    sqs_client = boto3.client('sqs')
    response = sqs_client.send_message(
        QueueUrl = os.getenv("TRANSFER_RESULT_QUEUE_URL"),
        MessageBody = json.dumps({
            'bucket': src_bucket,
            'key': key,
            'TransferStatusCode': diodeStatusCode,
            'Status': status,
            'mappingId': transfer_response["transfer"]["mappingId"],
            'transferId': transfer_response["transfer"]["transferId"],
            })
        )
    print(response)

def get_mapping(bucket,key):
    response = s3_client.get_object_tagging(
        Bucket=bucket,
        Key=key
    )
    print(response)
    tagset = response['TagSet']
    for tags in tagset:
        if tags['Key'] == 'CDSProfile':
            cds_profile = tags['Value']
            break
    print(cds_profile)
    if cds_profile == 'CDS_1':
        mapping = os.environ['CDS1_MAPPING']
    elif cds_profile == 'CDS_2':
        mapping = os.environ['CDS2_MAPPING']
    elif cds_profile == 'CDS_3':
        mapping = os.environ['CDS3_MAPPING'] 
    else:
        mapping = os.environ['CDS1_MAPPING']
    
    return mapping
def lambda_handler(event, context):

    logger.info(f"Incoming file: {event}")
    print(f'Event: {event}')
    
    region = os.environ['AWS_REGION']



    # message = event["Records"][0]["body"]
    msg = event["Records"][0]["body"]
    
    # print(f'Message: {msg}')
    msg = json.loads(msg)

    
    src_bucket = msg['Records'][0]['s3']['bucket']['name']
    key = msg['Records'][0]['s3']['object']['key']
    # After we've obtained the key name, perform the unquote_plus operation on it to handle any whitespace in the key name
    key = unquote_plus(key)
    diode_id = get_mapping(src_bucket, key)
    print(f'Mapping ID: {diode_id}')
    print(src_bucket, key)

    # if statusCode == 200:
    filename = key.split("/")[-1]
    if len(filename)>99:
        filename = filename[-99:]
        
    try:

        print('AttemptingTransfer')
        transfer_response = diode.create_transfer(
            description=f"{filename}",
            mappingId=diode_id,
            s3Bucket=src_bucket,
            s3Key=key,
            includeS3ObjectTags=True
        )  

        print(f"Transfer Response: {transfer_response}")
        diodeStatusCode = transfer_response['ResponseMetadata']['HTTPStatusCode']
    except Exception as e:
        print(f"TRANSFER FAILURE - ERROR {key} -- {e}")
        transfer_response = {"ResponseMetadata": {"HTTPStatusCode": 499},"transfer": {"mappingId":diode_id,"transferId":"FailedTransfer","s3Uri":key}}
        diodeStatusCode = 499
    logger.info(f"Diode transfer response: {transfer_response}")
    print(f'Transfer response: {transfer_response}')
    
    
    if diodeStatusCode != 200:
        logger.info(f'Failed transfer of {key}')
        print('failed transfer of key')
        status = 'FAILURE'
        return_status(src_bucket, key, diodeStatusCode, status, transfer_response)

    else:
        print('successful transfer of key')
        status = 'SUCCESS'
        return_status(src_bucket, key, diodeStatusCode, status, transfer_response)


