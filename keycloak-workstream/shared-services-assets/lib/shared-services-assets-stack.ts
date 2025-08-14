import type { ConfigurationDocument, Helm, HelmChart, Docker, Image, Vpc } from "./interface.types";
import { Construct } from "constructs";
import {
  Duration,
  RemovalPolicy,
  Size,
  Stack,
  StackProps,
  aws_ec2 as ec2,
  aws_ecr as ecr,
  aws_s3 as s3,
  aws_s3_deployment as s3Deployment,
  aws_lambda as lambda,
  aws_iam as iam,
  aws_logs as logs,
  custom_resources as customResources,
  Aws,
  CfnOutput,
  CfnResource,
} from "aws-cdk-lib";
import { KubectlV31Layer as KubectlLayer } from "@aws-cdk/lambda-layer-kubectl-v31";

import * as path from "path";
import { globSync } from "glob";

export interface ChartRepositoryMap {
  [key: string]: {
    repository: string;
    version: string;
  };
}

export interface SharedServicesAssetsStackProps extends StackProps, ConfigurationDocument {
  enableSync?: boolean;
}

export class SharedServicesAssetsStack extends Stack {
  private _chartMap: ChartRepositoryMap = {};

  get ChartMap() {
    return this._chartMap;
  }

  constructor(scope: Construct, id: string, private readonly props: SharedServicesAssetsStackProps) {
    super(scope, id, props);

    const { helm, docker, vpc, enableSync = false } = props;

    const vpcResource = vpc
      ? ec2.Vpc.fromLookup(this, `${this.node.id}-Vpc`, { vpcId: vpc.id })
      : ec2.Vpc.fromLookup(this, `${this.node.id}-Vpc`, { isDefault: true });

    // Create a logGroup to record logs from lambda functions
    const logGroup = new logs.LogGroup(this, "shared-services-assets-lambda-logGroup", {
      retention: logs.RetentionDays.ONE_WEEK,
      removalPolicy: RemovalPolicy.DESTROY,
      logGroupName: "shared-services-assets-lambda",
    });

    const chartMap = this._chartMap;

    const assetBucket = new s3.Bucket(this, "assets-bucket", {
      bucketName: `${this.account}-${this.region}-local-assets`,
      removalPolicy: RemovalPolicy.DESTROY,
      autoDeleteObjects: true,
      blockPublicAccess: s3.BlockPublicAccess.BLOCK_ALL,
      lifecycleRules: [
        {
          expiration: Duration.days(60),
          transitions: [
            {
              storageClass: s3.StorageClass.INFREQUENT_ACCESS,
              transitionAfter: Duration.days(30),
            },
          ],
        },
      ],
    });

    const lambdaFunctionSecurityGroup = new ec2.SecurityGroup(this, "sg-lambda-general-access", {
      vpc: vpcResource,
      allowAllOutbound: true,
      description: "Security group for lambda function",
    });

    const lambdaS3AutoDeleteObjectsCustomResourceProvider = this.node
      .findAll()
      .find(
        (node) =>
          node instanceof CfnResource &&
          node.cfnResourceType == "AWS::Lambda::Function" &&
          node.logicalId.includes("Custom::S3AutoDeleteObjectsCustomResourceProvider")
      ) as lambda.CfnFunction;

    const lambdaS3AutoDeleteObjectsCustomResourceProviderRole = this.node
      .findAll()
      .find(
        (node) =>
          node instanceof CfnResource &&
          node.cfnResourceType == "AWS::IAM::Role" &&
          node.logicalId.includes("Custom::S3AutoDeleteObjectsCustomResourceProvider")
      ) as iam.CfnRole;

    if (lambdaS3AutoDeleteObjectsCustomResourceProvider) {
      if (this.region.includes("us-iso"))
        lambdaS3AutoDeleteObjectsCustomResourceProvider.addPropertyOverride("Runtime", "nodejs20.x");

      if (vpc?.subnets && vpc.subnets.length > 0) {
        lambdaS3AutoDeleteObjectsCustomResourceProvider.addPropertyOverride("VpcConfig", {
          SubnetIds: vpc?.subnets.map((subnet) => subnet.id) ?? [],
          SecurityGroupIds: [lambdaFunctionSecurityGroup.securityGroupId],
        });

        lambdaS3AutoDeleteObjectsCustomResourceProvider.addDependency(
          lambdaFunctionSecurityGroup.node.defaultChild as ec2.CfnSecurityGroup
        );

        if (lambdaS3AutoDeleteObjectsCustomResourceProviderRole) {
          const lambdaVPCAccessExecutionRoleArn = `arn:${Aws.PARTITION}:iam::aws:policy/service-role/AWSLambdaVPCAccessExecutionRole`;
          const lambdaAWSLambdaBasicExecutionRoleArn = `arn:${Aws.PARTITION}:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole`;

          lambdaS3AutoDeleteObjectsCustomResourceProviderRole.addPropertyOverride("ManagedPolicyArns", [
            lambdaAWSLambdaBasicExecutionRoleArn,
            lambdaVPCAccessExecutionRoleArn,
          ]);
        }
      }
    }

    const lambdaSubnetSelection: ec2.SubnetSelection = {
      subnetType: vpc?.isolated ? ec2.SubnetType.PRIVATE_ISOLATED : ec2.SubnetType.PRIVATE_WITH_EGRESS,
      subnetFilters: [ec2.SubnetFilter.byIds((vpc?.subnets ?? []).map((subnet) => subnet.id))],
    };

    // Upload external assets
    new s3Deployment.BucketDeployment(this, `external-asset-bucket-deployment`, {
      destinationBucket: assetBucket,
      sources: [
        s3Deployment.Source.asset(
          path.join(__dirname, "..", "external"),
          enableSync ? {} : { exclude: ["**/docker/**"] }
        ),
      ],
      memoryLimit: 1024,
      retainOnDelete: true,
      ephemeralStorageSize: Size.gibibytes(10),
      logGroup,
      vpc: vpc ? vpcResource : undefined,
      vpcSubnets: vpc ? lambdaSubnetSelection : undefined,
    });

    // Create a lambda role that have read access to asset-bucket and create, push permission for ecr
    const ECRPullPushLambdaRole = new iam.Role(this, "helm-push-lambda-role", {
      description: "Helm push lambda role",
      assumedBy: new iam.ServicePrincipal("lambda.amazonaws.com"),
      managedPolicies: [iam.ManagedPolicy.fromAwsManagedPolicyName("service-role/AWSLambdaBasicExecutionRole")],
      inlinePolicies: {
        "ec2-access": new iam.PolicyDocument({
          statements: [
            new iam.PolicyStatement({
              effect: iam.Effect.ALLOW,
              actions: ["ec2:DescribeNetworkInterfaces", "ec2:CreateNetworkInterface", "ec2:DeleteNetworkInterface"],
              resources: ["*"],
            }),
          ],
        }),
        "bucket-access": new iam.PolicyDocument({
          statements: [
            new iam.PolicyStatement({
              effect: iam.Effect.ALLOW,
              actions: ["s3:GetObject"],
              resources: [`${assetBucket.bucketArn}/*`],
            }),
          ],
        }),
        "ecr-access": new iam.PolicyDocument({
          statements: [
            new iam.PolicyStatement({
              effect: iam.Effect.ALLOW,
              actions: [
                "ecr:BatchCheckLayerAvailability",
                "ecr:BatchGetImage",
                "ecr:CompleteLayerUpload",
                "ecr:GetDownloadUrlForLayer",
                "ecr:InitiateLayerUpload",
                "ecr:DescribeRepositories",
                "ecr:DescribeImages",
                "ecr:UploadLayerPart",
                "ecr:PutImage",
              ],
              resources: [`arn:${this.partition}:ecr:${this.region}:${this.account}:repository/*`],
            }),
            new iam.PolicyStatement({
              effect: iam.Effect.ALLOW,
              actions: ["ecr:GetAuthorizationToken"],
              resources: [`*`],
            }),
          ],
        }),
      },
    });

    const kubectlLayer = new KubectlLayer(this, "KubectlLayer");

    const helmPushLambda = new lambda.Function(this, "helm-push-to-ecr", {
      functionName: `helm-push-to-ecr`,
      description: "Helm push lambda function",
      runtime: lambda.Runtime.PYTHON_3_11,
      code: lambda.Code.fromAsset(path.join(__dirname, "lambda", "helm")),
      handler: "main.lambda_handler",
      role: ECRPullPushLambdaRole,
      layers: [kubectlLayer],
      timeout: Duration.minutes(5),
      memorySize: 512,
      ephemeralStorageSize: Size.gibibytes(1),
      logGroup,
      vpc: vpc ? vpcResource : undefined,
      vpcSubnets: vpc ? lambdaSubnetSelection : undefined,
    });

    if (helm) {
      this.createHelmService(vpcResource, assetBucket, helm, chartMap);
    }

    if (docker) {
      this.createDockerService(vpcResource, assetBucket, docker);
    }
  }

