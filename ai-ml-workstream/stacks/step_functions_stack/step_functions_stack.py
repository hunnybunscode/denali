from aws_cdk import (
    # Duration,
    Stack,
    # aws_sqs as sqs,
)
from constructs import Construct
from config.config import Config
from .step_functions.remediation_step_function import RemediationStepFunction
from .step_functions.test_step_function import TestStepFunction

class StepFunctionsStack(Stack):

    def __init__(self, scope: Construct, construct_id: str, config: Config, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # The code that defines your stack goes here

        remediation_sf = RemediationStepFunction(
            self, 
            f"{config.namespace}-{config.version}-RemediationStepFunction",
            config=config  
        )

        test_sf = TestStepFunction(
            self,
            f"{config.namespace}-{config.version}-TestStepFunction",
            config=config 
        )
