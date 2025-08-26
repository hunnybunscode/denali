/*
 * © 2025 Amazon Web Services, Inc. or its affiliates. All Rights Reserved.
 * This AWS Content is provided subject to the terms of the AWS Customer Agreement
 * available at http://aws.amazon.com/agreement or other written agreement between
 * Customer and either Amazon Web Services, Inc. or Amazon Web Services EMEA SARL or both.
 * -----
 * File: /lib/stig-eks-imagebuilder-stack.ts
 * Created Date: Friday February 21st 2025
 * -----
 */

import {
  Stack,
  StackProps,
  aws_imagebuilder as imageBuilder,
  aws_ec2 as ec2,
  aws_iam as iam,
  aws_s3 as s3,
  aws_ssm as ssm,
  aws_logs as logs,
  aws_lambda as lambda,
  aws_stepfunctions as sfn,
  aws_stepfunctions_tasks as tasks,
  aws_events as events,
  aws_events_targets as targets,
  Tags,
  RemovalPolicy,
  Duration,
} from "aws-cdk-lib";
import { Construct } from "constructs";

import * as fs from "fs";
import * as path from "path";
import * as yaml from "js-yaml";

export interface StigEksImageBuilderStackProps extends StackProps, ConfigurationDocument {}

const projectRootDir = path.resolve(__dirname, "..");

const defaultStorageBlock = {
  deviceName: "/dev/xvda",
  ebs: {
    deleteOnTermination: true,
    encrypted: false,
    volumeSize: 20,
    volumeType: "gp3",
  },
};

