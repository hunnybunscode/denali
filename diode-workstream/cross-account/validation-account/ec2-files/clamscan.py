import boto3
import os
import logging
import json
import random

s3_client = boto3.client('s3',region_name="us-gov-west-1")

logging.basicConfig(format='%(message)s', filename='/var/log/messages', level=logging.INFO)

#Function to perform AV Scan
ssm_client = boto3.client('ssm', region_name='us-gov-west-1')


def scanner(bucket, key, receipt_handle):

    try:
        #perform AV scan and capture result
        logging.info('Performing Fake clamdscan')
        #exitstatus = os.system(f'clamdscan /usr/bin/files')
        
        scan_result = random.randint(1,20)
        print(f'Random Scan Result: {scan_result}')
        if scan_result == 20:
            exitstatus = 512
        else:
            exitstatus = 0

        logging.info(f'File {key} ClamAV Scan Exit Code: {exitstatus}')
        if exitstatus == 0:
            file_status = 'CLEAN'
            logging.info(f'{key} is clean')
            logging.info(json.loads('{"eventName":"ObjectTagged","TagValue":[{"Key":"FILE_STATUS"},{"Value":"CLEAN"}]}'))
            msg = f'Moving file: {key} to Data Transfer bucket...'
            tag_file(bucket, key, file_status, msg, exitstatus, receipt_handle)   
     # If file does not exist
        elif exitstatus == 512:
            logging.info(f'File {key} not found. Unable to scan.')
            delete_sqs_message(receipt_handle)

        # If scan does not return a 'CLEAN' result
        else:
            file_status = 'INFECTED'
            exit_status = 999
            logging.warning(f'{key} is infected')
            quarantine_bucket_response = ssm_client.get_parameter(
                Name = '/pipeline/QuarantineBucketName')
            quarantine_bucket = quarantine_bucket_response['Parameter']['Value']
            msg = f'Quarantined File: {key} stored in {bucket}'
            tag_file(bucket, key, file_status, msg, exitstatus, receipt_handle)
            publish_sns(quarantine_bucket, key, file_status, exit_status)
    except Exception as e:
        logging.error(f'Exception ocurred scanning file: {e}')




# Function to tag file depending on scan result
def tag_file(bucket, key, file_status, msg, exitstatus, receipt_handle):
    try:
        get_tags_response = s3_client.get_object_tagging(
            Bucket = bucket,
            Key = key
        )
        existing_tags = get_tags_response['TagSet']
        logging.info(f'Existing Object TagSet: {existing_tags}')
        new_tags = {
            'AV_SCAN_STATUS': file_status,
            'CLAM_AV_EXIT_CODE': str(exitstatus)
        }
        combined_tags = existing_tags + [{'Key': k, 'Value': v} for k, v in new_tags.items()]
        logging.info(f'Tagging {key} in Bucket {bucket}')
        response = s3_client.put_object_tagging(
            Bucket = bucket,
            Key = key,
            Tagging = {
                'TagSet': combined_tags
            },
        )
        tag_status_code = response["ResponseMetadata"]["HTTPStatusCode"]
        if tag_status_code == 200:
            logging.info(f'SUCCESS: {key} Successfully Tagged with HTTPStatusCode {tag_status_code}')
        else:
            logging.info(f'FAILURE: Unable to tag {key}.  HTTPStatusCode: {tag_status_code}') 
        #remove file from local storage
        os.system(f'rm -r /usr/bin/files/*')
        if file_status == 'CLEAN':
            dest_bucket_response = ssm_client.get_parameter(
                Name = '/pipeline/DataTransferIngestBucketName',)
            ingest_bucket = dest_bucket_response['Parameter']['Value']
            dest_bucket = ingest_bucket
        else:
            dest_bucket_response = ssm_client.get_parameter(
                Name = '/pipeline/QuarantineBucketName',)
            quarantine_bucket = dest_bucket_response['Parameter']['Value']
            dest_bucket = quarantine_bucket
        move_file(bucket, key, dest_bucket, msg, receipt_handle)
    except Exception as e:
        logging.error(f'Exception ocurred Tagging file: {e}')
def quarantine_file(bucket, key, dest_bucket, msg, receipt_handle):
    logging.info(f'Quarantining {key}')
    try:
        response = s3_client.copy_object(
            Bucket = dest_bucket,
            CopySource = f'{bucket}/{key}',
            Key = key,
            )
        delete_sqs_message(receipt_handle)
        send_sqs(dest_bucket, key)
        
        response = s3_client.delete_object(
            Bucket = bucket,
            Key = key
            )
    except Exception as e:
        logging.error(f'Exception ocurring quarantining file ---{e}')
# Copies file to proper destination bucket
def move_file(bucket, key, dest_bucket, msg, receipt_handle):
    logging.info(msg)
    try:
        response = s3_client.copy_object(
            Bucket = dest_bucket,
            CopySource = f'{bucket}/{key}',
            Key = key,
            )
        copy_status_code = response['ResponseMetadata']['HTTPStatusCode']
        logging.info(f'Copy Object Response {response}')
        if copy_status_code == 200:
            logging.info(f'SUCCESS: {key} successfully transferred to {dest_bucket} with HTTPStatusCode: {copy_status_code}')
            delete_sqs_message(receipt_handle)
            #send_sqs(dest_bucket,key)
            delete_file(bucket, key)
        else:
            logging.error(f"FAILURE: Unable to Copy Object: {key} to {dest_bucket}.  StatusCode: {copy_status_code}")
    except Exception as e:
        logging.error(f'Exception ocurred copying object to {dest_bucket}: {e}')
    
