import json
import os
import re
from aws_cdk import (
    Stack,
    aws_stepfunctions as sfn,
    aws_iam as iam,
)
from constructs import Construct
from config.config import Config
# from .step_functions.remediation_step_function import RemediationStepFunction
# from .step_functions.test_step_function import TestStepFunction

class StepFunctionsStack(Stack):

    def __init__(self, scope: Construct, construct_id: str, config: Config, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        with open('stacks/step_functions_stack/step_functions/json_definitions/remediation_step_function.json', 'r') as f:
            remediation_definition = json.load(f)

        # Replace hardcoded ARNs with dynamic values
        remediation_definition = self._replace_dynamic_values(remediation_definition, config)

        # Create the remediation step function from JSON definition
        # Create IAM role for the state machine with AFC2S prefix and permissions boundary
        state_machine_role = iam.Role(
            self,
            f"{config.permissions.role_prefix}-{config.namespace}-{config.version}-StepFunctionRole",
            role_name=f"{config.permissions.role_prefix}-{config.namespace}-{config.version}-StepFunctionRole",
            assumed_by=iam.ServicePrincipal("states.amazonaws.com"),
            permissions_boundary=iam.ManagedPolicy.from_managed_policy_arn(
                self, "StepFunctionPermissionsBoundary",
                config.permissions.boundary_policy_arn
            )
        )

        # Add specific permissions to the role
        state_machine_role.add_to_policy(iam.PolicyStatement(
            effect=iam.Effect.ALLOW,
            actions=[
                "lambda:InvokeFunction",
                "lambda:ListFunctions"
            ],
            resources=["*"]
        ))

        # Add permissions for Step Functions
        state_machine_role.add_to_policy(iam.PolicyStatement(
            effect=iam.Effect.ALLOW,
            actions=[
                "states:StartExecution",
                "states:DescribeExecution",
                "states:StopExecution"
            ],
            resources=["*"]
        ))

        # Add permissions for CloudWatch Logs
        state_machine_role.add_to_policy(iam.PolicyStatement(
            effect=iam.Effect.ALLOW,
            actions=[
                "logs:CreateLogDelivery",
                "logs:GetLogDelivery",
                "logs:UpdateLogDelivery",
                "logs:DeleteLogDelivery",
                "logs:ListLogDeliveries",
                "logs:PutResourcePolicy",
                "logs:DescribeResourcePolicies",
                "logs:DescribeLogGroups"
            ],
            resources=["*"]
        ))

        # Add permissions for EventBridge
        state_machine_role.add_to_policy(iam.PolicyStatement(
            effect=iam.Effect.ALLOW,
            actions=[
                "events:PutTargets",
                "events:PutRule",
                "events:DescribeRule"
            ],
            resources=["*"]
        ))

        # Add permissions for SSM
        state_machine_role.add_to_policy(iam.PolicyStatement(
            effect=iam.Effect.ALLOW,
            actions=[
                "ssm:SendCommand",
                "ssm:GetCommandInvocation"
            ],
            resources=["*"]
        ))

        # Add permissions for DynamoDB
        state_machine_role.add_to_policy(iam.PolicyStatement(
            effect=iam.Effect.ALLOW,
            actions=[
                "dynamodb:Scan",
                "dynamodb:GetItem",
                "dynamodb:PutItem",
                "dynamodb:UpdateItem",
                "dynamodb:DeleteItem",
                "dynamodb:DeleteTable"
            ],
            resources=["*"]
        ))

        remediation_sf = sfn.CfnStateMachine(
            self,
            f"{config.namespace}-{config.version}-RemediationStepFunction",
            definition_string=json.dumps(remediation_definition),
            role_arn=state_machine_role.role_arn,
        )

        # Load the test step function definition
        with open('stacks/step_functions_stack/step_functions/json_definitions/test_step_function.json', 'r') as f:
            test_definition = json.load(f)

        # Replace hardcoded ARNs with dynamic values
        test_definition = self._replace_dynamic_values(test_definition, config)

        # Create the test step function from JSON definition
        test_sf = sfn.CfnStateMachine(
            self,
            f"{config.namespace}-{config.version}-TestStepFunction",
            definition_string=json.dumps(test_definition),
            role_arn=state_machine_role.role_arn,
        )

    def _replace_dynamic_values(self, definition, config):
        """Replace template variables with config values"""
        definition_str = json.dumps(definition)

        # Replace template variables with namespaced function names
        namespace_prefix = f"{config.namespace}-{config.version}-"
        replacements = {
            '{{ACCOUNT_ID}}': self.account,
            '{{REGION}}': self.region,
            '{{GIT_BRANCH_CRUD}}': f"{namespace_prefix}{config.lambda_functions.git_branch_crud}",
            '{{GIT_ISSUES_CRUD}}': f"{namespace_prefix}{config.lambda_functions.git_issues_crud}",
            '{{GIT_CODE_MERGE_AND_PUSH}}': f"{namespace_prefix}{config.lambda_functions.git_code_merge_and_push}",
            '{{CREATE_DYNAMODB_TABLE}}': f"{namespace_prefix}{config.lambda_functions.create_dynamodb_table}",
            '{{PARSE_FORTIFY_FINDINGS}}': f"{namespace_prefix}{config.lambda_functions.parse_fortify_findings}",
            '{{DYNAMODB_TABLE_SCAN}}': f"{namespace_prefix}{config.lambda_functions.dynamodb_table_scan}",
            '{{BEDROCK_LLM_CALL}}': f"{namespace_prefix}{config.lambda_functions.bedrock_llm_call}",
            '{{GIT_FILE_CRUD}}': f"{namespace_prefix}{config.lambda_functions.git_file_crud}",
            '{{VERIFY_FINDINGS_RESOLVED}}': f"{namespace_prefix}{config.lambda_functions.verify_findings_resolved}",
            '{{GIT_PR_CRUD}}': f"{namespace_prefix}{config.lambda_functions.git_pr_crud}",
            '{{REMEDIATION_STATE_MACHINE}}': f"{namespace_prefix}{config.remediation_state_machine}"
        }

        for placeholder, value in replacements.items():
            definition_str = definition_str.replace(placeholder, value)

        return json.loads(definition_str)