export class StigEksImageBuilderStack extends Stack {
  constructor(scope: Construct, id: string, props: StigEksImageBuilderStackProps) {
    super(scope, id, { description: "CDK Project: Creates EC2 Image Builder Pipeline ", ...props });

    const pipelines = props?.pipelines ?? [];

    const s3LoggingImageBuilder = new s3.Bucket(this, "ImageBuilderLogging", {
      bucketName: `image-builder-logging-${this.account}-${this.region}`,
      blockPublicAccess: s3.BlockPublicAccess.BLOCK_ALL,
      encryption: s3.BucketEncryption.S3_MANAGED,
      removalPolicy: RemovalPolicy.DESTROY,
      autoDeleteObjects: (process.env["ENABLE_CLEANUP"] ?? "false").toLowerCase() === "true",
      enforceSSL: true,
      versioned: false,
      lifecycleRules: [
        {
          expiration: Duration.days(30),
        },
      ],
    });

    const imageBuilderServiceManagedPolicyDocument = this.getImageBuilderServiceManagedPolicyDocument();

    const imageBuilderServiceManagedPolicyDocumentOverflow = this.getImageBuilderServiceManagedPolicyDocumentOverflow();

    const imageBuilderServiceRole = new iam.Role(this, "ImageBuilderServiceRole", {
      roleName: "ImageBuilderCustomServiceRole",
      description: "Service Role for EC2 Image Builder",
      assumedBy: new iam.ServicePrincipal("imagebuilder.amazonaws.com"),
      // path: "/aws/custom/aws-service-role/imagebuilder.amazonaws.com/AWSServiceRoleForImageBuilder/",
      managedPolicies: [
        new iam.ManagedPolicy(this, "ImageBuilderServicePolicy", {
          managedPolicyName: "ImageBuilderServicePolicy",
          description: "Allows EC2ImageBuilder to call AWS services on your behalf.",
          document: imageBuilderServiceManagedPolicyDocument,
        }),
        new iam.ManagedPolicy(this, "ImageBuilderServicePolicyOverflow", {
          managedPolicyName: "ImageBuilderServicePolicyOverflow",
          description: "Allows EC2ImageBuilder to call AWS services on your behalf.",
          document: imageBuilderServiceManagedPolicyDocumentOverflow,
        }),
      ],
    });

    // Create an EC2 instance role for image builder
    const imageBuilderRole = new iam.Role(this, "ImageBuilderRole", {
      roleName: "ImageBuilderRole",
      description: "EC2 Image Builder Role",
      assumedBy: new iam.ServicePrincipal("ec2.amazonaws.com"),
      managedPolicies: [
        iam.ManagedPolicy.fromAwsManagedPolicyName("EC2InstanceProfileForImageBuilder"),
        iam.ManagedPolicy.fromAwsManagedPolicyName("EC2InstanceProfileForImageBuilderECRContainerBuilds"),
        iam.ManagedPolicy.fromAwsManagedPolicyName("AmazonSSMManagedInstanceCore"),
      ],
      inlinePolicies: {
        "EKS-S3-Access": new iam.PolicyDocument({
          statements: [
            new iam.PolicyStatement({
              effect: iam.Effect.ALLOW,
              actions: ["s3:Get*", "s3:List*"],
              resources: [`arn:${this.partition}:s3:::amazon-eks/*`, `arn:${this.partition}:s3:::amazon-eks`],
            }),
          ],
        }),
        "ECR-Access": new iam.PolicyDocument({
          statements: [
            new iam.PolicyStatement({
              effect: iam.Effect.ALLOW,
              actions: ["ecr:GetDownloadUrlForLayer", "ecr:BatchGetImage", "ecr:BatchCheckLayerAvailability"],
              resources: ["*"],
            }),
            new iam.PolicyStatement({
              effect: iam.Effect.ALLOW,
              actions: ["ecr:GetAuthorizationToken"],
              resources: ["*"],
            }),
          ],
        }),
        "Secrets-Access-ReadOnly": new iam.PolicyDocument({
          statements: [
            new iam.PolicyStatement({
              effect: iam.Effect.ALLOW,
              actions: ["secretsmanager:DescribeSecret", "secretsmanager:GetSecretValue", "secretsmanager:ListSecrets"],
              resources: ["*"],
            }),
          ],
        }),
        "SSM-ParameterStore-ReadOnly": new iam.PolicyDocument({
          statements: [
            new iam.PolicyStatement({
              effect: iam.Effect.ALLOW,
              actions: ["ssm:GetParameter", "ssm:GetParameters", "ssm:GetParametersByPath", "ssm:DescribeParameters"],
              resources: ["*"],
            }),
          ],
        }),
      },
    });

    s3LoggingImageBuilder.grantReadWrite(imageBuilderRole);

    const imageBuilderInstanceProfile = new iam.InstanceProfile(this, "ImageBuilderInstanceProfile", {
      instanceProfileName: "ImageBuilderRoleProfile",
      role: imageBuilderRole,
    });

    this.createStepsLogGroup();
    this.createTriggerImageBuilderPipelineLambdaFunction();
    this.createUpdateAmiLambdaFunction();

    for (const pipeline of pipelines) {
      const {
        ami: amiFilter,
        name: pipelineName,
        storages,
        tags,
        instanceTypes,
        description,
        components,
        vpc,
        version,
        scan: enableScan = true,
        test: enableTest = true,
        enhancedImageMetadata: enableEnhancedImageMetadataEnabled = true,
        distributions = [],
      } = pipeline;

      const amiLookup = new ec2.LookupMachineImage({
        name: "*",
        filters: Object.fromEntries(Object.entries(amiFilter).map(([key, value]) => [key, [value]])),
      });

      const vpcResource = vpc
        ? ec2.Vpc.fromLookup(this, `${pipelineName}-Vpc`, { vpcId: vpc.id })
        : ec2.Vpc.fromLookup(this, `${pipelineName}-Vpc`, { isDefault: true });

      let securityGroup: ec2.SecurityGroup | undefined = undefined;

      if (vpc) {
        const securityGroupName = `${pipelineName}-imagebuilder-sg`;

        // Create default security Group
        securityGroup = new ec2.SecurityGroup(this, `${pipelineName}-SecurityGroup`, {
          vpc: vpcResource,
          allowAllOutbound: true,
          allowAllIpv6Outbound: true,
          securityGroupName,
        });

        Tags.of(securityGroup).add("Name", securityGroupName);
        Tags.of(securityGroup).add("Description", `Security group for ${pipelineName} image builder pipeline`);
      }

      // create ec2 builder infrastructure configuration
      const imageBuilderInfrastructureConfiguration = new imageBuilder.CfnInfrastructureConfiguration(
        this,
        `${pipelineName}-ImageBuilderInfrastructureConfiguration`,
        {
          instanceProfileName: imageBuilderInstanceProfile.instanceProfileName,
          name: `${pipelineName}`,
          instanceTypes,
          description: "EC2 Image Builder Infrastructure Configuration",
          terminateInstanceOnFailure: true,
          instanceMetadataOptions: {
            httpPutResponseHopLimit: 2,
            httpTokens: "required",
          },
          subnetId: vpc?.subnet.id,
          securityGroupIds: securityGroup ? [securityGroup.securityGroupId] : undefined,
          logging: {
            s3Logs: {
              s3BucketName: s3LoggingImageBuilder.bucketName,
              s3KeyPrefix: "pipeline",
            },
          },
        }
      );

      const blockDeviceMappings: imageBuilder.CfnImageRecipe.InstanceBlockDeviceMappingProperty[] = [];

      if (storages && storages.length > 0) {
        for (const storageBlock of storages) {
          const { deviceName, sizeInGB, type, iops, encrypted, kmsKeyId } = storageBlock;
          const targetStorageBlock = {
            deviceName,
            ebs: {
              deleteOnTermination: true,
              encrypted: encrypted ?? false,
              volumeSize: sizeInGB,
              volumeType: type,
              iops,
              kmsKeyId: encrypted ? kmsKeyId : undefined,
            },
          };
          blockDeviceMappings.push(targetStorageBlock);
        }
      } else {
        blockDeviceMappings.push(defaultStorageBlock);
      }

      const imageComponents: imageBuilder.CfnImageRecipeProps["components"] = [];

      // Build up the image components from components
      for (const component of components) {
        if (typeof component === "string") {
          const componentPath = path.resolve(projectRootDir, component);

          const componentResource = this.createComponent(componentPath, pipelineName, version, description);

          const targetComponent = {
            componentArn: componentResource.attrArn,
          };

          imageComponents.push(targetComponent);
        } else {
          let { name, version, parameters } = component;

          // Check name is a file that exist
          const componentPath = path.resolve(projectRootDir, name);
          const componentValidFile = fs.existsSync(componentPath);
          let componentArn: string = "";

          if (componentValidFile) {
            const componentResource = this.createComponent(componentPath, pipelineName, version, description);
            version = `${version}/1`;
            componentArn = componentResource.attrArn;
          } else {
            if (!version.includes("/") && !version.includes("x")) {
              version = `${version}/1`;
            }

            componentArn = `arn:${this.partition}:imagebuilder:${this.region}:aws:component/${name}/${version}`;
          }

          const targetComponent = {
            componentArn,
          };

          if (parameters && parameters.length > 0) {
            Object.assign(targetComponent, {
              parameters: parameters.map(parameter => {
                const { name, value } = parameter;
                return {
                  name,
                  value: Array.isArray(value) ? value : [value],
                };
              }),
            });
          }

          imageComponents.push(targetComponent);
        }
      }

      const amiImage = amiLookup.getImage(this);

      const amiImageSSMParam = new ssm.StringParameter(this, `${pipelineName}-AmiImageSSMParam`, {
        stringValue: amiImage.imageId,
        description: `The target AMI image ID for EC2 Image Builder Pipeline: ${pipelineName}`,
        parameterName: `/image-builder/${pipelineName}/target-ami-image-id`,
      });

      amiImageSSMParam.grantRead(imageBuilderServiceRole);

      const completeUserData: string[] = [];

      if (props.environment.proxy) {
        const { httpProxy = "", httpsProxy = "", noProxy } = props.environment.proxy;

        let noProxyStr = "";

        if (noProxy) {
          if (Array.isArray(noProxy)) {
            noProxyStr = noProxy.join(",");
          } else {
            noProxyStr = noProxy;
          }
        }

        const defaultCleanupUserData = fs.readFileSync(
          path.resolve(projectRootDir, "lib/script", "default-cleanup-userdata.sh"),
          "utf8"
        );

        const proxyUserData = fs
          .readFileSync(path.resolve(projectRootDir, "lib/script", "proxy-userdata.sh"), "utf8")
          .replace(/{{HTTP_PROXY}}/g, httpProxy)
          .replace(/{{HTTPS_PROXY}}/g, httpsProxy)
          .replace(/{{NO_PROXY}}/g, noProxyStr);

        const userData = fs
          .readFileSync(path.resolve(projectRootDir, "lib/script", "userdata.sh"), "utf8")
          .replace(/{{AWS_REGION}}/g, this.region)
          .replace(/{{S3_ENDPOINT}}/g, `https://s3.${this.region}.amazonaws.com`);

        completeUserData.push(defaultCleanupUserData, proxyUserData, userData);
      }

      const userDataBase64 = Buffer.from(completeUserData.join("\n")).toString("base64");

      const imageRecipe = new imageBuilder.CfnImageRecipe(this, `${pipelineName}-ImageRecipe`, {
        name: pipelineName,
        version,
        components: imageComponents,
        parentImage: `ssm:${amiImageSSMParam.parameterArn}`,
        additionalInstanceConfiguration: {
          systemsManagerAgent: {
            uninstallAfterBuild: false,
          },
          userDataOverride: props.environment.proxy ? userDataBase64 : undefined,
        },
        blockDeviceMappings,
        description,
        tags,
      });

      Tags.of(imageRecipe).add("Base AMI", amiImage.imageId);
      imageBuilderServiceRole.node.addDependency(imageRecipe);

      const distributionConfiguration = distributions.map(({ region, amiDistributionConfiguration }) => {
        return {
          region,
          description: `${pipelineName} AMI Distribution Configuration for region ${this.region}`,
          amiDistributionConfiguration: {
            amiTags: {
              ...{
                PIPELINE: pipelineName,
                VERSION: version,
              },
              ...tags,
            },
            ...amiDistributionConfiguration,
          },
        };
      });

      type Writable<T> = { -readonly [P in keyof T]: T[P] };

      const preDistributions: Writable<imageBuilder.CfnDistributionConfiguration.DistributionProperty>[] = [
        {
          region: this.region,
          amiDistributionConfiguration: {
            description: `${pipelineName} Default AMI Distribution Configuration for region ${this.region}`,
            targetAccountIds: [Stack.of(this).account],
            amiTags: {
              ...{
                PIPELINE: pipelineName,
                VERSION: version,
              },
              ...tags,
            },
          },
        },
        ...distributionConfiguration,
      ];

      const mergedDistributions = preDistributions.reduce((accumulation, distribution) => {
        const existing = accumulation.find(targetDistribution => targetDistribution.region === distribution.region);
        if (existing) {
          console.info(`Updating distribution [${existing.region}]`);

          existing.amiDistributionConfiguration = {
            ...existing.amiDistributionConfiguration,
            ...distribution.amiDistributionConfiguration,
          };
        } else {
          accumulation.push(distribution);
        }
        return accumulation;
      }, [] as Writable<imageBuilder.CfnDistributionConfiguration.DistributionProperty>[]);

      const distributionConfig = new imageBuilder.CfnDistributionConfiguration(
        this,
        `${pipelineName}-ImageBuilderDistributionConfiguration`,
        {
          name: `${pipelineName}-distribution-config`,
          description: "AMI Distribution Configuration",
          distributions: mergedDistributions,
        }
      );

      const imageBuilderPipeline = new imageBuilder.CfnImagePipeline(this, `${pipelineName}-ImageBuilderPipeline`, {
        name: pipelineName,
        imageRecipeArn: imageRecipe.attrArn,
        executionRole: imageBuilderServiceRole.roleArn,
        infrastructureConfigurationArn: imageBuilderInfrastructureConfiguration.attrArn,
        description,
        enhancedImageMetadataEnabled: enableEnhancedImageMetadataEnabled,
        status: "ENABLED",
        imageScanningConfiguration: {
          imageScanningEnabled: enableScan,
        },
        distributionConfigurationArn: distributionConfig.attrArn,
        imageTestsConfiguration: {
          imageTestsEnabled: enableTest,
          timeoutMinutes: 60,
        },
        tags,
      });

      // Create Step Function to execute pipeline if schedule is provided
      if (pipeline.schedule) {
        this.createScheduledPipeline(pipelineName, imageBuilderPipeline, pipeline.schedule, pipeline.ami);
      }
    }
  }

