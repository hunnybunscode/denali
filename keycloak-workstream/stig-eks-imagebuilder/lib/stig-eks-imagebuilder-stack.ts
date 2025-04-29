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
  Tags,
  RemovalPolicy,
  Duration,
} from "aws-cdk-lib";
import { Construct } from "constructs";

import * as fs from "fs";
import * as path from "path";
import * as yaml from "js-yaml";

export interface StigEksImageBuilderStackProps extends StackProps, Configuration {}

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
      enforceSSL: true,
      versioned: false,
      autoDeleteObjects: true,
      lifecycleRules: [
        {
          expiration: Duration.days(30),
        },
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
      },
    });

    s3LoggingImageBuilder.grantReadWrite(imageBuilderRole);

    const imageBuilderInstanceProfile = new iam.InstanceProfile(this, "ImageBuilderInstanceProfile", {
      instanceProfileName: "ImageBuilderRoleProfile",
      role: imageBuilderRole,
    });

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
          const { deviceName, sizeInGB, type, iops } = storageBlock;
          const targetStorageBlock = {
            deviceName,
            ebs: {
              deleteOnTermination: true,
              encrypted: false,
              volumeSize: sizeInGB,
              volumeType: type,
              iops,
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
        parentImage: amiImage.imageId,
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

      const distributionConfig = new imageBuilder.CfnDistributionConfiguration(
        this,
        `${pipelineName}-ImageBuilderDistributionConfiguration`,
        {
          name: `${pipelineName}-distribution-config`,
          description: "AMI Distribution Configuration",
          distributions: [
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
          ],
        }
      );

      const imageBuilderPipeline = new imageBuilder.CfnImagePipeline(this, `${pipelineName}-ImageBuilderPipeline`, {
        name: pipelineName,
        imageRecipeArn: imageRecipe.attrArn,
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
    }
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
}
