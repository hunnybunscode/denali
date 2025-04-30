import os

import aws_cdk as cdk

from daffodil_conversion.daffodil_conversion_stack import DaffodilConversionStack

REGION = os.getenv("AWS_REGION", os.getenv("AWS_DEFAULT_REGION"))
DEVELOPMENT=eval(os.environ.get("DEVELOPMENT", "False"))

env=cdk.Environment(
    region=REGION,
    account=os.environ["CDK_DEFAULT_ACCOUNT"] if DEVELOPMENT else None,
)

app = cdk.App()

DaffodilConversionStack(
    app,
    'DaffodilConversionStack',
    env=env,
    synthesizer=cdk.CliCredentialsStackSynthesizer(),
)

app.synth()