  private getImageBuilderServiceManagedPolicyDocumentOverflow() {
    return new iam.PolicyDocument({
      statements: [
        new iam.PolicyStatement({
          effect: iam.Effect.ALLOW,
          actions: ["ec2:CreateTags"],
          resources: [`arn:${this.partition}:ec2:*::image/*`, `arn:${this.partition}:ec2:*:*:export-image-task/*`],
        }),
        new iam.PolicyStatement({
          effect: iam.Effect.ALLOW,
          actions: ["ec2:CreateTags"],
          resources: [`arn:${this.partition}:ec2:*::snapshot/*`, `arn:${this.partition}:ec2:*:*:launch-template/*`],
          conditions: {
            StringEquals: {
              "aws:RequestTag/CreatedBy": ["EC2 Image Builder", "EC2 Fast Launch"],
            },
          },
        }),
        new iam.PolicyStatement({
          effect: iam.Effect.ALLOW,
          actions: ["license-manager:UpdateLicenseSpecificationsForResource"],
          resources: ["*"],
        }),
        new iam.PolicyStatement({
          effect: iam.Effect.ALLOW,
          actions: ["sns:Publish"],
          resources: ["*"],
        }),
        new iam.PolicyStatement({
          effect: iam.Effect.ALLOW,
          actions: [
            "ssm:ListCommands",
            "ssm:ListCommandInvocations",
            "ssm:AddTagsToResource",
            "ssm:DescribeInstanceInformation",
            "ssm:GetAutomationExecution",
            "ssm:StopAutomationExecution",
            "ssm:ListInventoryEntries",
            "ssm:SendAutomationSignal",
            "ssm:DescribeInstanceAssociationsStatus",
            "ssm:DescribeAssociationExecutions",
            "ssm:GetCommandInvocation",
          ],
          resources: ["*"],
        }),
        new iam.PolicyStatement({
          effect: iam.Effect.ALLOW,
          actions: ["ssm:SendCommand"],
          resources: [
            `arn:${this.partition}:ssm:*:*:document/AWS-RunPowerShellScript`,
            `arn:${this.partition}:ssm:*:*:document/AWS-RunShellScript`,
            `arn:${this.partition}:ssm:*:*:document/AWSEC2-RunSysprep`,
            `arn:${this.partition}:s3:::*`,
          ],
        }),
        new iam.PolicyStatement({
          effect: iam.Effect.ALLOW,
          actions: ["ssm:SendCommand"],
          resources: [`arn:${this.partition}:ec2:*:*:instance/*`],
          conditions: {
            StringEquals: {
              "ssm:resourceTag/CreatedBy": ["EC2 Image Builder"],
            },
          },
        }),
        new iam.PolicyStatement({
          effect: iam.Effect.ALLOW,
          actions: ["ssm:StartAutomationExecution"],
          resources: [`arn:${this.partition}:ssm:*:*:automation-definition/ImageBuilder*`],
        }),
        new iam.PolicyStatement({
          effect: iam.Effect.ALLOW,
          actions: ["ssm:CreateAssociation", "ssm:DeleteAssociation"],
          resources: [
            `arn:${this.partition}:ssm:*:*:document/AWS-GatherSoftwareInventory`,
            `arn:${this.partition}:ssm:*:*:association/*`,
            `arn:${this.partition}:ec2:*:*:instance/*`,
          ],
        }),
        new iam.PolicyStatement({
          effect: iam.Effect.ALLOW,
          actions: [
            "kms:Encrypt",
            "kms:Decrypt",
            "kms:ReEncryptFrom",
            "kms:ReEncryptTo",
            "kms:GenerateDataKeyWithoutPlaintext",
          ],
          resources: ["*"],
          conditions: {
            "ForAllValues:StringEquals": {
              "kms:EncryptionContextKeys": ["aws:ebs:id"],
            },
            StringLike: {
              "kms:ViaService": ["ec2.*.amazonaws.com"],
            },
          },
        }),
        new iam.PolicyStatement({
          effect: iam.Effect.ALLOW,
          actions: ["kms:DescribeKey"],
          resources: ["*"],
          conditions: {
            StringLike: {
              "kms:ViaService": ["ec2.*.amazonaws.com"],
            },
          },
        }),
        new iam.PolicyStatement({
          effect: iam.Effect.ALLOW,
          actions: ["kms:CreateGrant"],
          resources: ["*"],
          conditions: {
            Bool: {
              "kms:GrantIsForAWSResource": "true",
            },
            StringLike: {
              "kms:ViaService": ["ec2.*.amazonaws.com"],
            },
          },
        }),
        new iam.PolicyStatement({
          effect: iam.Effect.ALLOW,
          actions: ["sts:AssumeRole"],
          resources: [`arn:${this.partition}:iam::*:role/EC2ImageBuilderDistributionCrossAccountRole`],
        }),
        new iam.PolicyStatement({
          effect: iam.Effect.ALLOW,
          actions: ["logs:CreateLogStream", "logs:CreateLogGroup", "logs:PutLogEvents"],
          resources: [`arn:${this.partition}:logs:*:*:log-group:/aws/imagebuilder/*`],
        }),
        new iam.PolicyStatement({
          effect: iam.Effect.ALLOW,
          actions: [
            "ec2:CreateLaunchTemplateVersion",
            "ec2:DescribeLaunchTemplates",
            "ec2:ModifyLaunchTemplate",
            "ec2:DescribeLaunchTemplateVersions",
          ],
          resources: ["*"],
        }),
        new iam.PolicyStatement({
          effect: iam.Effect.ALLOW,
          actions: ["ec2:ExportImage"],
          resources: [`arn:${this.partition}:ec2:*::image/*`],
          conditions: {
            StringEquals: {
              "ec2:ResourceTag/CreatedBy": "EC2 Image Builder",
            },
          },
        }),
        new iam.PolicyStatement({
          effect: iam.Effect.ALLOW,
          actions: ["ec2:ExportImage"],
          resources: [`arn:${this.partition}:ec2:*:*:export-image-task/*`],
        }),
        new iam.PolicyStatement({
          effect: iam.Effect.ALLOW,
          actions: ["ec2:CancelExportTask"],
          resources: [`arn:${this.partition}:ec2:*:*:export-image-task/*`],
          conditions: {
            StringEquals: {
              "ec2:ResourceTag/CreatedBy": "EC2 Image Builder",
            },
          },
        }),
        new iam.PolicyStatement({
          effect: iam.Effect.ALLOW,
          actions: ["iam:CreateServiceLinkedRole"],
          resources: ["*"],
          conditions: {
            StringEquals: {
              "iam:AWSServiceName": ["ssm.amazonaws.com", "ec2fastlaunch.amazonaws.com"],
            },
          },
        }),
        new iam.PolicyStatement({
          effect: iam.Effect.ALLOW,
          actions: ["ec2:EnableFastLaunch"],
          resources: [`arn:${this.partition}:ec2:*::image/*`, `arn:${this.partition}:ec2:*:*:launch-template/*`],
          conditions: {
            StringEquals: {
              "ec2:ResourceTag/CreatedBy": "EC2 Image Builder",
            },
          },
        }),
        new iam.PolicyStatement({
          effect: iam.Effect.ALLOW,
          actions: ["inspector2:ListCoverage", "inspector2:ListFindings"],
          resources: ["*"],
        }),
        new iam.PolicyStatement({
          effect: iam.Effect.ALLOW,
          actions: ["ecr:CreateRepository"],
          resources: ["*"],
          conditions: {
            StringEquals: {
              "aws:RequestTag/CreatedBy": "EC2 Image Builder",
            },
          },
        }),
        new iam.PolicyStatement({
          effect: iam.Effect.ALLOW,
          actions: ["ecr:TagResource"],
          resources: [`arn:${this.partition}:ecr:*:*:repository/image-builder-*`],
          conditions: {
            StringEquals: {
              "aws:RequestTag/CreatedBy": "EC2 Image Builder",
            },
          },
        }),
        new iam.PolicyStatement({
          effect: iam.Effect.ALLOW,
          actions: ["ecr:BatchDeleteImage"],
          resources: [`arn:${this.partition}:ecr:*:*:repository/image-builder-*`],
          conditions: {
            StringEquals: {
              "ecr:ResourceTag/CreatedBy": "EC2 Image Builder",
            },
          },
        }),
        new iam.PolicyStatement({
          effect: iam.Effect.ALLOW,
          actions: [
            "events:DeleteRule",
            "events:DescribeRule",
            "events:PutRule",
            "events:PutTargets",
            "events:RemoveTargets",
          ],
          resources: [`arn:${this.partition}:events:*:*:rule/ImageBuilder-*`],
        }),
      ],
    });
  }

