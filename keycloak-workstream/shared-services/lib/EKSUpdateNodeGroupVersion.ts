import * as fs from "fs";
import * as path from "path";
import { Construct } from "constructs";
import {
  aws_iam as iam,
  aws_lambda as lambda,
  aws_logs as logs,
  custom_resources as cr,
  CfnOutput,
  RemovalPolicy,
  Duration,
} from "aws-cdk-lib";

import { EksBlueprint } from "@aws-quickstart/eks-blueprints";
import { NagSuppressions } from "cdk-nag";

export interface EKSUpdateNodeGroupVersionProps {
  stacks: EksBlueprint[];
}

export default class EKSUpdateNodeGroupVersion {
  constructor(private scope: Construct, props: EKSUpdateNodeGroupVersionProps) {
    this.createUpdateClusterFunction();
    this.createUpdateClusterTriggerFunction(props.stacks);
  }

  private createUpdateClusterTriggerFunction(clusterStackBuilders: EksBlueprint[]) {
    clusterStackBuilders.forEach(builder => {
      const { cluster } = builder.getClusterInfo();

      const outputUpdateClusterFunctionArn = this.scope.node.findChild("UpdateClusterFunctionArn") as CfnOutput;

      const eventHandler: cr.AwsSdkCall = {
        service: "Lambda",
        action: "Invoke",

        physicalResourceId: cr.PhysicalResourceId.of(`UpdateClusterFunction-${cluster.node.id}`),
        parameters: {
          FunctionName: outputUpdateClusterFunctionArn.importValue,
          Payload: JSON.stringify({
            CLUSTER_NAME: cluster.node.id,
            REGION: builder.region,
          }),
        },
      };

      // Trigger Update Cluster function for the cluster
      const resource = new cr.AwsCustomResource(
        cluster.stack,
        `UpdateClusterCustomResource-${cluster.node.id}-${Date.now()}`,
        {
          functionName: `UpdateClusterCustomResource-${cluster.node.id}-cr`,
          policy: cr.AwsCustomResourcePolicy.fromStatements([
            new iam.PolicyStatement({
              actions: ["lambda:InvokeFunction"],
              resources: [outputUpdateClusterFunctionArn.importValue],
            }),
          ]),
          onCreate: eventHandler,
          onUpdate: eventHandler,
        }
      );

      resource.node.addDependency(cluster);
    });
  }

  private createUpdateClusterFunction() {
    const updateClusterFunctionLogGroup = new logs.LogGroup(this.scope, "UpdateClusterFunctionLogGroup", {
      logGroupName: `/aws/lambda/UpdateClusterFunction`,
      logGroupClass: logs.LogGroupClass.INFREQUENT_ACCESS,
      retention: logs.RetentionDays.ONE_WEEK,
      removalPolicy: RemovalPolicy.DESTROY,
    });

    const updateClusterFunctionRole = new iam.Role(this.scope, "UpdateClusterFunctionRole", {
      roleName: "UpdateClusterFunctionRole",
      description: "Role for the UpdateClusterFunction",
      assumedBy: new iam.ServicePrincipal("lambda.amazonaws.com"),
      managedPolicies: [iam.ManagedPolicy.fromAwsManagedPolicyName("service-role/AWSLambdaBasicExecutionRole")],
      inlinePolicies: {
        "eks-access": new iam.PolicyDocument({
          statements: [
            new iam.PolicyStatement({
              effect: iam.Effect.ALLOW,
              actions: ["eks:UpdateNodegroupVersion", "eks:List*", "eks:DescribeNodegroup"],
              resources: ["*"],
            }),
          ],
        }),
        "ec2-access": new iam.PolicyDocument({
          statements: [
            new iam.PolicyStatement({
              effect: iam.Effect.ALLOW,
              actions: ["ec2:DescribeLaunchTemplateVersions", "ec2:RunInstances", "ec2:CreateTags"],
              resources: ["*"],
            }),
          ],
        }),
      },
    });

    const updateClusterFunctionUUID: string = "f56f0b66-b3fd-4a38-a397-a4d79835544e";
    const updateClusterFunction = new lambda.SingletonFunction(this.scope, "UpdateClusterFunction", {
      uuid: updateClusterFunctionUUID,
      code: new lambda.InlineCode(
        fs.readFileSync(path.join(__dirname, "lambda/python/set-cluster-nodegroups-version/index.py"), {
          encoding: "utf-8",
        })
      ),
      handler: "index.handler",
      timeout: Duration.seconds(300),
      runtime: lambda.Runtime.PYTHON_3_11,
      logGroup: updateClusterFunctionLogGroup,
      role: updateClusterFunctionRole,
      environment: {
        LOG_LEVEL: "INFO",
      },
      description: "Update Cluster Managed Node Groups Version to the latest launch template version",
    });

    new CfnOutput(this.scope, "UpdateClusterFunctionArn", {
      exportName: "UpdateClusterFunctionArn",
      value: updateClusterFunction.functionArn,
    });

    NagSuppressions.addResourceSuppressionsByPath(
      updateClusterFunction.stack,
      `/${updateClusterFunction.stack.stackName}/SingletonLambda${updateClusterFunctionUUID.replaceAll(
        "-",
        ""
      )}/Resource`,
      [
        {
          id: "NIST.800.53.R4-LambdaInsideVPC",
          reason: "Lambda function only need access AWS resources directly",
        },
      ]
    );

    NagSuppressions.addResourceSuppressions(updateClusterFunctionLogGroup, [
      {
        id: "NIST.800.53.R4-CloudWatchLogGroupEncrypted",
        reason: "Using default Server-side encryption managed by the CloudWatch Logs service",
      },
    ]);

    NagSuppressions.addResourceSuppressions(updateClusterFunctionRole, [
      {
        id: "AwsSolutions-IAM4",
        reason: "Using default lambda execution role",
        appliesTo: ["Policy::arn:<AWS::Partition>:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"],
      },
      {
        id: "AwsSolutions-IAM5",
        reason: "Allow access to any EKS resources",
        appliesTo: ["Action::eks:List*", "Resource::*"],
      },
    ]);

    return updateClusterFunction;
  }
}
