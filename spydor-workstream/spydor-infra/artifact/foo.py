from aws_cdk import (
    Stack,
    aws_ec2 as ec2,
    aws_ecs as ecs,
    aws_ecs_patterns as ecs_patterns,
    aws_elasticloadbalancingv2 as elbv2,
    aws_rds as rds,
    aws_s3 as s3,
    aws_iam as iam,
    aws_route53 as route53,
    aws_certificatemanager as acm,
    RemovalPolicy,
    Duration,
    CfnOutput,
)
from constructs import Construct


class SpydorModernizedStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # Define VPC for the Tenant account
        self.tenant_vpc = ec2.Vpc(
            self, "SpydorTenantVpc",
            max_azs=2,
            subnet_configuration=[
                ec2.SubnetConfiguration(
                    name="Public",
                    subnet_type=ec2.SubnetType.PUBLIC,
                    cidr_mask=24
                ),
                ec2.SubnetConfiguration(
                    name="Application",
                    subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS,
                    cidr_mask=24
                ),
                ec2.SubnetConfiguration(
                    name="Database",
                    subnet_type=ec2.SubnetType.PRIVATE_ISOLATED,
                    cidr_mask=24
                )
            ]
        )

        # Create security groups
        alb_security_group = ec2.SecurityGroup(
            self, "AlbSecurityGroup",
            vpc=self.tenant_vpc,
            description="Security group for the application load balancer"
        )
        
        app_security_group = ec2.SecurityGroup(
            self, "AppSecurityGroup",
            vpc=self.tenant_vpc,
            description="Security group for the Tomcat container"
        )
        
        db_security_group = ec2.SecurityGroup(
            self, "DbSecurityGroup",
            vpc=self.tenant_vpc,
            description="Security group for Oracle RDS instances"
        )
        
        # Configure security group rules
        alb_security_group.add_ingress_rule(
            ec2.Peer.any_ipv4(),
            ec2.Port.tcp(443),
            "Allow HTTPS traffic from anywhere"
        )
        
        app_security_group.add_ingress_rule(
            alb_security_group,
            ec2.Port.tcp(8080),
            "Allow traffic from ALB to Tomcat"
        )
        
        db_security_group.add_ingress_rule(
            app_security_group,
            ec2.Port.tcp(1521),
            "Allow Oracle traffic from application"
        )
        
        # Create ECS Cluster
        cluster = ecs.Cluster(
            self, "SpydorFargateCluster",
            vpc=self.tenant_vpc,
            container_insights=True
        )
        
        # Create Oracle RDS instances (primary and standby)
        oracle_engine = rds.DatabaseInstanceEngine.oracle(
            version=rds.OracleEngineVersion.VER_19_0_0_0_2021_04_R1
        )
        
        parameter_group = rds.ParameterGroup(
            self, "OracleParameterGroup",
            engine=oracle_engine,
            parameters={
                "nls_length_semantics": "CHAR"
            }
        )
        
        oracle_primary = rds.DatabaseInstance(
            self, "OraclePrimaryInstance",
            engine=oracle_engine,
            instance_type=ec2.InstanceType.of(
                ec2.InstanceClass.BURSTABLE3, 
                ec2.InstanceSize.LARGE
            ),
            vpc=self.tenant_vpc,
            vpc_subnets=ec2.SubnetSelection(
                subnet_type=ec2.SubnetType.PRIVATE_ISOLATED,
                one_per_az=True
            ),
            multi_az=True,
            allocated_storage=100,
            max_allocated_storage=500,
            storage_type=rds.StorageType.GP2,
            backup_retention=Duration.days(7),
            deletion_protection=True,
            parameter_group=parameter_group,
            security_groups=[db_security_group],
            credentials=rds.Credentials.from_generated_secret("oracleadmin"),
            removal_policy=RemovalPolicy.SNAPSHOT
        )
        
        # S3 Buckets for DAF CloudWorks logs and Mission Data Store
        daf_log_bucket = s3.Bucket(
            self, "DafLogBucket",
            encryption=s3.BucketEncryption.S3_MANAGED,
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            removal_policy=RemovalPolicy.RETAIN,
            lifecycle_rules=[
                s3.LifecycleRule(
                    transitions=[
                        s3.Transition(
                            storage_class=s3.StorageClass.INFREQUENT_ACCESS,
                            transition_after=Duration.days(90)
                        ),
                        s3.Transition(
                            storage_class=s3.StorageClass.GLACIER,
                            transition_after=Duration.days(180)
                        )
                    ]
                )
            ]
        )
        
        mission_data_bucket = s3.Bucket(
            self, "MissionDataBucket",
            encryption=s3.BucketEncryption.S3_MANAGED,
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            removal_policy=RemovalPolicy.RETAIN,
            versioned=True,
        )
        
        # Create Task Definition for Tomcat container
        task_execution_role = iam.Role(
            self, "TaskExecutionRole",
            assumed_by=iam.ServicePrincipal("ecs-tasks.amazonaws.com")
        )
        
        task_role = iam.Role(
            self, "TaskRole",
            assumed_by=iam.ServicePrincipal("ecs-tasks.amazonaws.com")
        )
        
        # Add permissions to access S3 buckets and RDS Oracle
        daf_log_bucket.grant_read_write(task_role)
        mission_data_bucket.grant_read_write(task_role)
        
        task_definition = ecs.FargateTaskDefinition(
            self, "SpydorTaskDefinition",
            memory_limit_mib=4096,
            cpu=2048,
            execution_role=task_execution_role,
            task_role=task_role
        )
        
        container = task_definition.add_container(
            "TomcatContainer",
            image=ecs.ContainerImage.from_registry("apache/tomcat:9.0"),
            logging=ecs.LogDrivers.aws_logs(stream_prefix="spydor-container"),
            environment={
                "JAVA_OPTS": "-Xms2g -Xmx2g -Doracle.jdbc.timezoneAsRegion=false",
                "DB_HOST": oracle_primary.db_instance_endpoint_address,
                "DB_PORT": "1521",
                "DB_NAME": "SPYDORDB",
                "S3_DAF_LOG_BUCKET": daf_log_bucket.bucket_name,
                "S3_MISSION_DATA_BUCKET": mission_data_bucket.bucket_name
            },
            secrets={
                "DB_USER": ecs.Secret.from_secrets_manager(oracle_primary.secret, "username"),
                "DB_PASSWORD": ecs.Secret.from_secrets_manager(oracle_primary.secret, "password")
            }
        )
        
        container.add_port_mappings(
            ecs.PortMapping(container_port=8080, protocol=ecs.Protocol.TCP)
        )
        
        # Create ALB Service
        fargate_service = ecs_patterns.ApplicationLoadBalancedFargateService(
            self, "SpydorService",
            cluster=cluster,
            task_definition=task_definition,
            desired_count=2,
            security_groups=[app_security_group],
            public_load_balancer=True,
            listener_port=443,
            assign_public_ip=False,
            vpc_subnets=ec2.SubnetSelection(
                subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS
            ),
            load_balancer_name="spydor-alb",
            security_group=alb_security_group,
            platform_version=ecs.FargatePlatformVersion.VERSION1_4,
            capacity_provider_strategies=[
                ecs.CapacityProviderStrategy(
                    capacity_provider="FARGATE",
                    weight=1
                )
            ],
            circuit_breaker=ecs.DeploymentCircuitBreaker(rollback=True)
        )
        
        # Configure health check
        fargate_service.target_group.configure_health_check(
            path="/health",
            healthy_http_codes="200",
            interval=Duration.seconds(30),
            timeout=Duration.seconds(10),
            healthy_threshold_count=2,
            unhealthy_threshold_count=3
        )
        
        # Auto scaling for the Fargate service
        scaling = fargate_service.service.auto_scale_task_count(
            max_capacity=6,
            min_capacity=2
        )
        
        scaling.scale_on_cpu_utilization(
            "CpuScaling",
            target_utilization_percent=70,
            scale_in_cooldown=Duration.seconds(300),
            scale_out_cooldown=Duration.seconds(60)
        )
        
        scaling.scale_on_memory_utilization(
            "MemoryScaling",
            target_utilization_percent=75,
            scale_in_cooldown=Duration.seconds(300),
            scale_out_cooldown=Duration.seconds(60)
        )
        
        # VPC Peering with Transit Gateway Account
        # Note: For TGW integration, you would need cross-account references
        # or use custom resources to set this up properly
        
        # Outputs
        CfnOutput(self, "LoadBalancerDNS",
                 value=fargate_service.load_balancer.load_balancer_dns_name)
        CfnOutput(self, "OraclePrimaryEndpoint",
                 value=oracle_primary.db_instance_endpoint_address)
        CfnOutput(self, "DafLogBucketName",
                 value=daf_log_bucket.bucket_name)
        CfnOutput(self, "MissionDataBucketName",
                 value=mission_data_bucket.bucket_name)
