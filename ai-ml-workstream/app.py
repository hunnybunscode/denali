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

# Custom synthesizer for AFC2S bootstrap with permission boundaries
synthesizer = cdk.DefaultStackSynthesizer(
    qualifier='v1',
    cloud_formation_execution_role='arn:${AWS::Partition}:iam::${AWS::AccountId}:role/AFC2S-cdk-v1-cfn-exec-role-${AWS::AccountId}-${AWS::Region}',
    deploy_role_arn='arn:${AWS::Partition}:iam::${AWS::AccountId}:role/AFC2S-cdk-v1-deploy-role-${AWS::AccountId}-${AWS::Region}',
    file_asset_publishing_role_arn='arn:${AWS::Partition}:iam::${AWS::AccountId}:role/AFC2S-cdk-v1-file-pub-role-${AWS::AccountId}-${AWS::Region}',
    image_asset_publishing_role_arn='arn:${AWS::Partition}:iam::${AWS::AccountId}:role/AFC2S-cdk-v1-image-pub-role-${AWS::AccountId}-${AWS::Region}',
    lookup_role_arn='arn:${AWS::Partition}:iam::${AWS::AccountId}:role/AFC2S-cdk-v1-lookup-role-${AWS::AccountId}-${AWS::Region}',
    file_assets_bucket_name='afc2s-cdk-v1-assets-${AWS::AccountId}-${AWS::Region}',
    image_assets_repository_name='afc2s-cdk-v1-container-assets-${AWS::AccountId}-${AWS::Region}'
)

lambda_stack = LambdaStack(
    app,
    f"{cfg.namespace}-{cfg.version}-LambdaStack",
    env=env,
    config=cfg,
    synthesizer=synthesizer,
)

step_functions_stack = StepFunctionsStack(
    app,
    f"{cfg.namespace}-{cfg.version}-StepFunctionsStack",
    env=env,
    config=cfg,
    synthesizer=synthesizer,
)

step_functions_stack.add_dependency(lambda_stack)

app.synth()