  private getImageBuilderServiceManagedPolicyDocument() {
    return new iam.PolicyDocument({
      statements: [
        new iam.PolicyStatement({
          effect: iam.Effect.ALLOW,
          actions: ["ec2:RegisterImage"],
          resources: [`arn:${this.partition}:ec2:*::image/*`],
          conditions: {
            StringEquals: {
              "aws:RequestTag/CreatedBy": "EC2 Image Builder",
            },
          },
        }),
        new iam.PolicyStatement({
          effect: iam.Effect.ALLOW,
          actions: ["ec2:RegisterImage"],
          resources: [`arn:${this.partition}:ec2:*::snapshot/*`],
          conditions: {
            StringEquals: {
              "ec2:ResourceTag/CreatedBy": "EC2 Image Builder",
            },
          },
        }),
        new iam.PolicyStatement({
          effect: iam.Effect.ALLOW,
          actions: ["ec2:RunInstances"],
          resources: [
            `arn:${this.partition}:ec2:*::image/*`,
            `arn:${this.partition}:ec2:*::snapshot/*`,
            `arn:${this.partition}:ec2:*:*:subnet/*`,
            `arn:${this.partition}:ec2:*:*:network-interface/*`,
            `arn:${this.partition}:ec2:*:*:security-group/*`,
            `arn:${this.partition}:ec2:*:*:key-pair/*`,
            `arn:${this.partition}:ec2:*:*:launch-template/*`,
            `arn:${this.partition}:license-manager:*:*:license-configuration:*`,
          ],
        }),
        new iam.PolicyStatement({
          effect: iam.Effect.ALLOW,
          actions: ["ec2:RunInstances"],
          resources: [`arn:${this.partition}:ec2:*:*:volume/*`, `arn:${this.partition}:ec2:*:*:instance/*`],
          conditions: {
            StringEquals: {
              "aws:RequestTag/CreatedBy": ["EC2 Image Builder", "EC2 Fast Launch"],
            },
          },
        }),
        new iam.PolicyStatement({
          effect: iam.Effect.ALLOW,
          actions: ["iam:PassRole"],
          resources: ["*"],
          conditions: {
            StringEquals: {
              "iam:PassedToService": ["ec2.amazonaws.com", "ec2.amazonaws.com.cn", "vmie.amazonaws.com"],
            },
          },
        }),
        new iam.PolicyStatement({
          effect: iam.Effect.ALLOW,
          actions: ["ec2:StopInstances", "ec2:StartInstances", "ec2:TerminateInstances"],
          resources: ["*"],
          conditions: {
            StringEquals: {
              "ec2:ResourceTag/CreatedBy": "EC2 Image Builder",
            },
          },
        }),
        new iam.PolicyStatement({
          effect: iam.Effect.ALLOW,
          actions: [
            "ec2:CopyImage",
            "ec2:CreateImage",
            "ec2:CreateLaunchTemplate",
            "ec2:DeregisterImage",
            "ec2:DescribeImages",
            "ec2:DescribeInstanceAttribute",
            "ec2:DescribeInstanceStatus",
            "ec2:DescribeInstances",
            "ec2:DescribeInstanceTypeOfferings",
            "ec2:DescribeInstanceTypes",
            "ec2:DescribeSubnets",
            "ec2:DescribeTags",
            "ec2:ModifyImageAttribute",
            "ec2:DescribeImportImageTasks",
            "ec2:DescribeExportImageTasks",
            "ec2:DescribeSnapshots",
            "ec2:DescribeHosts",
          ],
          resources: ["*"],
        }),
        new iam.PolicyStatement({
          effect: iam.Effect.ALLOW,
          actions: ["ec2:ModifySnapshotAttribute"],
          resources: [`arn:${this.partition}:ec2:*::snapshot/*`],
          conditions: {
            StringEquals: {
              "ec2:ResourceTag/CreatedBy": "EC2 Image Builder",
            },
          },
        }),
        new iam.PolicyStatement({
          effect: iam.Effect.ALLOW,
          actions: ["ec2:CreateTags"],
          resources: ["*"],
          conditions: {
            StringEquals: {
              "ec2:CreateAction": ["RunInstances", "CreateImage"],
              "aws:RequestTag/CreatedBy": ["EC2 Image Builder", "EC2 Fast Launch"],
            },
          },
        }),
      ],
    });
  }

