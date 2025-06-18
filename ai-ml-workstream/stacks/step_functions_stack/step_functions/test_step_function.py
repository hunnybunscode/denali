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
from constructs import Construct
from aws_cdk.aws_stepfunctions import DefinitionBody 

class TestStepFunction(Construct):
    def __init__(self, scope: Construct, id: str):
        super().__init__(scope, id)


        # Define Lambda Functions
        create_dynamodb_table = _lambda.Function(self, "CreateDynamoDBTable-CDK",
            runtime=_lambda.Runtime.PYTHON_3_9,
            handler="index.lambda_handler",
            code=_lambda.Code.from_asset("stacks/step_functions_stack/lambdas/create_dynamodb_table"),
            timeout=Duration.minutes(5),
            function_name="CreateDynamoDBTable-CDK"
        )
        create_dynamodb_table.add_to_role_policy(iam.PolicyStatement(
            effect=iam.Effect.ALLOW,
            actions=[
                "dynamodb:CreateTable",
                "dynamodb:DescribeTable"
            ],
            resources=["arn:aws-us-gov:dynamodb:*:*:table/*"]
        ))
        
        parse_findings = _lambda.Function(self, "ParseFortifyFindings-CDK",
            runtime=_lambda.Runtime.PYTHON_3_9,
            handler="index.lambda_handler",
            code=_lambda.Code.from_asset("stacks/step_functions_stack/lambdas/parse_fortify_findings_dynamodb"),
            timeout=Duration.minutes(5),
            function_name="ParseFortifyFindings-CDK",
            vpc=ec2.Vpc.from_lookup(
                self, 
                "denali-poc-vpc", 
                vpc_id="vpc-04722c09eccda8315"
            ),
            vpc_subnets=ec2.SubnetSelection(
                subnets=[
                    ec2.Subnet.from_subnet_id(self, "denali-poc-private-subnet-2", "subnet-07b599999e083926a"),
                    ec2.Subnet.from_subnet_id(self, "denali-poc-private-subnet-1", "subnet-037ee1b96ac684f7d")
                ]
            ),
            security_groups=[ec2.SecurityGroup.from_security_group_id(
                self, 
                "LambdaSecurityGroup", 
                "sg-04db58b3fca80f069" 
            )]
        )

        parse_findings.add_to_role_policy(iam.PolicyStatement(
            effect=iam.Effect.ALLOW,
            actions=[
                "dynamodb:BatchWriteItem",
                "dynamodb:PutItem"
            ],
            resources=["arn:aws-us-gov:dynamodb:us-gov-west-1:354049455466:table/*"]
        ))

        parse_findings.add_to_role_policy(iam.PolicyStatement(
            effect=iam.Effect.ALLOW,
            actions=[
                "secretsmanager:GetSecretValue"
            ],
            resources=[
                "arn:aws-us-gov:secretsmanager:us-gov-west-1:354049455466:secret:*",
                "arn:aws-us-gov:secretsmanager:*:*:secret:gitea/api/*"
            ]
        ))

        scan_table = _lambda.Function(self, "DynamoDBTableScan-CDK",
            runtime=_lambda.Runtime.PYTHON_3_9,
            handler="index.lambda_handler",
            code=_lambda.Code.from_asset("stacks/step_functions_stack/lambdas/dynamodb_table_scan"),
            timeout=Duration.minutes(5),
            function_name="DynamoDBTableScan-CDK"
        )

        scan_table.role.add_managed_policy(
            iam.ManagedPolicy.from_managed_policy_arn(
                self, 
                "DynamoDBReadOnlyAccess",
                "arn:aws-us-gov:iam::aws:policy/AmazonDynamoDBReadOnlyAccess"
            )
        )

        # Define common states first
        fail_state = sfn.Fail(self, "Fail")
        success_state = sfn.Succeed(self, "Success")
        
        delete_table = tasks.CallAwsService(
            self, "DeleteTable",
            service="dynamodb",
            action="deleteTable",
            parameters={
                "TableName.$": "$.tableName"
            },
            iam_resources=["*"]
        ).next(fail_state)

        # Define Task States
        run_fortify_scan = tasks.CallAwsService(
            self, "Run Fortify Scan on Instance & Push Results to",
            service="ssm",
            action="sendCommand",
            parameters={
                "DocumentName.$": "$.scanDocumentName",
                "InstanceIds.$": "$.fortifyScanInstanceID",
                "Parameters": {
                    "BranchName.$": "$.mainBranch"
                }
            },
            iam_resources=["*"]
        )

        modify_output = sfn.Pass(
            self, "Modify Output for Loop",
            parameters={
                "CommandId.$": "$.Command.CommandId",
                "InstanceId.$": "$.Command.InstanceIds[0]"
            }
        )

        get_command_invocation = tasks.CallAwsService(
            self, "GetCommandInvocation",
            service="ssm",
            action="getCommandInvocation",
            parameters={
                "CommandId.$": "$.CommandId",
                "InstanceId.$": "$.InstanceId"
            },
            iam_resources=["*"]
        )

        create_table = tasks.LambdaInvoke(
            self, "Create DynamoDB Table for Findings",
            lambda_function=create_dynamodb_table,
            payload=sfn.TaskInput.from_object({
                "tableName.$": "$.tableName",
                "keySchema": [
                    {
                        "AttributeName": "InstanceID",
                        "KeyType": "HASH"
                    }
                ],
                "attributeDefinitions": [
                    {
                        "AttributeName": "InstanceID",
                        "AttributeType": "S"
                    }
                ],
                "billingMode": "PAY_PER_REQUEST"
            })
        ).add_catch(fail_state, errors=["TableAlreadyExistsError"])

        parse_findings_task = tasks.LambdaInvoke(
            self, "Pull Repo & Parse Individual Findings into Dyna",
            lambda_function=parse_findings,
            payload=sfn.TaskInput.from_object({
                "input.$": "$"
            })
        ).add_catch(delete_table, errors=["States.ALL"])

        get_findings = tasks.LambdaInvoke(
            self, "Get DynamoDB Findings",
            lambda_function=scan_table,
            payload=sfn.TaskInput.from_object({
                "tableName.$": "$.tableName"
            })
        )

        process_findings = sfn.Map(
            self, "Proccess each Finding",
            items_path="$.items",
            max_concurrency=1
        ).iterator(
            sfn.Pass(self, "Pass")
        ).add_catch(delete_table, errors=["States.ALL"])

        wait_state = sfn.Wait(
            self, "Wait",
            time=sfn.WaitTime.duration(Duration.seconds(5))
        )

        # Define choice state
        choice_state = sfn.Choice(self, "Choice")\
            .when(
                sfn.Condition.string_equals("$.StatusDetails", "Success"),
                create_table
            ).when(
                sfn.Condition.or_(
                    sfn.Condition.string_equals("$.StatusDetails", "InProgress"),
                    sfn.Condition.string_equals("$.StatusDetails", "Pending")
                ),
                wait_state
            ).otherwise(fail_state)

        # Chain everything together
        definition = run_fortify_scan\
            .next(modify_output)\
            .next(get_command_invocation)\
            .next(choice_state)

        wait_state.next(get_command_invocation)
        create_table.next(parse_findings_task)
        parse_findings_task.next(get_findings)
        get_findings.next(process_findings)
        process_findings.next(success_state)

        # Create State Machine
        self.state_machine = sfn.StateMachine(
            self, "TestStateMachine",
            state_machine_name="DenaliPOC-Test-CDK",
            definition_body=DefinitionBody.from_chainable(definition),
            timeout=Duration.minutes(30)
        )