  private createDockerService(vpcResource: ec2.IVpc, assetBucket: s3.Bucket, docker: Docker) {
    const bucketDeploymentNode = this.node.tryFindChild(`external-asset-bucket-deployment`) as s3.Bucket;

    const { images } = docker;

    images.forEach(({ repository, tag }) => {
      const containerName = path.basename(repository);
      const knownRepositories = this.node.findAll().filter((node) => node instanceof ecr.Repository);

      if (!knownRepositories.find((node) => node.node.id.split("--").at(-1) === containerName)) {
        const imageRepository = new ecr.Repository(this, `docker-registry--${containerName}`, {
          repositoryName: containerName,
          emptyOnDelete: true,
          removalPolicy: RemovalPolicy.DESTROY,
        });

        imageRepository.node.addDependency(bucketDeploymentNode);

        new CfnOutput(this, `output-docker-repository--${containerName}`, {
          value: imageRepository.repositoryUri,
        });
      }
    });
  }

  private createHelmService(vpcResource: ec2.IVpc, assetBucket: s3.Bucket, helm: Helm, chartMap: ChartRepositoryMap) {
    const { charts } = helm;

    const bucketDeploymentNode = this.node.tryFindChild(`external-asset-bucket-deployment`) as s3.Bucket;
    const helmPushLambda = this.node.tryFindChild("helm-push-to-ecr") as lambda.Function;
    const logGroup = this.node.tryFindChild("shared-services-assets-lambda-logGroup") as logs.LogGroup;

    const { vpc } = this.props;

    const lambdaSubnetSelection: ec2.SubnetSelection = {
      subnetType: vpc?.isolated ? ec2.SubnetType.PRIVATE_ISOLATED : ec2.SubnetType.PRIVATE_WITH_EGRESS,
      subnetFilters: [ec2.SubnetFilter.byIds((vpc?.subnets ?? []).map((subnet) => subnet.id))],
    };

    const dockerFiles = globSync(`${path.join(__dirname, "..", "external/docker")}/*`, {
      absolute: true,
    });

    charts.forEach(({ chartName, images, version }) => {
      const knownRepositories = this.node.findAll().filter((node) => node instanceof ecr.Repository);

      const chartRepository = new ecr.Repository(this, `helm-chart-registry--${chartName}`, {
        repositoryName: chartName,
        emptyOnDelete: true,
        removalPolicy: RemovalPolicy.DESTROY,
      });

      chartRepository.node.addDependency(bucketDeploymentNode);

      chartMap[chartName] = {
        repository: chartRepository.repositoryUri,
        version,
      };

      // Upload helm chart into ECR
      // get current time and get it in epoch
      const currentTime = new Date();
      const epochTime = currentTime.getTime();

      const triggerHandler: customResources.AwsSdkCall = {
        service: "Lambda",
        action: "Invoke",
        parameters: {
          FunctionName: helmPushLambda.functionArn,
          InvocationType: "Event",
          Payload: JSON.stringify({
            SOURCE_BUCKET: assetBucket.bucketName,
            SOURCE_KEY: `helm/${chartName}/${chartName}-${version}.tgz`,
            CHART_NAME: chartName,
            DESTINATION_REPOSITORY: chartRepository.repositoryUri,
          }),
        },
        physicalResourceId: customResources.PhysicalResourceId.of(
          `${this.node.id}-trigger-upload-helm-chart-${chartName}-${epochTime}`
        ),
      };

      // Create the custom resource
      const crFunction = new customResources.AwsCustomResource(
        this,
        `${this.node.id}-trigger-upload-helm-chart-${chartName}-cr`,
        {
          onCreate: triggerHandler,
          onUpdate: triggerHandler,
          policy: customResources.AwsCustomResourcePolicy.fromStatements([
            new iam.PolicyStatement({
              actions: ["lambda:InvokeFunction"],
              resources: [helmPushLambda.functionArn],
            }),
          ]),
          vpc: vpc ? vpcResource : undefined,
          vpcSubnets: vpc ? lambdaSubnetSelection : undefined,
          logGroup,
          serviceTimeout: Duration.seconds(180),
          timeout: Duration.seconds(120),
        }
      );

      const cfFunctionNode = this.node
        .findAll()
        .find(
          (node) =>
            node instanceof CfnResource &&
            node.cfnResourceType === "AWS::Lambda::Function" &&
            node.logicalId.includes(
              crFunction.node.children.filter((node) => node instanceof lambda.SingletonFunction)[0].constructName
            )
        );
      if (cfFunctionNode && this.region.includes("us-iso")) {
        (<lambda.CfnFunction>cfFunctionNode).addPropertyOverride("Runtime", "nodejs20.x");
      }

      // Upload related docker images to helm chart
      images.forEach(({ repository, tag }) => {
        const containerName = path.basename(repository);
        const knownRepositories = this.node.findAll().filter((node) => node instanceof ecr.Repository);

        let imageRegistry: ecr.Repository;

        if (containerName === chartName) {
          console.warn(`image ${containerName} is same as the chart name ${chartName}, using chart repository instead`);
          imageRegistry = chartRepository;
        } else {
          if (!knownRepositories.find((node) => node.node.id.split("--").at(-1) === containerName)) {
            imageRegistry = new ecr.Repository(this, `image-registry--${containerName}`, {
              repositoryName: containerName,
              emptyOnDelete: true,
              removalPolicy: RemovalPolicy.DESTROY,
            });

            imageRegistry.node.addDependency(bucketDeploymentNode);

            const dockerFile = dockerFiles.find((file) => file.includes(`${containerName}__${tag}`));

            if (dockerFile) {
              const src = `${assetBucket.bucketName}/docker/${containerName}__${tag}.tar`;
              const dest = `${imageRegistry.repositoryUri}:${tag}`;

              console.log(`Container Source: ${src}`);

              new CfnOutput(this, `output-image-registry--${containerName}`, {
                value: dest,
              });
            }
          }
        }
      });
    });
  }
}
