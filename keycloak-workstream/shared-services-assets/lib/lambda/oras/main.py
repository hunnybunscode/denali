import json, subprocess, os, logging, boto3, base64, tempfile

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

temp_directory = tempfile.TemporaryDirectory()

os.environ["PATH"] = "/opt/awscli:/opt/kubectl:/opt/helm:" + os.environ["PATH"]


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

    region = os.environ.get("AWS_REGION")

    # Check region is defined, if not defined, throw error
    if not region:
        raise Exception("AWS_REGION environment variable is not defined")

    payload = event
    logger.info(f"Payload: {payload}")
    logger.info(f"Region: {region}")
    logger.info(f"Current Working Directory: ${os.getcwd()}")

    source_bucket = payload.get("SOURCE_BUCKET") or ""
    source_key = payload.get("SOURCE_KEY") or ""
    destination_repository = payload.get("DESTINATION_REPOSITORY") or ""
    destination_repository_uri = os.path.dirname(destination_repository)

    local_destination_path = os.path.abspath(os.path.join(temp_directory, source_key))
    local_destination_directory = os.path.dirname(local_destination_path)

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

        # Get login to ECR with oras
        oras_login_cmd = [
            "oras",
            "login",
            "--username",
            username,
            "--password-stdin",
            destination_repository_uri,
        ]

        file_name = os.path.basename(local_destination_path)
        container_name = os.path.basename(destination_repository)
        container_tag = os.path.splitext(file_name.split("__")[1])[0]

        logger.info(f"Container name: {container_name}")

        # Extract tarball to container name folder
        if not os.path.exists(f"{local_destination_directory}/{container_name}"):
            os.makedirs(f"{local_destination_directory}/{container_name}", exist_ok=True)

        subprocess.run(["tar", "-xvf", local_destination_path, "-C", f"{local_destination_directory}/{container_name}"])

        # Run oras push to target repository
        # oras_push_cmd = [
        #     "oras",
        #     "push",
        #     "--disable-path-validation",
        #     "--oci-layout"
        #     "--config", "manifest.json:application/vnd.docker.distribution.manifest.v2+json",
        #     "--artifact-type", "application/vnd.docker.container.image.v1+json",
        #     f"{destination_repository}:{container_tag}",
        #     local_destination_path,
        # ]

        oras_push_cmd = [
            "oras",
            "cp",
            "--verbose",
            "--from-oci-layout",
            local_destination_path,
            f"{destination_repository}:{container_tag}",
        ]

        logger.info("Run the 'oras login' command and capture its output")
        subprocess.run(oras_login_cmd, input=password, text=True)
        logger.info("Run the 'oras push' command and capture its output")
        subprocess.run(oras_push_cmd)

        # Docker login to ECR
        docker_login_cmd = [
            "docker",
            "login",
            "-u",
            username,
            "-p",
            password,
            destination_repository_uri,
        ]

        # Docker tag command
        docker_tag_cmd = [
            "docker",
            "tag",
            "ubuntu:latest",
            f"{destination_repository}:{container_tag}",
        ]

        # Docker push
        docker_push_cmd = [
            "docker",
            "push",
            f"{destination_repository}:{container_tag}",
        ]

        # Docker pull the uploaded image
        docker_pull_cmd = [
            "docker",
            "pull",
            f"{destination_repository}:{container_tag}",
        ]

        logger.info("Run the 'docker login' command and capture its output")
        subprocess.run(docker_login_cmd, text=True)

        # logger.info("Run the 'docker tag' command and capture its output")
        # subprocess.run(docker_tag_cmd)
        # logger.info("Run the 'docker push' command and capture its output")
        # subprocess.run(docker_push_cmd)

        logger.info("Run the 'docker pull' command and capture its output")
        subprocess.run(docker_pull_cmd)

    except Exception as e:
        logger.error("Error occurred: %s", e)
        return {"statusCode": 500, "body": str(e)}
    finally:
        logger.info("End Lambda function")

    return {"statusCode": 200, "body": json.dumps("Successful Lambda response")}


if __name__ == "__main__":
    logger.info("Start main test")
    event = {
        "SOURCE_BUCKET": "908027385618-us-east-1-local-assets",
        "SOURCE_KEY": "docker/cert-manager-cainjector__v1.17.2.tar",
        "CHART_NAME": "cert-manager-cainjector",
        "DESTINATION_REPOSITORY": "908027385618.dkr.ecr.us-east-1.amazonaws.com/cert-manager-cainjector",
    }
    lambda_handler(event, None)
