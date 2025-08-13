import boto3
import json
import logging
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)

s3_client = boto3.client('s3')
ssm_client = boto3.client('ssm')

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
    """Copy a single file to a destination bucket"""
    logger.debug(f"Copying {key} from {source_bucket} to {dest_bucket}")
    
    try:
        response = s3_client.copy_object(
            CopySource={
                "Bucket": source_bucket,
                "Key": key
            },
            Bucket=dest_bucket,
            Key=key
        )
        
        status_code = response['ResponseMetadata']['HTTPStatusCode']
        if status_code != 200:
            raise RuntimeError(f"S3 copy failed with status code: {status_code}")
        
        logger.debug(f"Successfully copied {key} to {dest_bucket}")
        return response
        
    except ClientError as e:
        error_code = e.response['Error']['Code']
        logger.error(f"Failed to copy {key} to {dest_bucket}: {error_code} - {e.response['Error']['Message']}")
        raise

def copy_files(buckets, bucket, key):
    """Legacy function - kept for backward compatibility"""
    for dest_bucket in buckets:
        copy_single_file(bucket, key, dest_bucket)