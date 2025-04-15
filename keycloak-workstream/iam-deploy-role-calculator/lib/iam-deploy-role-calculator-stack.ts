import { Construct } from "constructs";
import {
  StackProps,
  Stack,
  CfnOutput,
  aws_iam as iam,
  aws_logs as logs,
  aws_cloudtrail as cloudtrail,
  aws_s3 as s3,
  aws_kms as kms,
  aws_accessanalyzer as accessAnalyzer,
  aws_ssm as ssm,
  RemovalPolicy,
  Duration,
} from "aws-cdk-lib";
import { NagSuppressions } from "cdk-nag";

import * as fs from "fs";
import * as path from "path";

export class IamDeployRoleCalculatorStack extends Stack {
  constructor(scope: Construct, id: string, props?: StackProps) {
    super(scope, id, props);

    this.createIamRoles();
    this.createIamAnalyzerLogging();

    NagSuppressions.addResourceSuppressions(
      this,
      [
        {
          id: "AwsSolutions-IAM4",
          reason: "Using AWS managed policy",
          appliesTo: [
            "Policy::arn:<AWS::Partition>:iam::aws:policy/AdministratorAccess",
            "Policy::arn:<AWS::Partition>:iam::aws:policy/AWSCloudTrail_ReadOnlyAccess",
          ],
        },
        {
          id: "AwsSolutions-IAM5",
          reason: "Not needed for IAM S3 Analyzer for monitoring ",
        },
        {
          id: "AwsSolutions-S1",
          reason: "Not needed for IAM S3 Analyzer for monitoring ",
        },
        {
          id: "NIST.800.53.R4-S3BucketLoggingEnabled",
          reason: "Not needed for IAM S3 Analyzer for monitoring ",
        },
        {
          id: "NIST.800.53.R4-S3BucketReplicationEnabled",
          reason: "Not needed for IAM S3 Analyzer for monitoring ",
        },
        {
          id: "NIST.800.53.R4-S3BucketVersioningEnabled",
          reason: "Not needed for IAM S3 Analyzer for monitoring ",
        },
        {
          id: "NIST.800.53.R4-S3BucketDefaultLockEnabled",
          reason: "Not needed for IAM S3 Analyzer for monitoring ",
        },
        {
          id: "NIST.800.53.R4-CloudTrailCloudWatchLogsEnabled",
          reason: "Not needed for IAM S3 Analyzer for monitoring ",
        },
      ],
      true
    );
  }

  private createIamRoles() {
    const adminDeployRole = new iam.Role(this, "cloudformation-admin-exec-role", {
      roleName: "cloudformation-admin-exec-role",
      description: "CloudFormation Admin Execution Role",
      assumedBy: new iam.ServicePrincipal("cloudformation.amazonaws.com"),
      managedPolicies: [iam.ManagedPolicy.fromAwsManagedPolicyName("AdministratorAccess")],
    });

    new ssm.StringParameter(this, "cloudformation-admin-exec-role-arn-ssm", {
      parameterName: "cloudformation-admin-exec-role-arn",
      stringValue: adminDeployRole.roleArn,
    });

    new CfnOutput(this, "cloudformation-admin-exec-role-arn", {
      value: adminDeployRole.roleArn,
      exportName: "cloudformation-admin-exec-role-arn",
    });

    const testDeployRole = new iam.Role(this, "cloudformation-test-exec-role", {
      roleName: "cloudformation-test-exec-role",
      description: "CloudFormation Test Execution Role",
      assumedBy: new iam.ServicePrincipal("cloudformation.amazonaws.com"),
    });

    new CfnOutput(this, "cloudformation-test-exec-role-arn", {
      value: testDeployRole.roleArn,
      exportName: "cloudformation-test-exec-role-arn",
    });

    const cdkDeployRole = iam.Role.fromRoleArn(
      this,
      `cdk-deply-role`,
      `arn:${this.partition}:iam::${this.account}:role/cdk-hnb659fds-deploy-role-${this.account}-${this.region}`
    );

    cdkDeployRole.attachInlinePolicy(
      new iam.Policy(this, "cdk-deploy-policy", {
        policyName: "AllowPassRole",
        statements: [
          new iam.PolicyStatement({
            effect: iam.Effect.ALLOW,
            actions: ["iam:PassRole"],
            resources: [adminDeployRole.roleArn, testDeployRole.roleArn],
          }),
        ],
      })
    );

    const workspaceDir = path.resolve(__dirname, "..");

    if (fs.existsSync(path.join(workspaceDir, "action.txt"))) {
      console.info("action.txt found, adding inline policy to test deploy role");

      const actionsTxt = fs.readFileSync(path.join(workspaceDir, "action.txt"), "utf8").trim();

      const actions = actionsTxt.split("\n");

      testDeployRole.addToPolicy(
        new iam.PolicyStatement({
          sid: "AllowCloudFormationActions",
          effect: iam.Effect.ALLOW,
          actions: actions,
          resources: ["*"],
        })
      );
    }
  }

