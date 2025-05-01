from os import path, environ
import boto3
from aws_cdk import (
    aws_ec2 as ec2,
    aws_iam as iam,
    aws_lambda as _lambda,
    aws_logs as logs,
    aws_s3 as s3,
    aws_s3_notifications as s3n,

    BundlingOptions,
    CfnOutput,
    CfnParameter,
    DockerVolume,
    Duration,
    RemovalPolicy,
    Stack,
)
from constructs import Construct
from typing import Optional, Sequence

REGION=environ.get("AWS_REGION", environ.get("AWS_DEFAULT_REGION"))

DEVELOPMENT=eval(environ.get("DEVELOPMENT", "False"))

if DEVELOPMENT:
    ssm_client = boto3.client("ssm", region_name=REGION)

def get_parameter(key, default=None, *, decrypt=False):
    """Return the SSM parameter if it exists, otherwise `None`"""
    val = default
    try:
        resp = ssm_client.get_parameter(Name=key, WithDecryption=decrypt)
        val = resp["Parameter"]["Value"]
    except Exception as e:
        if DEVELOPMENT:
            print(f"SSM::GetParameter for [{key}] returned {e}. Continuing...")
    return val

class DaffodilConversionStack(Stack):

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)
        
        self.iam_prefix = CfnParameter(self, "IamPrefix", type="String", default="None", min_length=2,
            description="The customer prefix to be used for IAM policies.")  # noqa: E501
        permissions_boundary = CfnParameter(self, "PermissionsBoundaryPolicyArn", type="String", min_length=1,
            description="The arn for permissions boundary.")  # noqa: E501
        self.permissions_boundary = iam.ManagedPolicy.from_managed_policy_arn(
            self, "PermissionsBoundary", permissions_boundary.value_as_string)  # noqa: E501
        
        self.lambda_endpoint = "lambda.amazonaws.com"

        lambda_basic_execution_roles = [
            iam.ManagedPolicy.from_aws_managed_policy_name(
                "service-role/AWSLambdaBasicExecutionRole",
            ),
            iam.ManagedPolicy.from_aws_managed_policy_name(
                "service-role/AWSLambdaVPCAccessExecutionRole",
            ),
        ]
        self.parser_role = self.__create_daffodil_parser_role(managed_policies=lambda_basic_execution_roles)

        self.default_bucket_options = {
            "encryption": s3.BucketEncryption.KMS_MANAGED,
            "enforce_ssl": True,
            "access_control": s3.BucketAccessControl.PRIVATE,
            "object_ownership": s3.ObjectOwnership.BUCKET_OWNER_ENFORCED,
            "block_public_access": s3.BlockPublicAccess.BLOCK_ALL,
            "versioned": True,
            "lifecycle_rules": [s3.LifecycleRule(
                abort_incomplete_multipart_upload_after=Duration.days(1),
            )]
        }

        input_bucket_name = CfnParameter(self, "InputBucket",
            description="The name of the Amazon S3 bucket where files to be processed by daffodil will be stored.")
        self.input_bucket = s3.Bucket.from_bucket_name(self, "inputBucket",
            bucket_name=input_bucket_name.value_as_string)

        output_bucket_name = CfnParameter(self, "OutputBucket",
            description="The name of the Amazon S3 bucket where successful daffodil transformed "
            "files will be stored.")
        self.output_bucket = s3.Bucket.from_bucket_name(self, "outputBucket",
            bucket_name=output_bucket_name.value_as_string)

        vpc_subnet_ids = CfnParameter(
            self, "VpcSubnetIDs",
            default=get_parameter("/platform/networking/vpc/default/subnet/private") if DEVELOPMENT else None,
            type="List<AWS::EC2::Subnet::Id>",
            description="The list of private subnet IDs to use for the daffodil pipeline"
        )

        vpc_id = CfnParameter(
            self, "VpcId",
            default=None,
            type="AWS::EC2::VPC::Id",
            description="ID of the VPC to put the compute resource in",
        )
        
        namespace = CfnParameter(self, "Namespace", default=environ.get("NAMESPACE", ""),
            description="The optional namespace to deploy to if deploying multiple stacks to the "
            "same account. (Resource Suffix)")
        
        sns_error_topic_arn = CfnParameter(
            self, "SnsErrorTopicArn", default="",
            description="The optional ARN of the SNS topic to send error notifications to."
        )
        
        enable_detailed_metrics = CfnParameter(self, "EnableDetailedMetrics",
            allowed_values=["true", "false"], default="false",
            description="Whether or not the more detailed custom CloudFormation metrics are enabled.")
        
        # proxy = CfnParameter(
        #     self, "Proxy",
        #     default=environ.get("PROXY", "") if DEVELOPMENT else "",
        #     description="The optional proxy to use for the parser")
        
        # no_proxy = CfnParameter(
        #     self, "NoProxy",
        #     default=environ.get("NO_PROXY", "") if DEVELOPMENT else "",
        #     description="The optional no-proxy to use for the parser")
        
        parser_filter_suffix = CfnParameter(
            self, "ParserFilterSuffix",
            default=None,
            description="Optional - File suffix filter(s) as a comma-separated-value to apply to the "
            "Bucket event listener. If no filter prefix is provided, all files will be sent to the "
            "daffodil parser.",
        )
        
        self.schema_bucket = self.optional_bucket_from_context_param("schema-bucket")

        self.archive_bucket_name = CfnParameter(
            self, "ArchiveBucket",
            default=None,
            description="Optional - The name of the Amazon S3 bucket where original files will be "
                "moved to from the Input Bucket after succesful daffodil transformation. If no "
                "name is supplied, successful transformed files will just be deleted from the "
                "Input Bucket.")

        # self.dead_letter_bucket = self.optional_bucket_from_context_param("dead-letter-bucket")
        dead_letter_bucket_name = CfnParameter(self, "DeadLetterBucket",
            description="Optional - The name of the Amazon S3 bucket where failed daffodil "
            "transformation will be stored. If no bucket name is provided, failed daffodil "
            "transformation files will remain in the Input Bucket")
        self.dead_letter_bucket = s3.Bucket.from_bucket_name(self, "deadLetterBucket",
            bucket_name=dead_letter_bucket_name.value_as_string)

        # Default to create precompile function unless context parameter for schema-bucket is given
        # to allow for dev running multiple stacks using the same schema bucket (only one can
        # have a bucket notification listner on it)
        self.create_precompile_fn = self.node.try_get_context("schema-bucket") is None

        # cond_proxy_exist=CfnCondition(
        #     self, "ProxyExistsCondition",
        #     expression=Fn.condition_not(Fn.condition_equals(proxy, '')))
        # proxy_value = Fn.condition_if(
        #     cond_proxy_exist.logical_id, proxy.value_as_string, Aws.NO_VALUE).to_string()

        # cond_no_proxy_exist=CfnCondition(
        #     self, "NoProxyExistsCondition",
        #     expression=Fn.condition_not(Fn.condition_equals(no_proxy, '')))
        # no_proxy_value = Fn.condition_if(
        #     cond_no_proxy_exist.logical_id, no_proxy.value_as_string, Aws.NO_VALUE).to_string()
        # proxy_env = {
        #     "HTTPS_PROXY": proxy_value,
        #     "HTTP_PROXY": proxy_value,
        #     "https_proxy": proxy_value,
        #     "http_proxy": proxy_value,
        #     "NO_PROXY": no_proxy_value,
        #     "no_proxy": no_proxy_value,
        # }

        content_types_file_key = CfnParameter(self, "ContentTypeFileKey", default="content-types.yaml",
            description="content-type file mapping s3 key, defaults to content-types.yaml")
        
        if DEVELOPMENT:
            parser_code = _lambda.Code.from_asset(
                "./daffodil_conversion/assets/lambda/java/",
                bundling=self.get_bundling_options('parser')
            )
            precompiler_code = _lambda.Code.from_asset(
                "./daffodil_conversion/assets/lambda/java/",
                bundling=self.get_bundling_options('precompiler')
            )
        else:
            lambda_code_bucket_param = CfnParameter(self, "LambdaCodeBucket",
                description="The name of the Amazon S3 bucket where uploaded code will be stored.")
            code_bucket = s3.Bucket.from_bucket_name(self, "codeBucket",
                bucket_name=lambda_code_bucket_param.value_as_string)
            
            parser_lambda_code_param = CfnParameter(self, 'ParserLambdaCodeKey',
                default="parser.jar",
                description="The S3 key of the parser code in the code bucket (including prefixes).")
            
            precompiler_lambda_code_param = CfnParameter(self, 'PrecompilerLambdaCodeKey',
                default="precompiler.jar",
                description="The S3 key of the precompiler code in the code bucket (including prefixes)")
            
            parser_code = _lambda.Code.from_bucket(
                bucket=code_bucket,
                key=parser_lambda_code_param.value_as_string,
            )

            precompiler_code = _lambda.Code.from_bucket(
                bucket=code_bucket,
                key=precompiler_lambda_code_param.value_as_string,
            )

        self.template_options.metadata = {
            'AWS::CloudFormation::Interface': {
                'ParameterGroups': [
                    {
                        'Label': { 'default': 'General'},
                        'Parameters': [
                            self.iam_prefix.logical_id,
                            permissions_boundary.logical_id,
                            namespace.logical_id,
                        ]
                    },
                    {
                        'Label': { 'default': 'Templates Location'},
                        'Parameters': [
                            lambda_code_bucket_param.logical_id,
                            parser_lambda_code_param.logical_id,
                            precompiler_lambda_code_param.logical_id,
                        ]
                    },
                    {
                        'Label': { 'default': 'Networking'},
                        'Parameters': [
                            vpc_id.logical_id,
                            vpc_subnet_ids.logical_id,
                        ]
                    },
                    {
                        'Label': { 'default': 'Daffodil Stack'},
                        'Parameters': [
                            input_bucket_name.logical_id,
                            output_bucket_name.logical_id,
                            self.archive_bucket_name.logical_id,
                            dead_letter_bucket_name.logical_id,
                            sns_error_topic_arn.logical_id,
                            content_types_file_key.logical_id,
                            enable_detailed_metrics.logical_id,
                            parser_filter_suffix.logical_id,
                        ]
                    },
                ],
                'ParameterLabels': {
                    self.iam_prefix.logical_id: {'default': 'IAM Prefix'},
                    permissions_boundary.logical_id: {'default': 'Permissions Boundary Policy ARN'},
                    namespace.logical_id: {'default': 'Namespace (Resource Suffix)'},
                    lambda_code_bucket_param.logical_id: {'default': 'Template Bucket Name'},
                    parser_lambda_code_param.logical_id: {'default': 'Parser Lambda Key'},
                    precompiler_lambda_code_param.logical_id: {'default': 'Precompiler Lambda Key'},
                    vpc_id.logical_id: {'default': 'VPC ID'},
                    vpc_subnet_ids.logical_id: {'default': 'Private Subnet IDs within the VPC'},
                    input_bucket_name.logical_id: {'default': 'Input Bucket'},
                    output_bucket_name.logical_id: {'default': 'Output Bucket (Data Transfer Bucket)'},
                    self.archive_bucket_name.logical_id: {'default': 'Archive Bucket'},
                    dead_letter_bucket_name.logical_id: {'default': 'Dead Letter Bucket (Invalid Files Bucket)'},
                    sns_error_topic_arn.logical_id: {'default': 'Invalid Files Topic ARN'},
                    content_types_file_key.logical_id: {'default': 'Content Types File S3 Key'},
                    enable_detailed_metrics.logical_id: {'default': 'Enable Detailed Performance Metrics'},
                    parser_filter_suffix.logical_id: {'default': 'Parser Filter S3 Key Suffix(es)'},
                },
            }
        }

        lambda_security_group = ec2.CfnSecurityGroup(
            self, "DfdlLambdaSecurityGroup",
            group_description="Security Group for Daffodil Lambda instances",
            security_group_egress=[ec2.CfnSecurityGroup.EgressProperty(
                cidr_ip="0.0.0.0/0",
                ip_protocol="tcp",
                from_port=443,
                to_port=443,
                description="Allow HTTPS traffic out to everywhere"
            )],
            vpc_id=vpc_id.value_as_string,
        )

        parser_log_group = logs.LogGroup(
            self, "DfdlParserLogGroup",
            removal_policy=RemovalPolicy.DESTROY,
            retention=logs.RetentionDays.ONE_WEEK,
        )

        environment={
            "OUTPUT_BUCKET": self.output_bucket.bucket_name,
            "SCHEMA_BUCKET": self.schema_bucket.bucket_name,
            "DEAD_LETTER_BUCKET": self.dead_letter_bucket.bucket_name,
            "CONTENT_TYPES_FILE": content_types_file_key.value_as_string,
            "NAMESPACE": namespace.value_as_string,
            "ENABLE_DETAILED_METRICS": enable_detailed_metrics.value_as_string,
            "SNS_ERROR_TOPIC_ARN": sns_error_topic_arn.value_as_string,
            # **proxy_env,
        }
        if self.archive_bucket_name and self.archive_bucket_name.value_as_string:
            environment["ARCHIVE_BUCKET"] = self.archive_bucket_name.value_as_string

        self.parser_fn = _lambda.Function(
            self, "DfdlParser",
            role=self.parser_role,
            runtime=_lambda.Runtime.JAVA_11,
            code=parser_code,
            handler="daffodil.conversion.App",
            memory_size=5120,
            timeout=Duration.seconds(30),
            log_group=parser_log_group,
            environment=environment,
        )
        self.parser_fn.node.default_child.vpc_config=_lambda.CfnFunction.VpcConfigProperty(
            security_group_ids=[lambda_security_group.attr_group_id],
            subnet_ids=vpc_subnet_ids.value_as_list,
        )

        filters = []
        if parser_filter_suffix and parser_filter_suffix.value_as_string:
            for suffix in parser_filter_suffix.value_as_string.split(","):
                filters.append(s3.NotificationKeyFilter(suffix=suffix.strip()))
        self.input_bucket.add_event_notification(
            s3.EventType.OBJECT_CREATED,
            s3n.LambdaDestination(self.parser_fn),
            *filters
        )

        precompiler_log_group = logs.LogGroup(
            self, "DfdlPrecompilerLogGroup",
            removal_policy=RemovalPolicy.DESTROY,
            retention=logs.RetentionDays.ONE_WEEK,
        )

        if self.create_precompile_fn:
            self.precompiler_fn = _lambda.Function(
                self, "precompiler",
                role=self.parser_role,
                runtime=_lambda.Runtime.JAVA_11,
                code=precompiler_code,
                handler="daffodil.precompile.App",
                memory_size=1024,
                timeout=Duration.seconds(30),
                log_group=precompiler_log_group,
                environment={
                    # **proxy_env,
                }
            )
            self.precompiler_fn.node.default_child.vpc_config=_lambda.CfnFunction.VpcConfigProperty(
                security_group_ids=[lambda_security_group.attr_group_id],
                subnet_ids=vpc_subnet_ids.value_as_list,
            )
            self.schema_bucket.add_event_notification(
                s3.EventType.OBJECT_CREATED,
                s3n.LambdaDestination(self.precompiler_fn),
                s3.NotificationKeyFilter(suffix=".dfdl.xsd")
            )

    def get_bundling_options(self, module_name) -> BundlingOptions:
        return BundlingOptions(
            command = [
                '/bin/sh',
                '-c',
                f'cd {module_name} && mvn clean install && cp /asset-input/{module_name}/target/{module_name}.jar /asset-output/'
            ],
            image = _lambda.Runtime.JAVA_11.bundling_image,
            volumes = [
                # Mount local .m2 repo to avoid download all the dependencies again inside the container
                DockerVolume(
                    host_path=path.expanduser("~/.m2/"),
                    container_path=("/root/.m2/")
                )
            ],
            user='root',
        )
    
    def optional_bucket_from_context_param(self,
            param_name: str,
            default_bucket_options: Optional[any] = None,
        ) -> s3.Bucket:
        default_bucket_options = default_bucket_options if default_bucket_options is not None else self.default_bucket_options
        bucket_name = self.node.try_get_context(param_name)
        bucket = s3.Bucket.from_bucket_name(self, param_name, bucket_name=bucket_name) if bucket_name is not None else s3.Bucket(self, param_name, **default_bucket_options)
        CfnOutput(self, f"o{param_name}", value=bucket.bucket_name)
        return bucket
    
    def __create_daffodil_parser_role(self, *, managed_policies: Sequence[iam.IManagedPolicy]):
        role = iam.Role(
            self,
            "DaffodilParserRole",
            assumed_by=iam.ServicePrincipal(self.lambda_endpoint),
            role_name=f"{self.iam_prefix.value_as_string}_Daffodil_Parser_Role",  # noqa: E501
            managed_policies=managed_policies,
            permissions_boundary=self.permissions_boundary,
        )
        role.add_managed_policy(
            policy=iam.ManagedPolicy(
                self,
                "DaffodilParserPolicy",
                managed_policy_name=f"{self.iam_prefix.value_as_string}_DaffodilParserPolicy",  # noqa: E501
                document=iam.PolicyDocument(
                    statements=[
                        iam.PolicyStatement(
                            effect=iam.Effect.ALLOW,
                            actions=[
                                "s3:AbortMultipartUpload",
                                "s3:GetObject",
                                "s3:GetObjectTagging",
                                "s3:HeadObject",
                                "s3:PutObject",
                                "s3:PutObjectTagging",
                                "s3:DeleteObject",
                                "s3:ListBucket",
                            ],
                            resources=[f"arn:{self.partition}:s3:::*"],
                        ),
                        iam.PolicyStatement(
                            effect=iam.Effect.ALLOW,
                            actions=[
                                "kms:Decrypt",
                                "kms:GenerateDataKey*"
                            ],
                            resources=["*"],
                        ),
                        iam.PolicyStatement(
                            effect=iam.Effect.ALLOW,
                            actions=[
                                "sns:Publish",
                            ],
                            resources=[f"arn:{self.partition}:sns:{self.region}:{self.account}:*"],
                        ),
                    ]
                ),
            )
        )
        CfnOutput(self, "oDaffodilParserRoleArn", value=role.role_arn)
        return role
