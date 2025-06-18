from aws_cdk import (
    # Duration,
    Stack,
    # aws_sqs as sqs,
)
from constructs import Construct
from .step_functions.remediation_step_function import RemediationStepFunction
from .step_functions.test_step_function import TestStepFunction

class StepFunctionsStack(Stack):

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # The code that defines your stack goes here

        remediation_sf = RemediationStepFunction(self, "DenaliPOC-Remediation-Test-CDK")
        test_sf = TestStepFunction(self, "DenaliPOC-Test-CDK")