  private createComponent(
    componentPath: string,
    pipelineName: string,
    version: string,
    description: string | undefined
  ) {
    const componentDefinition = yaml.load(fs.readFileSync(componentPath, "utf8"));
    const componentName = path.basename(componentPath).split(".")[0];
    const componentPlatform = "Linux";

    const componentResource = new imageBuilder.CfnComponent(this, `${pipelineName}--${componentName}-component`, {
      name: `${pipelineName}--${componentName}`,
      version,
      platform: componentPlatform,
      data: yaml.dump(componentDefinition),
      description,
    });
    return componentResource;
  }

  private createScheduledPipeline(
    pipelineName: string,
    pipeline: imageBuilder.CfnImagePipeline,
    schedule: string,
    amiFilter: Pipeline["ami"]
  ) {
    const pipelineArn = pipeline.attrArn;
    const stepLogGroup = this.node.findChild("StepsLogGroup") as logs.LogGroup;
    const updateAmiFunction = this.node.findChild("UpdateAmiFunction") as lambda.Function;
    const triggerImageBuilderPipelineFunction = this.node.findChild(
      "TriggerImageBuilderPipelineFunction"
    ) as lambda.Function;

    // Create IAM role for Step Function
    const stepFunctionRole = new iam.Role(this, `${pipelineName}-StepFunctionRole`, {
      assumedBy: new iam.ServicePrincipal("states.amazonaws.com"),
      inlinePolicies: {
        ImageBuilderPolicy: new iam.PolicyDocument({
          statements: [
            new iam.PolicyStatement({
              effect: iam.Effect.ALLOW,
              actions: ["imagebuilder:StartImagePipelineExecution"],
              resources: [pipelineArn],
            }),
          ],
        }),
      },
    });

    // Create Step Function task

    const startPipelineTask = new tasks.LambdaInvoke(
      this,
      `${pipelineName}-invoke-trigger-image-builder-pipeline-task`,
      {
        stateName: `Start Build`,
        comment: `Trigger image builder pipeline: ${pipelineName}`,
        taskTimeout: sfn.Timeout.duration(Duration.minutes(2)),
        lambdaFunction: triggerImageBuilderPipelineFunction,
        payload: sfn.TaskInput.fromObject({
          image_pipeline_arn: pipelineArn,
        }),
      }
    );

    const definition = sfn.Chain.start(
      new tasks.LambdaInvoke(this, `${pipelineName}-invoke-update-ami-task`, {
        stateName: `Update AMI ID`,
        comment: `Update image ami for pipeline: ${pipelineName}`,
        taskTimeout: sfn.Timeout.duration(Duration.minutes(2)),
        lambdaFunction: updateAmiFunction,
        payload: sfn.TaskInput.fromObject({
          pipeline_name: pipelineName,
          ami_filters: amiFilter,
        }),
      })
    ).next(startPipelineTask);

    // Create Step Function
    const stateMachine = new sfn.StateMachine(this, `imagebuilder-pipeline-${pipelineName}-sm`, {
      stateMachineName: `imagebuilder-pipeline-${pipelineName}`,
      role: stepFunctionRole,
      definitionBody: sfn.DefinitionBody.fromChainable(definition),
      logs: {
        destination: stepLogGroup,
        level: sfn.LogLevel.ALL,
      },
    });

    // Create EventBridge rule with cron schedule. Cron expression has 6 fields
    new events.Rule(this, `${pipelineName}-ScheduleRule`, {
      // ruleName: `imagebuilder-pipeline-${pipelineName}-Schedule`,
      schedule: events.Schedule.expression(`cron(${schedule})`),
      targets: [new targets.SfnStateMachine(stateMachine)],
      description: `Rule to trigger update and build image builder pipeline: ${pipelineName}`,
    });
  }

