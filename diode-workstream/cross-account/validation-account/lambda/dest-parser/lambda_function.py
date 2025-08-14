import boto3
import json
import time
import logging
import os
from botocore.exceptions import ClientError
import utils

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Non-retryable error codes
NON_RETRYABLE_ERRORS = {
    'AccessDenied', 'Forbidden', 'InvalidAccessKeyId', 'SignatureDoesNotMatch',
    'TokenRefreshRequired', 'NoSuchBucket', 'NoSuchKey', 'ParameterNotFound'
}

def retry_with_backoff(func, max_retries=3, base_delay=1):
    """Retry function with exponential backoff for retryable errors"""
    for attempt in range(max_retries + 1):
        try:
            return func()
        except ClientError as e:
            error_code = e.response['Error']['Code']
            
            if error_code in NON_RETRYABLE_ERRORS or attempt == max_retries:
                logger.error(f"Non-retryable error or max retries reached: {error_code}")
                raise
            
            delay = base_delay * (2 ** attempt)
            logger.warning(f"Retryable error {error_code}, attempt {attempt + 1}/{max_retries + 1}, retrying in {delay}s")
            time.sleep(delay)
        except Exception as e:
            logger.error(f"Unexpected error: {str(e)}")
            raise

def lambda_handler(event, context):
    try:

        bucket = event['Records'][0]['s3']['bucket']['name']
        key = event['Records'][0]['s3']['object']['key']
        
        logger.info(f"Processing file {key} from bucket {bucket}")
        
        # Get destination mapping key with retry
        destination_map_key = retry_with_backoff(
            lambda: utils.get_dest_tag(bucket, key)
        )
        
        if not destination_map_key:
            logger.error(f"No DestinationMappingKey tag found for {key}")
            raise ValueError("Missing DestinationMappingKey tag")
        
        # Get bucket mappings with retry
        buckets = retry_with_backoff(
            lambda: utils.get_key_mappings(destination_map_key)
        )
        
        if not buckets:
            logger.error(f"No destination buckets found for mapping keys: {destination_map_key}")
            raise ValueError("No destination buckets configured")
        
        logger.info(f"Found {len(buckets)} destination buckets: {buckets}")
        
        # Copy files with individual error handling
        success_count = 0
        failed_buckets = []
        
        for dest_bucket in buckets:
            try:
                retry_with_backoff(
                    lambda: utils.copy_single_file(bucket, key, dest_bucket)
                )
                success_count += 1
                logger.info(f"Successfully copied {key} to {dest_bucket}")
            except Exception as e:
                logger.error(f"Failed to copy {key} to {dest_bucket}: {str(e)}")
                failed_buckets.append(dest_bucket)
        
        # Log summary
        logger.info(f"Copy operation completed: {success_count}/{len(buckets)} successful")
        
        if success_count == len(buckets):
            # All transfers successful - delete original file
            try:
                retry_with_backoff(
                    lambda: utils.delete_source_file(bucket, key)
                )
                logger.info(f"Successfully deleted source file {key} from {bucket}")
            except Exception as e:
                logger.error(f"Failed to delete source file {key}: {str(e)}")
                # Don't fail the entire process if delete fails
        else:
            # Some transfers failed - send SNS notification
            logger.error(f"Failed to copy to buckets: {failed_buckets}")
            try:
                retry_with_backoff(
                    lambda: utils.send_failure_notification(bucket, key, failed_buckets, success_count, len(buckets))
                )
            except Exception as e:
                logger.error(f"Failed to send SNS notification: {str(e)}")
            
            if success_count == 0:
                raise RuntimeError("Failed to copy file to any destination bucket")
        
    except Exception as e:
        logger.error(f"Error processing file {event.get('Records', [{}])[0].get('s3', {}).get('object', {}).get('key', 'unknown')}: {str(e)}")
        raise


