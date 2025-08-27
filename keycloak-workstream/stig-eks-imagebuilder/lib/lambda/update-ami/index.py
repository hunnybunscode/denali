import os
import json
import logging
import boto3


from typing import TYPE_CHECKING, TypedDict

if TYPE_CHECKING:
    from mypy_boto3_ssm import SSMClient
    from mypy_boto3_ec2 import EC2Client


else:
    SSMClient = object
    EC2Client = object

LOG_LEVELS = {
    "DEBUG": logging.DEBUG,
    "INFO": logging.INFO,
    "WARNING": logging.WARNING,
    "ERROR": logging.ERROR,
    "CRITICAL": logging.CRITICAL,
}


# Fetch Debugging level based from ENVIRONMENT Variable DEBUG_LEVEL
DEBUG_LEVEL = os.environ.get("DEBUG_LEVEL")

LOG_LEVEL = LOG_LEVELS.get(DEBUG_LEVEL, logging.INFO)
logging.basicConfig(level=LOG_LEVEL, force=True)


def get_ec2_client() -> EC2Client:
    return boto3.Session().client("ec2")


def get_ssm_client() -> SSMClient:
    return boto3.Session().client("ssm")


class Event(TypedDict):
    pipeline_name: str
    ami_filters: dict[str, str]


def lambda_handler(event: Event, context):
    logging.info(f"Event: {event}")
    logging.info(f"Context: {context}")

    ssm = get_ssm_client()
    ec2 = get_ec2_client()

    pipeline_name = event["pipeline_name"]
    ami_filters = event["ami_filters"]

    # Get the current AWS region running this lambda function
    region = boto3.Session().region_name

    logging.info(f"Pipeline: {pipeline_name}")
    logging.info(f"AMI Filters: {ami_filters}")
    logging.info(f"Region: {region}")

    # Get latest AMI
    try:
        response = ec2.describe_images(
            Filters=[{"Name": key, "Values": [value]} for key, value in ami_filters.items()],
        )
    except Exception as exception:
        logging.error(f"Failed to describe images with filters: {ami_filters}. Error: {exception}")
        raise exception

    if not response["Images"]:
        raise Exception(f"No AMI found with filters: {ami_filters}")

    latest_ami = sorted(response["Images"], key=lambda x: x["CreationDate"])[-1]["ImageId"]
    logging.info(f"Found AMI: {latest_ami}")

    # Update SSM parameter
    param_name = f"/image-builder/{pipeline_name}/target-ami-image-id"
    try:
        ssm.put_parameter(Name=param_name, Value=latest_ami, Overwrite=True)
    except Exception as exception:
        logging.error(f"Failed to update SSM parameter {param_name} with value {latest_ami}. Error: {exception}")
        raise exception

    return {
        "statusCode": 200,
        "body": json.dumps({"pipeline": pipeline_name, "updated_ami": latest_ami, "parameter": param_name}),
    }


# Check if running main
if __name__ == "__main__":
    event = {
        "pipeline_name": "amazon-eks-node-al2023-x86_64-standard-1_30-stig-high",
        "ami_filters": {"name": "amazon-eks-node-al2023-x86_64-standard-1.30-*", "architecture": "x86_64"},
    }
    print(lambda_handler(event, None))