  private createStepsLogGroup() {
    const logGroup = new logs.LogGroup(this, "StepsLogGroup", {
      logGroupName: "/aws/pipeline-step-function",
      retention: logs.RetentionDays.FIVE_MONTHS,
      removalPolicy: RemovalPolicy.DESTROY,
    });

    return logGroup;
  }

  private createTriggerImageBuilderPipelineLambdaFunction() {
    const stepLogGroup = this.node.findChild("StepsLogGroup") as logs.LogGroup;

    const triggerImageBuilderPipelineFunction = new lambda.Function(this, "TriggerImageBuilderPipelineFunction", {
      description: "Function to trigger image builder pipeline execution",
      logGroup: stepLogGroup,
      runtime: lambda.Runtime.PYTHON_3_12,
      handler: "index.lambda_handler",
      code: lambda.Code.fromAsset(path.join(__dirname, "lambda/trigger-imagebuilder-pipeline"), {
        exclude: [".env", ".venv", ".vscode", "Makefile", "requirements-dev.txt", ".gitignore"],
      }),
      deadLetterQueueEnabled: false,
      timeout: Duration.minutes(1),
      role: new iam.Role(this, "TriggerImageBuilderPipelineFunctionRole", {
        assumedBy: new iam.ServicePrincipal("lambda.amazonaws.com"),
        managedPolicies: [iam.ManagedPolicy.fromAwsManagedPolicyName("service-role/AWSLambdaBasicExecutionRole")],
        inlinePolicies: {
          "Allow-ImageBuilder-Access": new iam.PolicyDocument({
            statements: [
              new iam.PolicyStatement({
                effect: iam.Effect.ALLOW,
                actions: ["imagebuilder:StartImagePipelineExecution"],
                resources: ["*"],
              }),
            ],
          }),
        },
      }),
    });

    return triggerImageBuilderPipelineFunction;
  }

