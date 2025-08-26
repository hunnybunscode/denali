from aws_cdk import (
    aws_stepfunctions as sfn,
    aws_stepfunctions_tasks as tasks,
    aws_lambda as _lambda,
    aws_ssm as ssm,
    aws_iam as iam,
    aws_ec2 as ec2,
    Duration,
    Stack
)

from aws_cdk.aws_stepfunctions import DefinitionBody 
from constructs import Construct
from config.config import Config

class RemediationStepFunction(Construct):
    def __init__(self, scope: Construct, id: str, config: Config):
        super().__init__(scope, id)

        def add_secrets_manager_permissions(lambda_function):
            lambda_function.add_to_role_policy(iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "secretsmanager:GetSecretValue",
                    "secretsmanager:DescribeSecret"
                ],
                resources=["arn:aws-us-gov:secretsmanager:us-gov-west-1:354049455466:secret:gitea/api/token-GAvBPY"]
            ))

            lambda_function.add_to_role_policy(iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=["secretsmanager:ListSecrets"],
                resources=["*"]
            ))

        self.vpc = ec2.Vpc.from_lookup(
            self,
            "denali-poc-vpc",
            vpc_id=config.networking.vpc_id
        )
        
        self.subnet_selection = ec2.SubnetSelection(
            subnets=[
                ec2.Subnet.from_subnet_id(
                    self, 
                    f"denali-poc-private-subnet-{i}", 
                    subnet_id=subnet.subnet_id
                ) for i, subnet in enumerate(config.networking.subnets)
            ]
        )

        self.security_group = ec2.SecurityGroup.from_security_group_id(
            self, 
            "LambdaSecurityGroup", 
            config.networking.security_group_id
        )

        # Define Lambda Functions
        git_grab_file = _lambda.Function(self, f"{config.namespace}-{config.version}-GitGrabFile",
            runtime=_lambda.Runtime.PYTHON_3_9,
            handler="index.lambda_handler",
            code=_lambda.Code.from_asset("stacks/step_functions_stack/lambdas/git_grab_file"),
            timeout=Duration.minutes(5),
            function_name=f"{config.namespace}-{config.version}-GitGrabFile",
            vpc=self.vpc,
            vpc_subnets=self.subnet_selection,
            security_groups=[self.security_group]
        )

        git_grab_file.add_to_role_policy(iam.PolicyStatement(
            effect=iam.Effect.ALLOW,
            actions=[
                "secretsmanager:GetSecretValue",
                "secretsmanager:DescribeSecret"
            ],
            resources=["arn:aws-us-gov:secretsmanager:us-gov-west-1:354049455466:secret:gitea/api/token-GAvBPY"]
        ))

        git_grab_file.add_to_role_policy(iam.PolicyStatement(
            effect=iam.Effect.ALLOW,
            actions=[
                "secretsmanager:ListSecrets"
            ],
            resources=["*"]
        ))

        code_remediation_bedrock = _lambda.Function(self, f"{config.namespace}-{config.version}-CodeRemediationBedrock",
            runtime=_lambda.Runtime.PYTHON_3_9,
            handler="index.lambda_handler",
            code=_lambda.Code.from_asset("stacks/step_functions_stack/lambdas/code_remediation_bedrock"),
            timeout=Duration.minutes(5),
            function_name=f"{config.namespace}-{config.version}-CodeRemediationBedrock",
            vpc=self.vpc,
            vpc_subnets=self.subnet_selection,
            security_groups=[self.security_group]
        )

        code_remediation_bedrock.add_to_role_policy(iam.PolicyStatement(
            effect=iam.Effect.ALLOW,
            actions=[
                "bedrock:InvokeModel",
                "bedrock:ListFoundationModels"
            ],
            resources=[
                "arn:aws-us-gov:bedrock:us-gov-west-1::foundation-model/anthropic.claude-3-5-sonnet-20240620-v1:0"
            ]
        ))


        git_branch_crud = _lambda.Function(self, f"{config.namespace}-{config.version}-GitBranchCRUD",
            runtime=_lambda.Runtime.PYTHON_3_9,
            handler="index.lambda_handler",
            code=_lambda.Code.from_asset("stacks/step_functions_stack/lambdas/git_branch_crud"),
            timeout=Duration.minutes(5),
            function_name=f"{config.namespace}-{config.version}-GitBranchCRUD",
            vpc=self.vpc,
            vpc_subnets=self.subnet_selection,
            security_groups=[self.security_group]
        )

        add_secrets_manager_permissions(git_branch_crud)

        git_issues_crud = _lambda.Function(self, f"{config.namespace}-{config.version}-GitIssuesCRUD",
            runtime=_lambda.Runtime.PYTHON_3_9,
            handler="index.lambda_handler",
            code=_lambda.Code.from_asset("stacks/step_functions_stack/lambdas/git_issues_crud"),
            timeout=Duration.minutes(5),
            function_name=f"{config.namespace}-{config.version}-GitIssuesCRUD",
            vpc=self.vpc,
            vpc_subnets=self.subnet_selection,
            security_groups=[self.security_group]
        )

        add_secrets_manager_permissions(git_issues_crud)

        git_code_merge = _lambda.Function(self, f"{config.namespace}-{config.version}-GitCodeMerge",
            runtime=_lambda.Runtime.PYTHON_3_9,
            handler="index.lambda_handler",
            code=_lambda.Code.from_asset("stacks/step_functions_stack/lambdas/git_code_merge"),
            timeout=Duration.minutes(5),
            function_name=f"{config.namespace}-{config.version}-GitCodeMerge",
            vpc=self.vpc,
            vpc_subnets=self.subnet_selection,
            security_groups=[self.security_group]
        )

        add_secrets_manager_permissions(git_code_merge)

        verify_findings_resolved = _lambda.Function(self, f"{config.namespace}-{config.version}-VerifyFindingsResolved",
            runtime=_lambda.Runtime.PYTHON_3_9,
            handler="index.lambda_handler",
            code=_lambda.Code.from_asset("stacks/step_functions_stack/lambdas/verify_findings_resolved"),
            function_name=f"{config.namespace}-{config.version}-VerifyFindingsResolved",
            vpc=self.vpc,
            vpc_subnets=self.subnet_selection,
            security_groups=[self.security_group]
        )

        git_pr_crud = _lambda.Function(self, f"{config.namespace}-{config.version}-GitPRCRUD",
            runtime=_lambda.Runtime.PYTHON_3_9,
            handler="index.lambda_handler",
            code=_lambda.Code.from_asset("stacks/step_functions_stack/lambdas/git_pr_crud"),
            timeout=Duration.minutes(5),
            function_name=f"{config.namespace}-{config.version}-GitPRCRUD",
            vpc=self.vpc,
            vpc_subnets=self.subnet_selection,
            security_groups=[self.security_group]
        )

        add_secrets_manager_permissions(git_pr_crud)

        # Define standard Lambda retry props
        lambda_retry_props = {
            "errors": [
                "Lambda.ServiceException",
                "Lambda.AWSLambdaException",
                "Lambda.SdkClientException",
                "Lambda.TooManyRequestsException"
            ],
            "interval": Duration.seconds(1),
            "max_attempts": 3,
            "backoff_rate": 2
        }

        # Define states
        fail_state = sfn.Fail(
            self, "Fail",
            cause="Step Function execution failed"
        )

        wait_state = sfn.Wait(
            self, "Wait",
            time=sfn.WaitTime.duration(Duration.seconds(5))
        )

        # Define Tasks
        grab_file_task = tasks.LambdaInvoke(
            self, "Grab File Contents from Git",
            lambda_function=git_grab_file,
            retry_on_service_exceptions=True,
            output_path="$.Payload",
            payload=sfn.TaskInput.from_object({
                "repo_url.$": "$.original_input.codeRepo",
                "file_path.$": "$.fortify_finding.sourceFileRelative",
                "branch.$": "$.original_input.mainBranch",
                "secret_name": "gitea/api/token"
            })
        )

        fix_finding_task = tasks.LambdaInvoke(
            self, "Fix Finding with Claud3.5 Bedrock",
            lambda_function=code_remediation_bedrock,
            retry_on_service_exceptions=True,
            output_path="$.Payload",
            payload=sfn.TaskInput.from_object({
                "fortify_result.$": "$.fortify_finding",
                "file_content.$": "$.content"
            })
        )

        create_branch_code_repo = tasks.LambdaInvoke(
            self, "Create Branch in Code Repo",
            lambda_function=git_branch_crud,
            retry_on_service_exceptions=True,
            payload=sfn.TaskInput.from_object({
                "operation": "create",
                "repo_url.$": "$.input.codeRepo",
                "base_branch.$": "$.input.mainBranch",
                "branch_name.$": "$.llm_output.branchName",
                "secret_name.$": "$.input.secretName"
            })
        )

        create_branch_finding_repo = tasks.LambdaInvoke(
            self, "Create Branch in Finding Repo",
            lambda_function=git_branch_crud,
            retry_on_service_exceptions=True,
            payload=sfn.TaskInput.from_object({
                "operation": "create",
                "repo_url.$": "$.input.scanResultsRepo",
                "base_branch.$": "$.input.mainBranch",
                "branch_name.$": "$.llm_output.branchName",
                "secret_name.$": "$.input.secretName"
            })
        )

        delete_branches = tasks.LambdaInvoke(
            self, "Delete Branches",
            lambda_function=git_branch_crud,
            retry_on_service_exceptions=True,
            payload=sfn.TaskInput.from_object({
                "branches": [
                    {
                        "operation": "delete",
                        "repo_url.$": "$.input.codeRepo",
                        "branch_name.$": "$.llm_output.branchName",
                        "secret_name.$": "$.input.secretName"
                    },
                    {
                        "operation": "delete",
                        "repo_url.$": "$.input.scanResultsRepo",
                        "branch_name.$": "$.llm_output.branchName",
                        "secret_name.$": "$.input.secretName"
                    }
                ]
            })
        ).next(fail_state)

        create_issue = tasks.LambdaInvoke(
            self, "Create Issue for Finding Comments (Code Repo)",
            lambda_function=git_issues_crud,
            retry_on_service_exceptions=True,
            payload=sfn.TaskInput.from_object({
                "operation": "create",
                "repo_url.$": "$.input.codeRepo",
                "title.$": "$.llm_output.issueTitle",
                "body.$": "$.llm_output.issueBody",
                "labels.$": "$.llm_output.issueLabels",
                "branch.$": "$.llm_output.branchName",
                "secret_name.$": "$.input.secretName"
            })
        ).add_catch(delete_branches, errors=["States.ALL"])

        merge_and_push = tasks.LambdaInvoke(
            self, "Merge and Push Code",
            lambda_function=git_code_merge,
            retry_on_service_exceptions=True,
            payload=sfn.TaskInput.from_object({
                "repo_url.$": "$.input.codeRepo",
                "branch_name.$": "$.llm_output.branchName",
                "file_path.$": "$.fortify_finding.sourceFileRelative",
                "content.$": "$.llm_output.codeBody",
                "commit_message.$": "$.llm_output.commitMessage",
                "secret_name": "gitea/api/token"
            })
        ).add_catch(delete_branches, errors=["States.ALL"])

        run_fortify_scan = tasks.CallAwsService(
            self, "Run Fortify Scan on Instance & Push Results to Git",
            service="ssm",
            action="sendCommand",
            parameters={
                "DocumentName": sfn.JsonPath.string_at("$.input.scanDocumentName"),
                "InstanceIds.$": "$.input.fortifyScanInstanceID",  
                "Parameters": {
                    "BranchName.$": "$.llm_output.branchName"  
                }
            },
            iam_resources=["*"]
        ).add_catch(delete_branches, errors=["States.ALL"])

        modify_output = sfn.Pass(
            self, "Modify Output for Loop",
            parameters={
                "CommandId": sfn.JsonPath.string_at("$.Command.CommandId"),
                "InstanceId": sfn.JsonPath.string_at("$.Command.InstanceIds[0]")
            }
        )

        check_scan_complete = tasks.CallAwsService(
            self, "Check if Scan is Complete",
            service="ssm",
            action="getCommandInvocation",
            parameters={
                "CommandId": sfn.JsonPath.string_at("$.CommandId"),
                "InstanceId": sfn.JsonPath.string_at("$.InstanceId")
            },
            iam_resources=["*"]
        )

        verify_findings_resolved = tasks.LambdaInvoke(
            self, "Verify Findings Resolved",
            lambda_function=verify_findings_resolved,
            retry_on_service_exceptions=True
        ).add_catch(delete_branches, errors=["States.ALL"])

        create_pr = tasks.LambdaInvoke(
            self, "Create PR (Issues Resolved)",
            lambda_function=git_pr_crud,
            retry_on_service_exceptions=True,
            payload=sfn.TaskInput.from_object({
                "operation": "create",
                "repo_url.$": "$.input.codeRepo",
                "source_branch.$": "$.llm_output.branchName",
                "target_branch.$": "$.input.mainBranch",
                "title.$": "$.prTitle",
                "description.$": "$.prDescription",
                "labels": ["AI Fix"],
                "assignees": ["jakedlee"],
                "secret_name.$": "$.input.secretName"
            })
        )

        # Create parallel state
        parallel_state = sfn.Parallel(
            self, "Parallel"
        ).branch(create_branch_code_repo)\
         .branch(create_branch_finding_repo)

        # Define choice states
        branch_exists_choice = sfn.Choice(self, "Does Branch Exist?")
        is_false_positive_choice = sfn.Choice(self, "Is False Positive?")
        scan_status_choice = sfn.Choice(self, "Choice")

        # Chain everything together
        definition = grab_file_task\
            .next(fix_finding_task)\
            .next(branch_exists_choice)

        # Branch exists choice paths
        branch_exists_choice\
            .when(sfn.Condition.boolean_equals("$.branch_exists", False), parallel_state)\
            .otherwise(create_issue)

        # After parallel completes, both branches join back
        parallel_state.next(create_issue)

        # Rest of the chain
        create_issue.next(is_false_positive_choice)

        is_false_positive_choice\
            .when(sfn.Condition.string_equals("$.llm_output.parsed_sections.false_positive", "TRUE"), create_pr)\
            .otherwise(merge_and_push)

        merge_and_push.next(run_fortify_scan)
        run_fortify_scan.next(modify_output)
        modify_output.next(check_scan_complete)
        check_scan_complete.next(scan_status_choice)

        scan_status_choice\
            .when(sfn.Condition.string_equals("$.StatusDetails", "Success"), verify_findings_resolved)\
            .when(
                sfn.Condition.or_(
                    sfn.Condition.string_equals("$.StatusDetails", "InProgress"),
                    sfn.Condition.string_equals("$.StatusDetails", "Pending")
                ),
                wait_state
            )\
            .otherwise(fail_state)

        wait_state.next(check_scan_complete)
        verify_findings_resolved.next(create_pr)

        # Create State Machine
        self.state_machine = sfn.StateMachine(
            self, f"{config.namespace}-{config.version}-RemediationStateMachine",
            state_machine_name=f"{config.namespace}-{config.version}-DenaliPOC-Remediation-Test",
            definition_body=DefinitionBody.from_chainable(definition),
            timeout=Duration.minutes(30)
        )