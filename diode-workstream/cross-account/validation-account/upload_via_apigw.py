# References:
# https://github.com/aws-samples/sigv4-signing-examples/blob/main/sdk/python/main.py
# https://github.com/boto/botocore/blob/develop/botocore/auth.py
# https://boto3.amazonaws.com/v1/documentation/api/latest/guide/s3-presigned-urls.html
#
###################################################################################
#
# 1. Pre-requisites
#
# a. Python 3.11 (or higher)
#
# For example:
# Linux: yum install python3.11
# Windows: https://www.python.org/downloads/release/python-3110/
#
# b. boto3 and requests library
#
# For example:
# Linux: python3.11 -m pip install boto3 requests
# Windows: py -3.11 -m pip install boto3 requests
#
# 2. Set environment variables (see further down)
#
# 3. Run the following command for help
#
# For example:
# Linux: python3.11 <name_of_script> -h
# Windows: py -3.11 <name_of_script> -h
#
###################################################################################
import argparse
import os
import sys
from pathlib import Path

import boto3  # type: ignore
import requests  # type: ignore
from botocore.auth import SigV4Auth  # type: ignore
from botocore.awsrequest import AWSRequest  # type: ignore


###################################################################################
# -----------------     Set these environment variables     -----------------
# For example:
# Bash: export AWS_ACCESS_KEY_ID="abcdefg"
# PowerShell: $Env:AWS_ACCESS_KEY_ID="abcdefg"

ACCESS_KEY = os.getenv("AWS_ACCESS_KEY_ID")
SECRET_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")
# Set this if using temporary credentials
SESSION_TOKEN = os.getenv("AWS_SESSION_TOKEN")
# (Optional) Defaults to us-gov-west-1, if not set
REGION = os.getenv("AWS_DEFAULT_REGION", "us-gov-west-1")
# For example: "https://abcdef.execute-api.us-gov-west-1.amazonaws.com/prod/upload"
INVOKE_URL = os.getenv("INVOKE_URL")

###################################################################################


def main(bucket_name: str, key_name: str, prefix: str, filepath: str, credentials):
    method = "POST"
    service = "execute-api"

    validate_invoke_url()
    params = dict(bucket=bucket_name, key=prefix + key_name)
    request = AWSRequest(method, INVOKE_URL, params=params)
    SigV4Auth(credentials, service, REGION).add_auth(request)
    presigned_url = get_presigned_post_url(method, request, params)
    upload_file(presigned_url, filepath, params)


def validate_invoke_url():
    if not INVOKE_URL:
        print(
            "ERROR: INVOKE_URL must be set as an environment variable. For example: "
            "https://abcdef.execute-api.us-gov-west-1.amazonaws.com/prod/upload",
        )
        sys.exit(1)


def get_credentials():
    if not (ACCESS_KEY and SECRET_KEY):
        raise ValueError(
            "AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY must be set as environment variables",  # noqa: E501
        )

    session_config = dict(
        aws_access_key_id=ACCESS_KEY,
        aws_secret_access_key=SECRET_KEY,
        region_name=REGION,
    )

    # If using temporary credentials
    if ACCESS_KEY.startswith("ASIA"):
        if not SESSION_TOKEN:
            raise ValueError(
                "AWS_SESSION_TOKEN must be set as an environment variable",  # noqa: E501
            )

        session_config["aws_session_token"] = SESSION_TOKEN

    session = boto3.Session(**session_config)
    return session.get_credentials()


def get_presigned_post_url(method: str, request, params: dict):
    try:
        response = requests.request(
            method,
            INVOKE_URL,
            headers=dict(request.headers),
            params=params,
            timeout=10,
        )
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"Could not get presigned post url: {e}")
        raise


def upload_file(presigned_url: dict, file_path: str, params: dict):
    with open(file_path, "rb") as f:
        files = {"file": (file_path, f)}
        response = requests.post(
            presigned_url["url"],
            data=presigned_url["fields"],
            files=files,
            timeout=300,  # Adjust this as necessary
        )

    try:
        # Successful HTTP status code is 204
        response.raise_for_status()
        print(f"SUCCESS: {file_path} uploaded to {params['bucket']}/{params['key']}")
    except Exception as e:
        print(f"Could not upload file: {e}")


def get_resolved_file_path(path: Path):
    """
    Returns the resolved file path
    """
    return str(path.resolve())


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Gets a pre-signed URL from the specified API Gateway endpoint and uploads a file to a bucket",  # noqa: E501
        allow_abbrev=False,
    )

    parser.add_argument(
        "--bucket",
        type=str,
        help="Specify the name of a bucket to which you want to upload a file",
    )

    parser.add_argument(
        "--filepath",
        type=str,
        help="Specify the path of a file to upload",
    )

    parser.add_argument(
        "--prefix",
        type=str,
        default="",
        help="(Optional) Specify the prefix to append to the file. Defaults to an empty string",  # noqa: E501
    )

    args = parser.parse_args()

    path = Path(args.filepath)
    filepath = get_resolved_file_path(path)
    prefix: str = args.prefix.strip()
    if prefix:
        prefix = "/".join([part for part in prefix.split("/") if part]) + "/"

    try:
        credentials = get_credentials()
    except Exception as e:
        print(f"ERROR: {e}")
        sys.exit(1)

    main(
        bucket_name=args.bucket,
        key_name=path.name,
        prefix=prefix,
        filepath=filepath,
        credentials=credentials,
    )