  private createUpdateAmiLambdaFunction() {
    const stepLogGroup = this.node.findChild("StepsLogGroup") as logs.LogGroup;

    // Define the Lambda function
    const updateAmiFunction = new lambda.Function(this, "UpdateAmiFunction", {
      description: "Function to update AMI ID in SSM Parameter Store based on AMI filters",
      logGroup: stepLogGroup,
      runtime: lambda.Runtime.PYTHON_3_12,
      handler: "index.lambda_handler",
      code: lambda.Code.fromAsset(path.join(__dirname, "lambda/update-ami"), {
        exclude: [".env", ".venv", ".vscode", "Makefile", "requirements-dev.txt", ".gitignore"],
      }),
      deadLetterQueueEnabled: false,
      timeout: Duration.minutes(1),
      role: new iam.Role(this, "UpdateAmiFunctionRole", {
        assumedBy: new iam.ServicePrincipal("lambda.amazonaws.com"),
        managedPolicies: [iam.ManagedPolicy.fromAwsManagedPolicyName("service-role/AWSLambdaBasicExecutionRole")],
        inlinePolicies: {
          "Allow-SSM-Access": new iam.PolicyDocument({
            statements: [
              new iam.PolicyStatement({
                effect: iam.Effect.ALLOW,
                actions: ["ssm:GetParameter", "ssm:PutParameter"],
                resources: ["arn:*:ssm:*:*:parameter/image-builder/*/target-ami-image-id"],
              }),
            ],
          }),
          "Allow-EC2-Access": new iam.PolicyDocument({
            statements: [
              new iam.PolicyStatement({
                effect: iam.Effect.ALLOW,
                actions: ["ec2:DescribeImages"],
                resources: ["*"],
              }),
            ],
          }),
        },
      }),
    });

    return updateAmiFunction;
  }
}