def send_sqs(dest_bucket, key):
    sqs_client = boto3.client('sqs', region_name = 'us-gov-west-1')
    transfer_queue_response = ssm_client.get_parameter(
        Name = '/pipeline/DataTransferQueueUrl')
    transfer_queue = transfer_queue_response['Parameter']['Value']
    try:
        logging.info('Sending SQS Message....')
        response = sqs_client.send_message(
            QueueUrl = transfer_queue,
            MessageBody = json.dumps({
                'bucket': dest_bucket,
                'key': key
                })
            )
        send_sqs_status_code = response['ResponseMetadata']['HTTPStatusCode']
        if send_sqs_status_code == 200:
            logging.info(f'SUCCESS: SQS Message Successfully sent to Diode Transfer Account.  HTTPStatusCode: {send_sqs_status_code}')
        else:
            logging.info(f'FAILURE: SQS Message Unable to send to Diode Transfer Account.  HTTPStatusCode: {send_sqs_status_code}')
        logging.info(f'SQS Response: {response}')
    except Exception as e:
        logging.info(f'Error Occurred sending SQS Message.  Exception: {e}')
        

# Function to delete file from ingest bucket
def delete_file(bucket, key):
    lts_bucket_response = ssm_client.get_parameter(
        Name = '/pipeline/LongTermStorageBucketName')
    lts_bucket_name = lts_bucket_response['Parameter']['Value']
    lts_bucket = lts_bucket_name
    try:
        logging.info(f'Moving file to {lts_bucket}')
        response = s3_client.copy_object(
            Bucket = lts_bucket,
            CopySource = f'{bucket}/{key}',
            Key = key
        )
        copy_object_status_code = response['ResponseMetadata']['HTTPStatusCode']
        if copy_object_status_code == 200:
            logging.info(f'SUCCESS: {key} successfully transferred to storage bucket: {lts_bucket}')
        else:
            logging.info(f'FAILURE: {key} transfer to {lts_bucket} received StatusCode: {copy_object_status_code}')
        logging.info(f'Deleting file: {key} from Bucket: {bucket}')
        response = s3_client.delete_object(
            Bucket = bucket, 
            Key = key
            )
        delete_object_status_code = response['ResponseMetadata']['HTTPStatusCode']
        if delete_object_status_code == 204:
            logging.info(f'SUCCESS:  {key} successfully deleted from {bucket}.  StatusCode: {delete_object_status_code}')
        else:
            logging.info(f'FAILURE: Unable to delete {key} from {bucket}.  StatusCode: {delete_object_status_code}')
        logging.info(f'Delete Object Response: {response}')
    except Exception as e:
        logging.error(f'Exception ocurred deleting object: {e}')

def delete_sqs_message(receipt_handle):
    sqs_client = boto3.client('sqs', region_name = 'us-gov-west-1')
    av_scan_queue_response = ssm_client.get_parameter(
        Name = '/pipeline/AvScanQueueUrl')
    av_scan_queue_url = av_scan_queue_response['Parameter']['Value']
    try:
        logging.info('Deleting SQS Message....')
        del_msg_response = sqs_client.delete_message(
            QueueUrl = av_scan_queue_url,
            ReceiptHandle = receipt_handle
            )
        del_msg_status_code = del_msg_response['ResponseMetadata']['HTTPStatusCode']
        if del_msg_status_code == 200:
            logging.info(f'SUCCESS:  SQS Message successfully deleted from Queue.  StatusCode: {del_msg_status_code}')
        else: 
            logging.info(f'FAILURE: Unable to delete SQS Message from Queue.  StatusCode: {del_msg_status_code}')
    except Exception as e:
        logging.info(f'An Error Ocurred Deleting SQS Message queue.  Error: {e}')

def publish_sns(bucket, key, file_status, exitstatus):
    try:
        logging.info('Publishing SNS Message for Quarantined file')
        sns_client = boto3.client('sns', region_name='us-gov-west-1')
        quarantine_topic_response = ssm_client.get_parameter(
            Name = '/pipeline/QuarantineTopicArn')
        quarantine_topic_arn = quarantine_topic_response['Parameter']['Value']
        message = f'A File has been quarantined due to the results of a ClamAV Scan.\nFile: {key}\nFile Status: {file_status}\nClamAV Exit Code: {exitstatus}\nFile Location: {bucket}/{key}'
        response = sns_client.publish(
            TopicArn = quarantine_topic_arn,
            Message = message,
            MessageStructure = 'text',
            Subject = f'A file  has been quarantined in the quarantin S3 Bucket following a ClamAV Scan'
            )
        print('made it here')
        print(response)
        sns_publish_status_code = response['ResponseMetadata']['HTTPStatusCode']
        if sns_publish_status_code == 200:
            logging.info(f'SUCCESS:  SNS Message Successfully published.  StatusCode: {sns_publish_status_code}')
        else:
            logging.info(f'FAILURE: Unable to Publish SNS Message.  StatusCode: {sns_publish_status_code}')
    except Exception as e:
        logging.error(f'An Exception ocurred publishing SNS: {e}')



