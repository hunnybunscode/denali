import os
import json
import logging
import uuid
import boto3


from typing import TYPE_CHECKING, TypedDict

if TYPE_CHECKING:
    from mypy_boto3_imagebuilder import ImagebuilderClient


else:
    ImagebuilderClient = object


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


def get_imageBuilder_client() -> ImagebuilderClient:
    return boto3.Session().client("imagebuilder")


class Event(TypedDict):
    image_pipeline_arn: str


def lambda_handler(event: Event, context):
    logging.info(f"Event: {event}")
    logging.info(f"Context: {context}")

    image_builder = get_imageBuilder_client()

    image_pipeline_arn = event["image_pipeline_arn"]

    # Generate a UUID for the Client Token
    client_token = uuid.uuid4()

    # Get the current AWS region running this lambda function
    region = boto3.Session().region_name

    logging.info(f"Image Builder Pipeline ARN: {image_pipeline_arn}")
    logging.info(f"Client Token : {client_token}")
    logging.info(f"Region: {region}")

    try:
        response = image_builder.start_image_pipeline_execution(
            clientToken=str(client_token), imagePipelineArn=image_pipeline_arn
        )

        logging.info(f"Start Image pipeline execution: {response}")

    except Exception as exception:
        logging.error(f"Start Image pipeline execution Error: {exception}")
        raise exception

    return {
        "statusCode": 200,
        "body": json.dumps(
            {"ImagePipelineArn": image_pipeline_arn, "ClientToken": str(client_token), "Response": response}
        ),
    }


# Check if running main
if __name__ == "__main__":
    event = {
        "ImagePipelineArn": "arn:aws:imagebuilder:us-west-1:908027385618:image-pipeline/amazon-eks-node-rhel9-x86-64-standard-1-30-stig-high",
    }
    print(lambda_handler(event, None))
