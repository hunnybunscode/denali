from aws_cdk import (
    Stack,
    aws_lambda as _lambda,
    aws_iam as iam,
    aws_ec2 as ec2,
    Duration,
    BundlingOptions,
)
from constructs import Construct
from config.config import Config

class LambdaStack(Stack):

    def __init__(self, scope: Construct, construct_id: str, config: Config, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # Create Lambda execution role with AFC2S prefix and permissions boundary
        lambda_role = iam.Role(
            self,
            f"{config.permissions.role_prefix}-{config.namespace}-{config.version}-LambdaRole",
            role_name=f"{config.permissions.role_prefix}-{config.namespace}-{config.version}-LambdaRole",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name("service-role/AWSLambdaBasicExecutionRole"),
                iam.ManagedPolicy.from_aws_managed_policy_name("service-role/AWSLambdaVPCAccessExecutionRole")
            ],
            permissions_boundary=iam.ManagedPolicy.from_managed_policy_arn(
                self, "LambdaPermissionsBoundary",
                config.permissions.boundary_policy_arn
            )
        )

        # Add permissions for Lambda functions
        lambda_role.add_to_policy(iam.PolicyStatement(
            effect=iam.Effect.ALLOW,
            actions=[
                "dynamodb:*",
                "ssm:*",
                "secretsmanager:GetSecretValue",
                "bedrock:InvokeModel",
                "bedrock:InvokeModelWithResponseStream"
            ],
            resources=["*"]
        ))

        # Add Step Functions permissions for nested executions
        lambda_role.add_to_policy(iam.PolicyStatement(
            effect=iam.Effect.ALLOW,
            actions=[
                "states:StartExecution",
                "states:DescribeExecution",
                "states:StopExecution"
            ],
            resources=["*"]
        ))

        # Create Lambda layer with requests package
        requests_layer = _lambda.LayerVersion(
            self,
            f"{config.namespace}-{config.version}-RequestsLayer",
            code=_lambda.Code.from_asset(
                "layers/requests",
                bundling=BundlingOptions(
                    image=_lambda.Runtime.PYTHON_3_9.bundling_image,
                    command=[
                        "bash", "-c",
                        "pip install requests -t /asset-output/python && cp -r /asset-input/* /asset-output/"
                    ]
                )
            ),
            compatible_runtimes=[_lambda.Runtime.PYTHON_3_9],
            description="Layer containing requests package"
        )

        # Lookup VPC and networking resources once
        vpc = ec2.Vpc.from_lookup(self, "VPC", vpc_id=config.networking.vpc_id)
        subnets = [
            ec2.Subnet.from_subnet_id(self, f"Subnet{i}", subnet.subnet_id)
            for i, subnet in enumerate(config.networking.subnets)
        ]
        security_group = ec2.SecurityGroup.from_security_group_id(
            self, "SecurityGroup", config.networking.security_group_id
        )

        # Create Lambda functions with actual code
        lambda_configs = {
            config.lambda_functions.git_branch_crud: "stacks/step_functions_stack/lambdas/git_branch_crud",
            config.lambda_functions.git_issues_crud: "stacks/step_functions_stack/lambdas/git_issues_crud",
            config.lambda_functions.git_code_merge_and_push: "stacks/step_functions_stack/lambdas/git_code_merge",
            config.lambda_functions.create_dynamodb_table: "stacks/step_functions_stack/lambdas/create_dynamodb_table",
            config.lambda_functions.parse_fortify_findings: "stacks/step_functions_stack/lambdas/parse_fortify_findings_dynamodb",
            config.lambda_functions.dynamodb_table_scan: "stacks/step_functions_stack/lambdas/dynamodb_table_scan",
            config.lambda_functions.bedrock_llm_call: "stacks/step_functions_stack/lambdas/code_remediation_bedrock",
            config.lambda_functions.git_file_crud: "stacks/step_functions_stack/lambdas/git_grab_file",
            config.lambda_functions.verify_findings_resolved: "stacks/step_functions_stack/lambdas/verify_findings_resolved",
            config.lambda_functions.git_pr_crud: "stacks/step_functions_stack/lambdas/git_pr_crud"
        }

        for func_name, code_path in lambda_configs.items():
            _lambda.Function(
                self,
                f"{config.namespace}-{config.version}-{func_name}",
                runtime=_lambda.Runtime.PYTHON_3_9,
                handler="index.lambda_handler",
                code=_lambda.Code.from_asset(code_path),
                function_name=f"{config.namespace}-{config.version}-{func_name}",
                role=lambda_role,
                timeout=Duration.minutes(15),
                layers=[requests_layer],
                vpc=vpc,
                vpc_subnets=ec2.SubnetSelection(subnets=subnets),
                security_groups=[security_group]
            )