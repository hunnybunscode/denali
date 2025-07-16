#!/usr/bin/env python3
import os

import aws_cdk as cdk

from dashboard.dashboard_stack import DashboardStack
from dashboard.pipeline_dashboard_stack import PipelineDashboardStack


app = cdk.App()
DashboardStack(app, "DashboardStack",
    env=cdk.Environment(account=os.getenv('CDK_DEFAULT_ACCOUNT'), region=os.getenv('CDK_DEFAULT_REGION')),
)
PipelineDashboardStack(app, "PipelineDashboardStack",
    env=cdk.Environment(account=os.getenv('CDK_DEFAULT_ACCOUNT'), region=os.getenv('CDK_DEFAULT_REGION')),
)
app.synth()
