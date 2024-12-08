import json
import os
import boto3
import zoneinfo
from datetime import datetime
import logging

from urllib.parse import unquote_plus

logger = logging.getLogger()

dynamodb_table_name = os.environ['DYNAMODB_TABLE_NAME']

ddb_client = boto3.client('dynamodb')
s3_client = boto3.client('s3')
sns_client = boto3.client('sns')

# TODO: Add handling for Failed Transfers - Delete Object From Pitcher, Move object to failed transfer bucket, Send SNS Message

def publish_sns(key):
    print('Sending SNS Message due to failed statusCode')
    response = sns_client.publish(
        TopicArn = os.getenv('FAILED_TRANSFER_TOPIC_ARN'),
        Message = f'The File {key} was not successfully transferred.\nIt has been moved from the Data Transfer bucket and is now located at the following Location:\n{os.getenv("FAILED_TRANSFER_BUCKET")}/{key}',
        Subject = 'Failed Cross Domain Trainsfer'
    )

def move_object(key):
    move_response = s3_client.copy_object(
        Bucket = os.getenv('FAILED_TRANSFER_BUCKET'),
        CopySource = {'Bucket': os.getenv('DATA_TRANSFER_BUCKET'), 'Key': key},
        Key = key
    )
    logger.info(f'Copy Response: {move_response}')
    
    
def delete_object(key):
    del_response = s3_client.delete_object(
        Bucket = os.getenv('DATA_TRANSFER_BUCKET'),
        Key = key
    )
    logger.info(f'Delete Response: {del_response}')



def get_object_tagging(bucket, key):
    print(f'Getting Object Tags for {bucket}/{key}')
    try: 
        response = s3_client.get_object_tagging(
            Bucket = bucket,
            Key = key
            )
        tags = response['TagSet']
        data_owner = None
        gov_poc = None   
        key_owner = None
        for i in tags:
            if i['Key'] == 'DataOwner':
                data_owner = i['Value']
            elif i['Key'] == 'GovPOC':
                gov_poc = i['Value']
            elif i['Key'] == 'KeyOwner':
                key_owner = i['Value']
            else:
                pass
        # print(f'Data Owner = {data_owner}')
        # print(f'Gov POC = {gov_poc}')
        # print(f'Key Owner = {key_owner}')
        print(f'{key} tags obtained: {tags}')
        return data_owner, gov_poc, key_owner
    except Exception as e:
        logger.error(f'Exception occurred getting object tags ------- {e}')
        #print(f'Exception occurred getting object tags ------- {e}')
        data_owner = 'Unknown'
        gov_poc = 'Unknown'
        key_owner = 'Unknown'
        return data_owner, gov_poc, key_owner


def lambda_handler(event, context):
    print(event)
    data = event["Records"][0]["body"]
    data = json.loads(data)

    gov_poc = 'unknown'
    data_owner = 'unknown'
    key_owner = 'unknown'
    
    bucket = data["bucket"]
    key = data["key"]
    key = unquote_plus(key)
    statusCode = data["TransferStatusCode"] 
    
    data_owner, gov_poc, key_owner = get_object_tagging(bucket, key)
    
    try:
        ny_tz = zoneinfo.ZoneInfo("America/New_York")
        current_timestamp= datetime.now(ny_tz)

        ddb_client.put_item(
            TableName=dynamodb_table_name,
            Item={
                "mappingId": {"S": data["mappingId"]},
                "transferId": {"S": data["transferId"]},
                "s3Key": {"S": data["key"]},
                "TransferStatusCode": {"S": str(statusCode)},
                "Status": {"S": data["Status"]},
                "timestamp": {"S": str(current_timestamp)},
                "govPoc": {"S": gov_poc},
                "dataOwner": {"S": data_owner},
                "keyOwner": {"S": key_owner},
            },
        )
    except Exception as e:
        print(e)
        print(
            "Error putting metadata about object {} into DynamoDB table".format(
                data["key"]
            )
        )
        raise e
    
    if statusCode != 200:
        print(f'Transfer failed - moving {bucket}/{key} to {os.environ["FAILED_TRANSFER_BUCKET"]}')
        publish_sns(key)
        move_object(key)

    delete_object(key)
    
    
    return {
        'statusCode': 200,
        'body': json.dumps('Result Successfully Captured')
    }
