import boto3
import json
import time
import get_file
import logging

logging.basicConfig(format='%(message)s', filename='/var/log/messages', level=logging.INFO)
sqs_client = boto3.client('sqs', region_name = 'us-gov-west-1')
queue = True
ssm_client = boto3.client('ssm', region_name = 'us-gov-west-1')

ssm_client = boto3.client('ssm', region_name='us-gov-west-1')
response = ssm_client.get_parameter(Name='/pipeline/ApprovedFileTypes')
dfdl_response = ssm_client.get_parameter(Name='/pipeline/DfdlApprovedFileTypes')
approved_filetypes = f"{response['Parameter']['Value'].replace('.','')}, {dfdl_response['Parameter']['Value'].replace('.','')}"

ssm_response = ssm_client.get_parameter(
    Name='/pipeline/AvScanQueueUrl'
    )
queue_url = ssm_response['Parameter']['Value']

# Get Mime Mapping
logging.info('Loading Mime Mapping')
mime_data = json.loads(open('/usr/bin/validation-pipeline/mime_list.json').read())
mime_mapping = {}
for i in mime_data:
    mime_mapping.update(i)
logging.info(mime_mapping)
while queue == True:
    try:
        response = sqs_client.receive_message(
            QueueUrl=queue_url,
            MaxNumberOfMessages=1
            )
        #for message in response:
        receipt_handle = response['Messages'][0]['ReceiptHandle']
        # load message for parsing to obtain bucket and key
        response_body = json.loads(response['Messages'][0]['Body'])
        bucket = response_body['detail']['requestParameters']['bucketName']
        key = response_body['detail']['requestParameters']['key']
        logging.info(f'Found File: {key}')
        get_file.get_file(bucket, key, receipt_handle, approved_filetypes, mime_mapping)

    except KeyError as e:
        print(f'KeyError: No Available Messages----------{e}')
        #queue = False
    
    except Exception as e:
        print(e)
        time.sleep(10)
