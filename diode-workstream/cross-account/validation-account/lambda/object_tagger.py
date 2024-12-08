import json
import boto3
import os
def add_tags(bucket, key):
    gov_poc = os.environ['GOV_POC']
    data_owner = os.environ['DATA_OWNER']
    key_owner = os.environ['KEY_OWNER']
    cds_profile = os.environ['CDS_PROFILE']
    tags = [
        {'Key': 'GovPOC', 'Value': gov_poc},
        {'Key': 'DataOwner', 'Value': data_owner},
        {'Key': 'KeyOwner', 'Value': key_owner},
        {'Key': 'CDSProfile', 'Value': cds_profile}
    ]
    
    s3_client = boto3.client('s3')
    response = s3_client.put_object_tagging(
        Bucket = bucket,
        Key = key,
        Tagging = {
            'TagSet': tags
        }
        )
    print(f'Tagging Response = {response}')
def send_to_sqs(bucket, key):
    sqs_client = boto3.client('sqs')
    queue_url = os.environ['QUEUE_URL']
    
    response = sqs_client.send_message(
        QueueUrl = queue_url,
        MessageBody = json.dumps({
            'detail': {
                'requestParameters':{
                    'bucketName':bucket,
                    'key': key
                }
            }
        })
        
        )
    print(f'sqs response: {response}')

def lambda_handler(event, context):
    
    bucket = event["Records"][0]["s3"]["bucket"]["name"]
    key = event["Records"][0]["s3"]["object"]["key"]
    
    add_tags(bucket,key)
    send_to_sqs(bucket, key)
    
    
    # TODO implement
    return {
        'statusCode': 200,
        'body': json.dumps('Hello from Lambda!')
    }