  private createIamAnalyzerLogging() {
    const key = new kms.Key(this, "trail-key", {
      enableKeyRotation: true,
      removalPolicy: RemovalPolicy.DESTROY,
      alias: "iam-analyzer-trail-key",
      policy: new iam.PolicyDocument({
        statements: [
          new iam.PolicyStatement({
            sid: "Enable IAM User Permissions",
            effect: iam.Effect.ALLOW,
            principals: [new iam.AccountRootPrincipal()],
            actions: ["kms:*"],
            resources: ["*"],
          }),
          new iam.PolicyStatement({
            sid: "Allow CloudTrail to encrypt logs",
            effect: iam.Effect.ALLOW,
            principals: [new iam.ServicePrincipal("cloudtrail.amazonaws.com")],
            actions: ["kms:GenerateDataKey*"],
            resources: ["*"],
            conditions: {
              StringEquals: {
                "aws:SourceArn": `arn:${this.partition}:cloudtrail:${this.region}:${this.account}:trail/iam-analyzer-trail`,
              },
              StringLike: {
                "kms:EncryptionContext:aws:cloudtrail:arn": `arn:${this.partition}:cloudtrail:*:${this.account}:trail/*`,
              },
            },
          }),
          new iam.PolicyStatement({
            sid: "Allow CloudTrail to encrypt event data store",
            effect: iam.Effect.ALLOW,
            principals: [new iam.ServicePrincipal("cloudtrail.amazonaws.com")],
            actions: ["kms:GenerateDataKey", "kms:Decrypt"],
            resources: ["*"],
          }),
          new iam.PolicyStatement({
            sid: "Allow Log Groups",
            principals: [new iam.ServicePrincipal(`logs.${this.region}.amazonaws.com`)],
            effect: iam.Effect.ALLOW,
            actions: ["kms:Encrypt*", "kms:Decrypt*", "kms:ReEncrypt*", "kms:GenerateDataKey*", "kms:Describe*"],
            resources: ["*"],
            conditions: {
              ArnEquals: {
                "kms:EncryptionContext:aws:logs:arn": `arn:${this.partition}:logs:${this.region}:${this.account}:log-group:iam-analyzer-log-group`,
              },
            },
          }),
        ],
      }),
    });

    // Create log group for analysis an iam role
    const iamAnalyzerLogGroup = new logs.LogGroup(this, "iam-analyzer-log-group", {
      logGroupName: "iam-analyzer-log-group",
      retention: logs.RetentionDays.ONE_MONTH,
      removalPolicy: RemovalPolicy.DESTROY,
      encryptionKey: key,
    });

    const trailBucket = new s3.Bucket(this, "s3-trail", {
      encryption: s3.BucketEncryption.KMS,
      encryptionKey: key,
      blockPublicAccess: s3.BlockPublicAccess.BLOCK_ALL,
      enforceSSL: true,
      removalPolicy: RemovalPolicy.DESTROY,
      autoDeleteObjects: true,
      bucketName: `${this.account}-${this.region}-iam-analyzer-trail`,
      lifecycleRules: [
        {
          expiration: Duration.days(30),
        },
      ],
    });

    const trail = new cloudtrail.Trail(this, "cloudtrail", {
      includeGlobalServiceEvents: true,
      cloudWatchLogGroup: iamAnalyzerLogGroup,
      bucket: trailBucket,
      trailName: "iam-analyzer-trail",
      enableFileValidation: true,
      encryptionKey: key,
      cloudWatchLogsRetention: logs.RetentionDays.ONE_MONTH,
    });

    new CfnOutput(this, "trail-bucket-name", {
      value: trailBucket.bucketName,
      exportName: "trail-bucket-name",
    });

    new CfnOutput(this, "iam-analyzer-trail-arn", {
      value: trail.trailArn,
      exportName: "iam-analyzer-trail-arn",
    });

    // Create IAM Analyzer
    const iamAnalyzer = new accessAnalyzer.CfnAnalyzer(this, "iam-analyzer", {
      analyzerName: "iam-analyzer-cfn-deploy",
      type: "ACCOUNT",
      tags: [
        {
          key: "Access Type",
          value: "ACCOUNT",
        },
      ],
    });

    new CfnOutput(this, "iam-analyzer-arn", {
      value: iamAnalyzer.attrArn,
      exportName: "iam-analyzer-arn",
    });

    // Create IAM Analyzer Service role
    const iamAnalyzerRole = new iam.Role(this, "iam-analyzer-role", {
      roleName: "iam-analyzer-role",
      assumedBy: new iam.ServicePrincipal("access-analyzer.amazonaws.com"),
      managedPolicies: [iam.ManagedPolicy.fromAwsManagedPolicyName("AWSCloudTrail_ReadOnlyAccess")],
      inlinePolicies: {
        "iam-analyzer-policy": new iam.PolicyDocument({
          statements: [
            new iam.PolicyStatement({
              effect: iam.Effect.ALLOW,
              actions: ["iam:GenerateServiceLastAccessedDetails", "iam:GetServiceLastAccessedDetails"],
              resources: ["*"],
            }),
          ],
        }),
      },
    });

    trailBucket.grantRead(iamAnalyzerRole);

    new CfnOutput(this, "iam-analyzer-role-arn", {
      value: iamAnalyzerRole.roleArn,
      exportName: "iam-analyzer-role-arn",
    });

    new ssm.StringParameter(this, "iam-analyzer-role-arn-ssm", {
      parameterName: "iam-analyzer-role-arn",
      stringValue: iamAnalyzerRole.roleArn,
    });

    new ssm.StringParameter(this, "iam-analyzer-arn-ssm", {
      parameterName: "iam-analyzer-arn",
      stringValue: iamAnalyzer.attrArn,
    });

    new ssm.StringParameter(this, "iam-analyzer-cloudtrail-arn-ssm", {
      parameterName: "iam-analyzer-cloudtrail-arn",
      stringValue: trail.trailArn,
    });
  }
}
