#!/usr/bin/env python3
import os

import aws_cdk as cdk

from pipeline_dashboard.pipeline_dashboard_stack import PipelineDashboardStack


app = cdk.App()
PipelineDashboardStack(app, "PipelineDashboardStack",
    synthesizer = cdk.DefaultStackSynthesizer(
        qualifier='hnb659fds',
        cloud_formation_execution_role='arn:${AWS::Partition}:iam::${AWS::Region}:role/cdk-hnb659fds-cfn-exec-role-{AWS::AccountId}-${AWS::Region}',
        deploy_role_arn='arn:${AWS::Partition}:iam::${AWS::Region}:role/cdk-hnb659fds-deploy-role-{AWS::AccountId}-${AWS::Region}',
        file_asset_publishing_role_arn='arn:${AWS::Partition}:iam::${AWS::Region}:role/cdk-hnb659fds-file-pub-role-{AWS::AccountId}-${AWS::Region}',
        image_asset_publishing_role_arn='arn:${AWS::Partition}:iam::${AWS::Region}:role/cdk-hnb659fds-image-pub-role-{AWS::AccountId}-${AWS::Region}',
        lookup_role_arn='arn:${AWS::Partition}:iam::${AWS::Region}:role/cdk-hnb659fds-lookup-role-{AWS::AccountId}-${AWS::Region}'
    )

    env=cdk.Environment(account=os.getenv('CDK_DEFAULT_ACCOUNT'), region=os.getenv('CDK_DEFAULT_REGION')),

    )

app.synth()
