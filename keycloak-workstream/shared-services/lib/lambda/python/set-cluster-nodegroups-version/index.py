import os
import boto3
import logging

from typing import TYPE_CHECKING, TypedDict

if TYPE_CHECKING:
    from mypy_boto3_eks import EKSClient
    from mypy_boto3_ec2 import EC2Client


else:
    EKSClient = object
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


class Event(TypedDict):
    REGION: str
    CLUSTER_NAME: str


def get_ec2_client(region: str) -> EC2Client:
    return boto3.Session().client("ec2", region_name=region)


def get_eks_client(region: str) -> EKSClient:
    return boto3.Session().client("eks", region_name=region)


def handler(event: Event, context):
    # Get the region from the event
    region = event.get("REGION", "us-west-1")

    ec2_client = get_ec2_client(region=region)

    # Get a list of EKS clusters
    eks_client = get_eks_client(region=region)
    clusters = eks_client.list_clusters()["clusters"]
    logging.info(f"Found {len(clusters)} EKS clusters in Region: {region}")

    # check if the cluster exists
    cluster_name = event.get("CLUSTER_NAME")
    if cluster_name not in clusters:
        logging.error(f"Cluster {cluster_name} not found")
        return

    logging.info(f"Updating nodes in cluster {cluster_name}")

    # Get all managed nodes from cluster
    managed_nodes = eks_client.list_nodegroups(clusterName=cluster_name)["nodegroups"]
    logging.info(f"Found {len(managed_nodes)} managed node groups in cluster {cluster_name}")

    # Update all managed nodes to the latest version
    for node in managed_nodes:

        logging.info(f"Updating managed node group: {node}")
        # Check if node is using custom ami
        node_info = eks_client.describe_nodegroup(clusterName=cluster_name, nodegroupName=node)["nodegroup"]

        try:
            if node_info["amiType"] == "CUSTOM":
                logging.info(f"Node {node} is using a custom AMI. Updating using Latest Launch Template")

                # Get launch template name
                launch_template_name = node_info["launchTemplate"]["name"]
                launch_template_id = node_info["launchTemplate"]["id"]

                # Get current version of the launch template
                current_launch_template_version = int(node_info["launchTemplate"]["version"])

                # Get the latest version of the launch template using ec2 client
                latest_launch_template_version = ec2_client.describe_launch_template_versions(
                    LaunchTemplateId=launch_template_id,
                    Versions=["$Latest"],
                )["LaunchTemplateVersions"][0]["VersionNumber"]

                logging.info(f"Current Launch Template Version: {current_launch_template_version}")
                logging.info(f"Latest Launch Template Version: {latest_launch_template_version}")

                if current_launch_template_version == latest_launch_template_version:

                    logging.info(f"Managed Node Group: {node} is already using the latest Launch Template version")
                else:
                    logging.info(f"Updating Managed Node Group: {node} using Latest Launch Template")

                    # Update node managed with the latest version of the launch template
                    eks_client.update_nodegroup_version(
                        clusterName=cluster_name,
                        nodegroupName=node,
                        force=True,
                        launchTemplate={
                            "name": launch_template_name,
                            "version": "$Latest",
                        },
                    )

            else:
                logging.info(f"Updating Managed Node Group: {node} using default AMI")

                eks_client.update_nodegroup_version(
                    clusterName=cluster_name,
                    nodegroupName=node,
                    force=True,
                )

        except Exception as error:
            logging.error(f"Error updating node {node}: {error}")


# Simple Test
handler(
    event={
        "CLUSTER_NAME": "WhiteCluster",
        "REGION": "us-west-1",
    },
    context="",
)
