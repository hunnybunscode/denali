import os
import aws_cdk as cdk
from config.config import get_configs
from stacks.lambda_stack import LambdaStack
from stacks.step_functions_stack.step_functions_stack import StepFunctionsStack

app = cdk.App()

config_fp = app.node.try_get_context("config_file") or "config/deployment_config.yaml"
print(f"Using config file: {config_fp}")
cfg = get_configs(config_fp)

env = cdk.Environment(
    account=os.environ.get('CDK_DEFAULT_ACCOUNT', os.environ.get('AWS_ACCOUNT_ID')),
    region=os.environ.get('CDK_DEFAULT_REGION', cfg.region)
)

lambda_stack = LambdaStack(
    app,
    f"{cfg.namespace}-{cfg.version}-LambdaStack",
    env=env,
    config=cfg,
)

step_functions_stack = StepFunctionsStack(
    app,
    f"{cfg.namespace}-{cfg.version}-StepFunctionsStack",
    env=env,
    config=cfg,
)

step_functions_stack.add_dependency(lambda_stack)

app.synth()
