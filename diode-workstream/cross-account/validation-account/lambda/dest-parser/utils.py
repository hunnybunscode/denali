import boto3
import json



s3_client = boto3.client('s3')

def get_dest_tag(bucket, key):
    response = s3_client.get_object_tagging(
        Bucket=bucket,
        Key=key
    )
    tagset = response["TagSet"]
    for tag in tagset:
        if tag["Key"] == "DestinationMappingKey":
            dest_tags =[ val for val in tag["Value"].split(" ") if val]
            return dest_tags
        
def get_key_mappings(destination_map_key):
    ssm_client = boto3.client('ssm')
    parameter_prefix = "/pipeline/destination"
    bucket_list = [
        bucket
        for key in destination_map_key
        for bucket in ssm_client.get_parameter(Name=f"{parameter_prefix}/{key}")['Parameter']['Value'].replace(" ", "").split(",")
    ]
    return bucket_list

def copy_files(buckets, bucket, key):
    for dest_bucket in buckets:
        response = s3_client.copy_object(
            CopySource = {
                "Bucket": bucket,
                "Key": key
                },
            Bucket = dest_bucket,
            Key = key
            )
        status_code = response['ResponseMetadata']['HTTPStatusCode']
        if response['ResponseMetadata']['HTTPStatusCode'] != 200:
            print(f"Error copying file {key} to {dest_bucket}")
            print(f"StatusCode: {response['ResponseMetadata']['HTTPStatusCode']}")
        else:
            print(f"File {key} copied to {dest_bucket} --> StatusCode = {status_code}")