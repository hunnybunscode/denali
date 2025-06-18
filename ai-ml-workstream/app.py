#!/usr/bin/env python3
import os
import aws_cdk as cdk
from stacks.step_functions_stack.step_functions_stack import StepFunctionsStack

app = cdk.App()

env = cdk.Environment(
    account=os.environ.get('CDK_DEFAULT_ACCOUNT', os.environ.get('AWS_ACCOUNT_ID')),
    region=os.environ.get('CDK_DEFAULT_REGION', os.environ.get('AWS_REGION'))
)

StepFunctionsStack(app, "StepFunctionsStack", env=env)

app.synth()
