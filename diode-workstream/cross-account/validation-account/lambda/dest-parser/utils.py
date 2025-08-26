import boto3
import json
import logging
import os
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)

s3_client = boto3.client('s3')
ssm_client = boto3.client('ssm')
sns_client = boto3.client('sns')

def get_dest_tag(bucket, key):
    """Get DestinationMappingKey tag from S3 object"""
    logger.info(f"Getting tags for object {key} in bucket {bucket}")
    
    response = s3_client.get_object_tagging(
        Bucket=bucket,
        Key=key
    )
    
    tagset = response["TagSet"]
    logger.debug(f"Found {len(tagset)} tags on object {key}")
    
    for tag in tagset:
        if tag["Key"] == "DestinationMappingKey":
            dest_tags = [val for val in tag["Value"].split(" ") if val]
            logger.info(f"Found DestinationMappingKey: {dest_tags}")
            return dest_tags
    
    logger.warning(f"No DestinationMappingKey tag found on object {key}")
    return None
        
def get_key_mappings(destination_map_key):
    """Get destination bucket mappings from Parameter Store"""
    logger.info(f"Looking up mappings for keys: {destination_map_key}")
    
    parameter_prefix = "/pipeline/destination"
    bucket_list = []
    
    for key in destination_map_key:
        try:
            parameter_name = f"{parameter_prefix}/{key}"
            logger.debug(f"Getting parameter: {parameter_name}")
            
            response = ssm_client.get_parameter(Name=parameter_name)
            buckets = response['Parameter']['Value'].replace(" ", "").split(",")
            bucket_list.extend([bucket for bucket in buckets if bucket])
            
            logger.info(f"Found {len(buckets)} buckets for key '{key}': {buckets}")
            
        except ClientError as e:
            if e.response['Error']['Code'] == 'ParameterNotFound':
                logger.error(f"Parameter not found: {parameter_name}")
                raise ValueError(f"No mapping found for key: {key}")
            else:
                logger.error(f"Error getting parameter {parameter_name}: {e}")
                raise
    
    logger.info(f"Total destination buckets found: {len(bucket_list)}")
    return bucket_list

def copy_single_file(source_bucket, key, dest_bucket):
    """Copy a single file using download/upload to ensure completion"""
    logger.debug(f"Copying {key} from {source_bucket} to {dest_bucket}")
    
    import tempfile
    
    try:
        # Download to temporary file
        with tempfile.NamedTemporaryFile() as temp_file:
            s3_client.download_file(source_bucket, key, temp_file.name)
            
            # Upload to destination
            s3_client.upload_file(temp_file.name, dest_bucket, key)
        
        logger.debug(f"Successfully copied {key} to {dest_bucket}")
        
    except ClientError as e:
        error_code = e.response['Error']['Code']
        logger.error(f"Failed to copy {key} to {dest_bucket}: {error_code} - {e.response['Error']['Message']}")
        raise

def delete_source_file(bucket, key):
    """Delete the source file after successful transfer"""
    logger.info(f"Deleting source file {key} from bucket {bucket}")
    
    try:
        s3_client.delete_object(Bucket=bucket, Key=key)
        logger.info(f"Successfully deleted {key} from {bucket}")
    except ClientError as e:
        logger.error(f"Failed to delete {key} from {bucket}: {e}")
        raise

def send_failure_notification(bucket, key, failed_buckets, success_count, total_count):
    """Send SNS notification for transfer failures"""
    topic_arn = os.environ.get('SNS_TOPIC_ARN')
    if not topic_arn:
        logger.error("SNS_TOPIC_ARN environment variable not set")
        return
    
    subject = f"One-to-Many Transfer Failure: {key}"
    message = f"""Transfer failure for file: {key}
Source bucket: {bucket}
Successful transfers: {success_count}/{total_count}
Failed destination buckets: {', '.join(failed_buckets)}

Please investigate and retry the transfer manually if needed."""
    
    try:
        sns_client.publish(
            TopicArn=topic_arn,
            Subject=subject,
            Message=message
        )
        logger.info(f"Sent failure notification for {key}")
    except ClientError as e:
        logger.error(f"Failed to send SNS notification: {e}")
        raise

def copy_files(buckets, bucket, key):
    """Legacy function - kept for backward compatibility"""
    for dest_bucket in buckets:
        copy_single_file(bucket, key, dest_bucket)