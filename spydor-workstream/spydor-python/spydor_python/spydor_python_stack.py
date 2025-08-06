from aws_cdk import (
    Stack,
    RemovalPolicy,
    aws_ec2 as ec2,
    aws_ecs as ecs,
    aws_efs as efs,
    aws_elasticloadbalancingv2 as elbv2,
    aws_rds as rds,
    aws_s3 as s3,
    aws_iam as iam,
)
from constructs import Construct

class SpydorPythonStack(Stack):

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # VPC Configuration
        spydor_infra_vpc = ec2.Vpc(
            self, "spydor_infra_vpc",
            max_azs=2,
            subnet_configuration=[
                ec2.SubnetConfiguration(
                    cidr_mask=24,
                    name="Public",
                    subnet_type=ec2.SubnetType.PUBLIC
                ),
                ec2.SubnetConfiguration(
                    cidr_mask=24,
                    name="Fargate",
                    subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS
                ),
                ec2.SubnetConfiguration(
                    cidr_mask=24,
                    name="Database",
                    subnet_type=ec2.SubnetType.PRIVATE_ISOLATED
                )
            ]
        )

        # Security Groups
        spydor_infra_alb_sg = ec2.SecurityGroup(
            self, "spydor_infra_alb_sg",
            vpc=spydor_infra_vpc,
            allow_all_outbound=True
        )
        spydor_infra_alb_sg.add_ingress_rule(ec2.Peer.any_ipv4(), ec2.Port.tcp(80))
        spydor_infra_alb_sg.add_ingress_rule(ec2.Peer.any_ipv4(), ec2.Port.tcp(443))

        spydor_infra_fargate_sg = ec2.SecurityGroup(
            self, "spydor_infra_fargate_sg",
            vpc=spydor_infra_vpc,
            allow_all_outbound=True
        )

        spydor_infra_database_sg = ec2.SecurityGroup(
            self, "spydor_infra_database_sg",
            vpc=spydor_infra_vpc,
            allow_all_outbound=False
        )

        spydor_infra_efs_sg = ec2.SecurityGroup(
            self, "spydor_infra_efs_sg",
            vpc=spydor_infra_vpc,
            allow_all_outbound=False
        )

        spydor_infra_fargate_sg.add_ingress_rule(spydor_infra_alb_sg, ec2.Port.tcp(8080))
        spydor_infra_database_sg.add_ingress_rule(spydor_infra_fargate_sg, ec2.Port.tcp(1521))
        spydor_infra_efs_sg.add_ingress_rule(spydor_infra_fargate_sg, ec2.Port.tcp(2049))

        # ECS Cluster
        spydor_infra_cluster = ecs.Cluster(
            self, "spydor_infra_cluster",
            vpc=spydor_infra_vpc
        )

        # S3 Buckets
        spydor_infra_logs_bucket = s3.Bucket(
            self, "spydor_infra_logs_bucket",
            removal_policy=RemovalPolicy.RETAIN,
            encryption=s3.BucketEncryption.S3_MANAGED,
            enforce_ssl=True
        )

        spydor_infra_mdl_bucket = s3.Bucket(
            self, "spydor_infra_mdl_bucket",
            removal_policy=RemovalPolicy.RETAIN,
            encryption=s3.BucketEncryption.S3_MANAGED,
            enforce_ssl=True
        )

        # EFS File System
        spydor_infra_efs = efs.FileSystem(
            self, "spydor_infra_efs",
            vpc=spydor_infra_vpc,
            encrypted=True,
            security_group=spydor_infra_efs_sg,
            vpc_subnets=ec2.SubnetSelection(subnet_group_name="Fargate"),
            removal_policy=RemovalPolicy.RETAIN
        )

        spydor_infra_efs.add_to_resource_policy(iam.PolicyStatement(
            effect=iam.Effect.ALLOW,
            principals=[iam.AnyPrincipal()],
            actions=[
                "elasticfilesystem:ClientMount",
                "elasticfilesystem:ClientWrite", 
                "elasticfilesystem:ClientRootAccess"
            ],
            resources=[spydor_infra_efs.file_system_arn],
            conditions={
                "Bool": {
                    "elasticfilesystem:AccessedViaMountTarget": "true"
                }
            }
        ))

        # RDS Database
        spydor_infra_db = rds.DatabaseInstance(
            self, "spydor_infra_db",
            engine=rds.DatabaseInstanceEngine.oracle_ee(
                version=rds.OracleEngineVersion.VER_19_0_0_0_2023_04_R1
            ),
            # Production DB should be the db.m5.large or bigger
            # instance_type=ec2.InstanceType.of(ec2.InstanceClass.M5, ec2.InstanceSize.LARGE),
            instance_type=ec2.InstanceType.of(ec2.InstanceClass.T3, ec2.InstanceSize.MEDIUM),
            vpc=spydor_infra_vpc,
            vpc_subnets=ec2.SubnetSelection(subnet_group_name="Database"),
            security_groups=[spydor_infra_database_sg],
            multi_az=True,
            # Must Retain for Production
            # removal_policy=RemovalPolicy.RETAIN
            removal_policy=RemovalPolicy.DESTROY
            
        )

        # Fargate Task Definition
        spydor_infra_fargate_task = ecs.FargateTaskDefinition(
            self, "spydor_infra_fargate_task",
            memory_limit_mib=512,
            cpu=256
        )

        spydor_infra_fargate_task.add_volume(
            name="efs-volume",
            efs_volume_configuration=ecs.EfsVolumeConfiguration(
                file_system_id=spydor_infra_efs.file_system_id
            )
        )

        container = spydor_infra_fargate_task.add_container(
            "spydor_infra_fargate_container",
            image=ecs.ContainerImage.from_registry("tomcat:9.0"),
            port_mappings=[ecs.PortMapping(container_port=8080)]
        )

        container.add_mount_points(ecs.MountPoint(
            source_volume="efs-volume",
            container_path="/mnt/efs",
            read_only=False
        ))

        # Application Load Balancer
        spydor_infra_alb = elbv2.ApplicationLoadBalancer(
            self, "spydor_infra_alb",
            vpc=spydor_infra_vpc,
            internet_facing=True,
            security_group=spydor_infra_alb_sg,
            vpc_subnets=ec2.SubnetSelection(subnet_type=ec2.SubnetType.PUBLIC)
        )

        # Fargate Service
        spydor_infra_fargate_service = ecs.FargateService(
            self, "spydor_infra_fargate_service",
            cluster=spydor_infra_cluster,
            task_definition=spydor_infra_fargate_task,
            security_groups=[spydor_infra_fargate_sg],
            vpc_subnets=ec2.SubnetSelection(subnet_group_name="Fargate")
        )

        # Target Group and Listener
        target_group = elbv2.ApplicationTargetGroup(
            self, "spydor_target_group",
            vpc=spydor_infra_vpc,
            port=8080,
            targets=[spydor_infra_fargate_service]
        )

        target_group.configure_health_check(
            path="/",
            healthy_http_codes="404"
        )

        spydor_infra_alb.add_listener(
            "spydor_listener",
            port=80,
            default_target_groups=[target_group]
        )
