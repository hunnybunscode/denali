#!/usr/bin/env python3
"""
Validation Account Architecture Diagram
Generates an architecture diagram for the AFTAC validation account infrastructure
"""
from diagrams import Cluster
from diagrams import Diagram
from diagrams import Edge
from diagrams.aws.analytics import KinesisDataFirehose
from diagrams.aws.compute import EC2
from diagrams.aws.compute import Lambda
from diagrams.aws.integration import SNS
from diagrams.aws.integration import SQS
from diagrams.aws.management import Cloudwatch
from diagrams.aws.management import SystemsManager
from diagrams.aws.network import APIGateway
from diagrams.aws.network import InternetGateway
from diagrams.aws.network import NATGateway
from diagrams.aws.security import IAM
from diagrams.aws.security import SecretsManager
from diagrams.aws.storage import S3


def create_validation_architecture():
    with Diagram(
        "AFTAC Validation Account Architecture",
        filename="images/validation-account-architecture",
        show=False,
        direction="TB",
    ):

        # External connections
        with Cluster("External"):
            internet = InternetGateway("Internet Gateway")

        # VPC and networking
        with Cluster("VPC"):
            with Cluster("Public Subnets"):
                NATGateway("NAT Gateway")
                api_gw = APIGateway("API Gateway")

            with Cluster("Private Subnets"):
                # EC2 instances for validation
                ec2_validation = EC2("Validation EC2")
                EC2("Image Builder")

                # Lambda functions
                with Cluster("Lambda Functions"):
                    lambda_presigner = Lambda("Presigner")
                    lambda_dest_parser = Lambda("Dest Parser")
                    lambda_object_tagger = Lambda("Object Tagger")
                    lambda_transfer_result = Lambda("Transfer Result")

                # Storage
                with Cluster("Storage"):
                    s3_ingestion = S3("Ingestion Bucket")
                    s3_validated = S3("Validated Data")
                    s3_quarantine = S3("Quarantine Bucket")

                # Messaging
                sqs_queue = SQS("Validation Queue")
                sns_topic = SNS("Notifications")

                # Data processing
                kinesis_firehose = KinesisDataFirehose("Data Firehose")

                # Management services
                with Cluster("Management"):
                    cloudwatch = Cloudwatch("CloudWatch")
                    ssm = SystemsManager("Systems Manager")
                    secrets = SecretsManager("Secrets Manager")
                    iam = IAM("IAM Roles")

        # SFTP/File transfer
        with Cluster("File Transfer"):
            sftp_server = EC2("SFTP Server")

        # Connections
        internet >> api_gw >> lambda_presigner

        # Data flow
        api_gw >> s3_ingestion
        s3_ingestion >> Edge(label="Object Created") >> sqs_queue
        sqs_queue >> ec2_validation
        ec2_validation >> Edge(label="Validation Results") >> lambda_transfer_result

        # Validation process
        ec2_validation >> Edge(label="Clean Files") >> s3_validated
        ec2_validation >> Edge(label="Infected Files") >> s3_quarantine

        # Lambda interactions
        lambda_dest_parser >> s3_ingestion
        lambda_object_tagger >> s3_ingestion
        lambda_transfer_result >> sns_topic

        # Data pipeline
        s3_validated >> kinesis_firehose

        # SFTP flow
        sftp_server >> s3_ingestion

        # Monitoring and management
        ec2_validation >> cloudwatch
        lambda_presigner >> cloudwatch
        lambda_dest_parser >> cloudwatch
        lambda_object_tagger >> cloudwatch
        lambda_transfer_result >> cloudwatch

        ssm >> ec2_validation
        secrets >> ec2_validation
        iam >> [
            lambda_presigner,
            lambda_dest_parser,
            lambda_object_tagger,
            lambda_transfer_result,
            ec2_validation,
        ]


if __name__ == "__main__":
    create_validation_architecture()
    print("Architecture diagram generated: validation-account-architecture.png")
