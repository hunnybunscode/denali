import json
import boto3
import logging
logger = logging.getLogger()

def lambda_handler(event, context):
    logger.info(f'Event: {event}')
    print(f'Event: {event}')
    
    bucket = event["queryStringParameters"]['bucket']
    key = event["queryStringParameters"]['key']
    logger.info(f'Bucket: {bucket}')
    logger.info(f'Key: {key}')

    
    s3_client = boto3.client('s3')
    
    response_body = s3_client.generate_presigned_post(
        Bucket = bucket,
        Key = key
        )
    #response_body = json.dumps(response_body)
    logger.info(f'Response Body: {response_body}')

    response = {
        "statusCode":200,
        "body":json.dumps(response_body),
        "isBase64Encoded": False
    }
    
    return response