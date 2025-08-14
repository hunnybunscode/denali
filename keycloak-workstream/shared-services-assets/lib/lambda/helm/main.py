import json, subprocess, os, logging, boto3, base64

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from mypy_boto3_s3 import S3Client, S3ServiceResource
    from mypy_boto3_ecr import ECRClient

else:
    S3Client = object
    S3ServiceResource = object
    ECRClient = object

# Initialize the log configuration
logging.basicConfig(level=logging.INFO, force=True)

# Retrieve the logger instance
logger = logging.getLogger()

os.environ["PATH"] = "/opt/awscli:/opt/kubectl:/opt/helm:" + os.environ["PATH"]
os.environ["KUBECONFIG"] = kubeconfig = "/tmp/kubeconfig"
os.environ["HELM_CONFIG_HOME"] = helm_config_home = "/tmp/helm/.config"


def get_ecr_client(region: str) -> ECRClient:
    return boto3.Session().client("ecr", region_name=region)


def get_s3_client() -> S3Client:
    return boto3.Session().client("s3")


def get_s3_resource() -> S3ServiceResource:
    return boto3.resource("s3")


def lambda_handler(event, context):
    print("Start Lambda function")

    logger.info("---Received event:\n%s", event)

    logger.info("\n---Received context:\n%s", context)

    region = os.environ.get("AWS_REGION") or "us-west-1"

    payload = event
    logger.info(f"Payload: {payload}")
    logger.info(f"Region: {region}")
    logger.info(f"Current Working Directory: ${os.getcwd()}")

    source_bucket = payload.get("SOURCE_BUCKET") or ""
    source_key = payload.get("SOURCE_KEY") or ""
    destination_repository = payload.get("DESTINATION_REPOSITORY") or ""
    destination_repository_uri = os.path.dirname(destination_repository)

    local_destination_path = os.path.abspath(os.path.join("/tmp", source_key))
    local_destination_directory = os.path.dirname(local_destination_path)

    if not os.path.exists(os.path.dirname(helm_config_home)):
        os.makedirs(os.path.dirname(helm_config_home), exist_ok=True)

    try:
        # Run the df -h command and capture its output
        result = subprocess.run(["df", "-h"], stdout=subprocess.PIPE, text=True)
        logger.info(f"Output of 'df -h':\n{result.stdout}")

        # Run the 'ls' command and capture its output
        result = subprocess.run(["ls", "-l"], stdout=subprocess.PIPE, text=True)
        logger.info(f"Output of 'ls -l':\n{result.stdout}")

        logger.info(f"Download file from S3: s3://{source_bucket}/{source_key}")
        logger.info(f"Local file path: {local_destination_path}")

        # Check local destination folder path exist, create directories if missing
        if not os.path.exists(local_destination_directory):
            os.makedirs(local_destination_directory, exist_ok=True)

        # Download the file from S3
        s3_client = get_s3_client()
        s3_client.download_file(Bucket=source_bucket, Key=source_key, Filename=local_destination_path)

        # Check file exists
        if not os.path.exists(local_destination_path):
            raise Exception(f"File not found: {local_destination_path}")

        # Get the login of ECR
        ecr_client = get_ecr_client(region)
        token = ecr_client.get_authorization_token()

        # Decode the authorization token to extract username and password
        username, password = base64.b64decode(token["authorizationData"][0]["authorizationToken"]).decode().split(":")

        # Get login to ECR with Helm
        helm_login_cmd = [
            "helm",
            "registry",
            "login",
            "--username",
            username,
            "--password-stdin",
            destination_repository_uri,
        ]

        # Run helm push to target repository
        helm_push_cmd = [
            "helm",
            "push",
            local_destination_path,
            f"oci://{destination_repository_uri}",
        ]

        logger.info("Run the 'helm login' command and capture its output")
        subprocess.run(helm_login_cmd, input=password, text=True)

        logger.info("Run the 'helm push' command and capture its output")
        subprocess.run(helm_push_cmd)

    except Exception as e:
        logger.error("Error occurred: %s", e)
        return {"statusCode": 500, "body": str(e)}
    finally:
        logger.info("End Lambda function")

    return {"statusCode": 200, "body": json.dumps("Successful Lambda response")}


if __name__ == "__main__":
    logger.info("Start main test")
    event = {
        "SOURCE_BUCKET": "654654446198-us-west-1-local-assets",
        "SOURCE_KEY": "helm/cluster-autoscaler/cluster-autoscaler-9.36.0.tgz",
        "CHART_NAME": "cluster-autoscaler",
        "DESTINATION_REPOSITORY": "654654446198.dkr.ecr.us-west-1.amazonaws.com/cluster-autoscaler",
    }
    lambda_handler(event, None)
