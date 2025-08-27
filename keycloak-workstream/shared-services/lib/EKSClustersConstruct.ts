///<reference path="interfaces.d.ts" />

import * as path from "path";
import * as fs from "fs";
import { Construct } from "constructs";
import {
  aws_route53 as route53,
  StackProps,
  aws_kms as kms,
  aws_ec2 as ec2,
  aws_iam as iam,
  aws_eks as eks,
  RemovalPolicy,
  Duration,
  Stack,
  Tags,
  CfnOutput,
  DefaultStackSynthesizer,
} from "aws-cdk-lib";

import { globSync } from "glob";
import * as blueprints from "@aws-quickstart/eks-blueprints";
import { StorageClassDefaultAddon } from "./eks-blueprints/addons/storage-class-default-addon";
import { AckAddOn } from "./eks-blueprints/addons/ack";

import { NagSuppressions } from "cdk-nag";
import { VpcCniProxyPatchAddon, VpcCniProxyPatchAddonProps } from "./eks-blueprints/addons/vpc-cni-proxy-patch-addon";
import { LookupHostedZoneProvider } from "./eks-blueprints/resource-providers/hosted-zone";

export interface EksClustersConstructProps extends StackProps, ConfigurationDocument {
  extended: {
    parentStack: Stack;
    hostedZones: {
      zoneName: string;
      zone: route53.IHostedZone;
      private: boolean;
    }[];
  };
}

export class EKSClustersConstruct extends Construct {
  private _clusters: { [key: string]: eks.ICluster } = {};
  private _clusterStacks: { [key: string]: Stack } = {};

  get Clusters() {
    return this._clusters;
  }

  get ClusterStacks() {
    return this._clusterStacks;
  }

  private _props: EksClustersConstructProps;

  get props() {
    return this._props;
  }

  constructor(scope: Construct, private _id: string, props: EksClustersConstructProps) {
    super(scope, _id);

    this._props = props;
    const { clusters, env } = props;

    if (clusters === undefined) {
      return;
    }

    const commonKeyPair = this.createCommonKeyPair();

    for (const clusterMetadata of clusters) {
      const clusterStack = this.createCluster(clusterMetadata, commonKeyPair);
      this._clusters[clusterMetadata.name] = clusterStack.getClusterInfo().cluster;
      this._clusterStacks[clusterMetadata.name] = clusterStack;

      clusterStack.addDependency(props.extended.parentStack);

      // Suppress Nag for CDK Blueprints for EKS
      NagSuppressions.addStackSuppressions(
        clusterStack,
        [
          {
            id: "NIST.800.53.R4-CloudWatchLogGroupEncrypted",
            reason: "Encryption is handled by the blueprints library",
          },
          {
            id: "NIST.800.53.R5-CloudWatchLogGroupRetentionPeriod",
            reason: "Retention is handled by the blueprints library",
          },
          {
            id: "NIST.800.53.R4-LambdaInsideVPC",
            reason: "Lambda is handled by the blueprints library",
          },
          {
            id: "NIST.800.53.R4-IAMNoInlinePolicy",
            reason: "All inline policies here are created within IaC",
          },
          {
            id: "AwsSolutions-IAM5",
            reason: "IAM roles is handled by the blueprints library",
          },
          {
            id: "AwsSolutions-IAM4",
            reason: "IAM roles is handled by the blueprints library",
            appliesTo: [
              "Resource::*",
              "Policy::arn:<AWS::Partition>:iam::aws:policy/AmazonEKSClusterPolicy",
              "Policy::arn:<AWS::Partition>:iam::aws:policy/AmazonEC2ContainerRegistryReadOnly",
              "Policy::arn:<AWS::Partition>:iam::aws:policy/AmazonEKS_CNI_Policy",
              "Policy::arn:<AWS::Partition>:iam::aws:policy/AmazonEKSWorkerNodePolicy",
              "Policy::arn:<AWS::Partition>:iam::aws:policy/AmazonSSMManagedInstanceCore",
              "Policy::arn:<AWS::Partition>:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole",
              "Policy::arn:<AWS::Partition>:iam::aws:policy/service-role/AWSLambdaVPCAccessExecutionRole",
              "Policy::arn:<AWS::Partition>:iam::aws:policy/CloudWatchAgentServerPolicy",
              "Policy::arn:<AWS::Partition>:iam::aws:policy/AWSXrayWriteOnlyAccess",
              "Policy::arn:<AWS::Partition>:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole",
              "Policy::arn:<AWS::Partition>:iam::aws:policy/AmazonElasticContainerRegistryPublicReadOnly",
              "Policy::arn:<AWS::Partition>:iam::aws:policy/AmazonEKSVPCResourceController",
              "Policy::arn:<AWS::Partition>:iam::aws:policy/AmazonEKSClusterPolicy",
            ],
          },
          {
            id: "AwsSolutions-SF1",
            reason: "Handled by the blueprints library",
          },
          {
            id: "AwsSolutions-SF2",
            reason: "X-Ray is handled by the blueprints library",
          },
          {
            id: "AwsSolutions-EKS1",
            reason: "Handled by the blueprints library",
          },
        ],
        true
      );

      NagSuppressions.addResourceSuppressionsByPath(
        clusterStack,
        [`/${clusterStack.node.path}/${clusterStack.node.id}/KubectlHandlerRole/Resource`],
        [
          {
            id: "AwsSolutions-IAM4",
            reason: "Lambda is handled by the blueprints library",
          },
        ]
      );
    }
  }

  private createCommonKeyPair() {
    // Create a common ec2 key pair for SSH access for SSM
    const keyPair = new ec2.KeyPair(this, `${this.node.id}-cluster-ec2-KeyPair`, {
      keyPairName: "common-cluster-ec2-key-pair",
      format: ec2.KeyPairFormat.PEM,
      type: ec2.KeyPairType.RSA,
    });

    Tags.of(keyPair).add("Description", "Common EC2 key pair for SSH access for SSM");

    // Output of the common ec2 key pair parameter name in Parameter Store
    new CfnOutput(this, "common-ec2-key-pair-parameter-name", {
      value: keyPair.privateKey.parameterName,
      description: "Common EC2 key pair for SSH access for SSM",
    });

    return keyPair;
  }

  private createCluster(clusterMetadata: Cluster, commonKeyPair: ec2.KeyPair) {
    const {
      name: clusterName,
      vpc: vpcData,
      tags,
      version: clusterVersion,
      nodeGroups,
      hostedZones,
      private: isPrivateCluster,
      isolated: isClusterIsolated,
      teams,
    } = clusterMetadata;

    // Get the tags attached to this stack
    const environmentTags = this.props.environment?.tags ?? {};
    const environmentTagsStr = Object.fromEntries(
      Object.entries(environmentTags).map(([key, value]) => [key, `${value}`])
    );

    const tagsStr = Object.fromEntries(Object.entries(tags ?? {}).map(([key, value]) => [key, `${value}`]));

    // Read the enx-max-pod.txt and generate a hash table of instance limits
    // https://github.com/awslabs/amazon-eks-ami/blob/main/templates/shared/runtime/eni-max-pods.txt
    const enxMaxPods = fs
      .readFileSync(path.join(__dirname, "scripts/eni-max-pods.txt"), {
        encoding: "utf-8",
      })
      .split("\n")
      .filter(line => !line.startsWith("#"))
      .map(line => line.split(" "))
      .reduce((acc, [key, value]) => {
        acc[key] = value;
        return acc;
      }, {} as { [key: string]: string });

    console.info(`Cluster Isolation Mode : ${(vpcData.isolated && isClusterIsolated) ?? false}`);

    const vpc = ec2.Vpc.fromLookup(this, `VPC-${clusterName}`, {
      vpcId: vpcData.id,
    });

    const clusterSubnetFilter = {
      subnetType:
        vpcData.isolated && isClusterIsolated ? ec2.SubnetType.PRIVATE_ISOLATED : ec2.SubnetType.PRIVATE_WITH_EGRESS,
      subnetFilters: [ec2.SubnetFilter.byIds((vpcData.subnets ?? []).map(subnet => subnet.id))],
    };

    const clusterKey = blueprints.getResource(({ scope }) => {
      const key = new kms.Key(scope, `${scope.node.id}-key-cluster`, {
        alias: `eks/${clusterName}/default`,
        removalPolicy: RemovalPolicy.DESTROY,
        pendingWindow: Duration.days(7),
        enableKeyRotation: true,
        description: "KMS key for EKS cluster, mostly used for EKS Secrets",
      });
      return key;
    });

    const clusterDataKey = blueprints.getResource(({ scope }) => {
      const key = new kms.Key(scope, `${scope.node.id}-key-cluster-data`, {
        alias: `eks/${clusterName}/storage/default`,
        removalPolicy: RemovalPolicy.DESTROY,
        pendingWindow: Duration.days(7),
        description: "KMS key for EKS cluster workload data",
        enableKeyRotation: true,
      });
      return key;
    });

    const { helm, docker } = this.props;

    const blueprintsAddons: blueprints.ClusterAddOn[] = [
      new blueprints.addons.VpcCniAddOn({
        eniConfigLabelDef: "topology.kubernetes.io/zone",
        serviceAccountPolicies: [iam.ManagedPolicy.fromAwsManagedPolicyName("AmazonEKS_CNI_Policy")],
        enablePodEni: true,
        enableNetworkPolicy: true,
        warmIpTarget: 2,
        minimumIpTarget: 20,
        awsVpcK8sCniLogFile: "stderr",
        awsVpcK8sPluginLogFile: "stderr",
      }),
      new blueprints.addons.CoreDnsAddOn(),
      new blueprints.addons.KubeProxyAddOn(),
      new blueprints.addons.CloudWatchInsights({
        ebsPerformanceLogs: true,
      }),
    ];

    if (this.props.environment.proxy) {
      const { httpProxy = "", httpsProxy = "", noProxy } = this.props.environment.proxy;

      const noProxyStr = this.createNoProxyString(noProxy);

      const proxyAddonConfig: VpcCniProxyPatchAddonProps = {
        proxy: {
          httpProxy,
          httpsProxy,
          noProxy: noProxyStr,
        },
      };

      blueprintsAddons.push(new VpcCniProxyPatchAddon(proxyAddonConfig));
      console.warn("Adding Proxy Patch");
    }

    // Add each addons based on options
    /**
     * Metric Server
     */
    {
      const chart = helm?.charts.find(chart => chart.chartName === "metrics-server");
      if (chart) {
        const { chartName, images, repositoryUrl: chartRepository, version: chartVersion } = chart;
        const values: blueprints.Values = {
          image: {
            repository: images.find(image => image.repository.includes("metrics-server"))?.repository,
            tag: images.find(image => image.repository.includes("metrics-server"))?.tag,
          },
          addonResizer: {
            image: {
              repository: images.find(image => image.repository.includes("addon-resizer"))?.repository,
              tag: images.find(image => image.repository.includes("addon-resizer"))?.tag,
            },
          },
        };

        blueprintsAddons.push(
          new blueprints.addons.MetricsServerAddOn({
            repository: chartRepository,
            version: chartVersion,
            values,
          })
        );
      } else {
        blueprintsAddons.push(new blueprints.addons.MetricsServerAddOn());
      }
    }

    /**
     * AWS Load Balancer Controller
     */
    {
      const extraEnvVars: { name: string; value: string }[] = this.createHttpProxyEnv();

      const extraEnvVarsFlat = extraEnvVars.reduce((acc, { name, value }) => {
        acc[name] = value;
        return acc;
      }, {} as { [key: string]: string });

      const chart = helm?.charts.find(chart => chart.chartName === "aws-load-balancer-controller");
      if (chart) {
        const { chartName, images, repositoryUrl: chartRepository, version: chartVersion } = chart;
        const values: blueprints.Values = {
          image: {
            repository: images.find(image => image.repository.includes("aws-load-balancer-controller"))?.repository,
            tag: images.find(image => image.repository.includes("aws-load-balancer-controller"))?.tag,
          },
          defaultSSLPolicy: "ELBSecurityPolicy-TLS13-1-2-FIPS-2023-04",
        };

        if (isClusterIsolated) {
          values["enableShield"] = false;
          values["enableWaf"] = false;
          values["enableWafv2"] = false;
        }

        blueprintsAddons.push(
          new blueprints.addons.AwsLoadBalancerControllerAddOn({
            repository: chartRepository,
            version: chartVersion,
            values: Object.assign(
              values,
              this.props.environment.proxy
                ? { env: extraEnvVarsFlat, defaultTags: { ...environmentTagsStr, ...tagsStr } }
                : { defaultTags: { ...environmentTagsStr, ...tagsStr } }
            ),
          })
        );
      } else {
        blueprintsAddons.push(
          new blueprints.addons.AwsLoadBalancerControllerAddOn({
            values: this.props.environment.proxy
              ? { env: extraEnvVarsFlat, defaultTags: { ...environmentTagsStr, ...tagsStr } }
              : { defaultTags: { ...environmentTagsStr, ...tagsStr } },
          })
        );
      }
    }

    /**
     * Cert Manager
     */
    {
      const chart = helm?.charts.find(chart => chart.chartName === "cert-manager");
      if (chart) {
        const { chartName, images, repositoryUrl: chartRepository, version: chartVersion } = chart;
        const values: blueprints.Values = {
          image: {
            repository: images.find(image => image.repository.includes("cert-manager-controller"))?.repository,
            tag: images.find(image => image.repository.includes("cert-manager-controller"))?.tag,
          },
          cainjector: {
            image: {
              repository: images.find(image => image.repository.includes("cert-manager-cainjector"))?.repository,
              tag: images.find(image => image.repository.includes("cert-manager-cainjector"))?.tag,
            },
          },
          webhook: {
            image: {
              repository: images.find(image => image.repository.includes("cert-manager-webhook"))?.repository,
              tag: images.find(image => image.repository.includes("cert-manager-webhook"))?.tag,
            },
          },
          startupapicheck: {
            image: {
              repository: images.find(image => image.repository.includes("cert-manager-startupapicheck"))?.repository,
              tag: images.find(image => image.repository.includes("cert-manager-startupapicheck"))?.tag,
            },
          },
        };

        blueprintsAddons.push(
          new blueprints.addons.CertManagerAddOn({
            repository: chartRepository,
            version: chartVersion,
            values,
          })
        );
      } else {
        blueprintsAddons.push(new blueprints.addons.CertManagerAddOn());
      }
    }

    /**
     * Cluster Autoscaler
     */
    {
      const chart = helm?.charts.find(chart => chart.chartName === "cluster-autoscaler");
      if (chart) {
        const { chartName, images, repositoryUrl: chartRepository, version: chartVersion } = chart;
        const values: blueprints.Values = {
          image: {
            repository: images.find(image => image.repository.includes("cluster-autoscaler"))?.repository,
            tag: images.find(image => image.repository.includes("cluster-autoscaler"))?.tag,
          },
        };

        if (isClusterIsolated) {
          values["customArgs"] = ["--aws-use-static-instance-list=true"];
        }

        blueprintsAddons.push(
          new blueprints.addons.ClusterAutoScalerAddOn({
            repository: chartRepository,
            version: chartVersion,
            values,
          })
        );
      } else {
        blueprintsAddons.push(new blueprints.addons.ClusterAutoScalerAddOn());
      }
    }

    /**
     * ACK Controller
     */
    {
      const ackDefaultValues = {
        resourceTags: [
          ...Object.entries({ ...environmentTagsStr, ...tagsStr }).flatMap(item => `${item[0]}=${item[1]}`),
          "Managed By=eks-ack-controller",
          `eks:cluster-name=${clusterName}`,
        ],
      };

      // Security Groups - creates the namespace
      const ec2AckAddon = new AckAddOn({
        createNamespace: true,
        namespace: "ack-system",
        serviceName: blueprints.AckServiceName.EC2,
        values: ackDefaultValues,
        inlinePolicyStatements: [
          new iam.PolicyStatement({
            sid: "AllowSubnetAccess",
            actions: ["ec2:CreateSubnet", "ec2:DeleteSubnet", "ec2:DescribeSubnets", "ec2:ModifySubnetAttribute"],
            resources: ["*"],
          }),
          new iam.PolicyStatement({
            actions: ["ec2:CreateTags", "ec2:DescribeTags"],
            resources: ["*"],
          }),
          new iam.PolicyStatement({
            sid: "AllowCreateSecurityGroupWithPrefix",
            actions: ["ec2:CreateSecurityGroup"],
            resources: ["*"],
          }),
          new iam.PolicyStatement({
            sid: "AllowDeleteSecurityGroupWithPrefix",
            actions: ["ec2:DeleteSecurityGroup"],
            resources: ["*"],
            conditions: {
              StringLike: {
                "ec2:ResourceTag/Name": "eks-ack-*",
              },
            },
          }),
          // Restrict other actions to eks-ack-* security groups
          new iam.PolicyStatement({
            actions: ["ec2:*SecurityGroup*"],
            resources: ["*"],
            conditions: {
              StringLike: {
                "aws:ResourceTag/Name": "eks-ack-*",
              },
            },
          }),

          // Generic Security Read Only Access
          new iam.PolicyStatement({
            actions: ["ec2:DescribeSecurityGroups"],
            resources: ["*"],
          }),
        ],
      });
      blueprintsAddons.push(ec2AckAddon);

      // Secret Manager - depends on namespace creation
      const secretsManagerAckAddon = new AckAddOn({
        createNamespace: false,
        namespace: "ack-system",
        serviceName: blueprints.AckServiceName.SECRETSMANAGER,
        values: ackDefaultValues,
        inlinePolicyStatements: [
          new iam.PolicyStatement({
            actions: ["secretsmanager:*"],
            resources: ["arn:*:secretsmanager:*:*:secret:*eks-ack-*"],
          }),
        ],
      });
      blueprintsAddons.push(secretsManagerAckAddon);

      // RDS - depends on namespace creation
      const rdsAckAddon = new AckAddOn({
        createNamespace: false,
        namespace: "ack-system",
        serviceName: blueprints.AckServiceName.RDS,
        values: ackDefaultValues,
        inlinePolicyStatements: [
          new iam.PolicyStatement({
            actions: [
              "rds:CreateDBInstance",
              "rds:DeleteDBInstance",
              "rds:ModifyDBInstance",
              "rds:RebootDBInstance",
              "rds:StartDBInstance",
              "rds:StopDBInstance",
              "rds:CreateDBCluster",
              "rds:DeleteDBCluster",
              "rds:ModifyDBCluster",
              "rds:CreateDBSubnetGroup",
              "rds:DeleteDBSubnetGroup",
              "rds:ModifyDBSubnetGroup",
              "rds:CreateDBParameterGroup",
              "rds:DeleteDBParameterGroup",
              "rds:ModifyDBParameterGroup",
              "rds:CreateDBSnapshot",
              "rds:DeleteDBSnapshot",
              "rds:AddTagsToResource",
              "rds:RemoveTagsFromResource",
              "rds:ListTagsForResource",
              "rds:CreateTags",
            ],
            resources: ["*"],
          }),
          new iam.PolicyStatement({
            actions: ["rds:Describe*", "rds:List*"],
            resources: ["*"],
          }),
          new iam.PolicyStatement({
            actions: ["kms:Decrypt", "kms:DescribeKey", "kms:Encrypt", "kms:GenerateDataKey", "kms:ReEncrypt*"],
            resources: ["*"],
          }),
          new iam.PolicyStatement({
            actions: [
              "secretsmanager:CreateSecret",
              "secretsmanager:DeleteSecret",
              "secretsmanager:DescribeSecret",
              "secretsmanager:GetSecretValue",
              "secretsmanager:PutSecretValue",
              "secretsmanager:UpdateSecret",
              "secretsmanager:TagResource",
            ],
            resources: ["arn:*:secretsmanager:*:*:secret:rds!*"],
          }),
          new iam.PolicyStatement({
            actions: ["iam:CreateServiceLinkedRole"],
            resources: ["arn:*:iam::*:role/aws-service-role/rds.amazonaws.com/AWSServiceRoleForRDS"],
            conditions: {
              StringLike: {
                "iam:AWSServiceName": "rds.amazonaws.com",
              },
            },
          }),
        ],
      });
      blueprintsAddons.push(rdsAckAddon);
    }

    /**
     * Kubernetes Secrets Store CSI Driver
     */

    const clusterTeams: blueprints.Team[] = [];

    {
      const chart = helm?.charts.find(chart => chart.chartName === "secrets-store-csi-driver");
      if (chart) {
        const { chartName, images, repositoryUrl: chartRepository, version: chartVersion } = chart;
        const values: blueprints.Values = {
          linux: {
            image: {
              repository: images.find(image => image.repository.includes("driver"))?.repository,
              tag: images.find(image => image.repository.includes("driver"))?.tag,
            },
            crds: {
              image: {
                repository: images.find(image => image.repository.includes("driver-crds"))?.repository,
                tag: images.find(image => image.repository.includes("driver-crds"))?.tag,
              },
            },
            registrarImage: {
              repository: images.find(image => image.repository.includes("csi-node-driver-registrar"))?.repository,
              tag: images.find(image => image.repository.includes("csi-node-driver-registrar"))?.tag,
            },
            livenessProbeImage: {
              repository: images.find(image => image.repository.includes("livenessprobe"))?.repository,
              tag: images.find(image => image.repository.includes("livenessprobe"))?.tag,
            },
          },
        };

        blueprintsAddons.push(
          new blueprints.addons.SecretsStoreAddOn({
            repository: chartRepository,
            version: chartVersion,
            values,
          })
        );
      } else {
        blueprintsAddons.push(new blueprints.addons.SecretsStoreAddOn());
      }

      // Parse the configuration file for teams and process for secrets
      if (teams?.length > 0) {
        teams.forEach(
          ({
            name,
            type,
            namespace,
            namespaceAnnotations,
            namespaceHardLimits,
            namespaceLabels,
            secrets,
            serviceAccountName,
          }) => {
            const teamClassType = type == "application" ? blueprints.ApplicationTeam : blueprints.PlatformTeam;
            const teamSecrets: blueprints.CsiSecretProps[] = [];

            secrets?.forEach(({ secretName, secretArn, lookUpType, secretType, metadata }) => {
              let secretProvider: blueprints.SecretProvider;
              let secretTypeClass: blueprints.KubernetesSecretType = blueprints.KubernetesSecretType.OPAQUE;

              switch (lookUpType) {
                case "arn":
                  if (secretArn)
                    secretProvider = new blueprints.LookupSecretsManagerSecretByArn(
                      secretArn,
                      `${clusterName}-lookup-${secretArn}`
                    );
                  break;
                case "name":
                  secretProvider = new blueprints.LookupSecretsManagerSecretByName(
                    secretArn ?? secretName,
                    `${clusterName}-lookup-${secretArn ?? secretName}`
                  );
                  break;
                case "attr":
                  throw new Error(
                    `Not implemented for secrets: ${lookUpType} for team: ${name} in cluster: ${clusterName}`
                  );
                default:
                  throw new Error(
                    `Unable to determine lookup type for secrets: ${lookUpType} for team: ${name} in cluster: ${clusterName}`
                  );
              }

              switch (secretType) {
                case "kubernetes.io/basic-auth":
                  secretTypeClass = blueprints.KubernetesSecretType.BASIC_AUTH;
                  break;
                case "bootstrap.kubernetes.io/token":
                  secretTypeClass = blueprints.KubernetesSecretType.TOKEN;
                  break;
                case "kubernetes.io/dockerconfigjson":
                  secretTypeClass = blueprints.KubernetesSecretType.DOCKER_CONFIG_JSON;
                  break;
                case "kubernetes.io/dockercfg":
                  secretTypeClass = blueprints.KubernetesSecretType.DOCKER_CONFIG;
                  break;
                case "kubernetes.io/ssh-auth":
                  secretTypeClass = blueprints.KubernetesSecretType.SSH_AUTH;
                  break;
                case "kubernetes.io/service-account-token":
                  secretTypeClass = blueprints.KubernetesSecretType.SERVICE_ACCOUNT_TOKEN;
                  break;
                case "kubernetes.io/tls":
                  secretTypeClass = blueprints.KubernetesSecretType.TLS;
                  break;
                case "Opaque":
                default:
                  // Default to Opaque Type
                  break;
              }

              if (secretProvider!) {
                const teamSecret: blueprints.CsiSecretProps = {
                  secretProvider,
                  jmesPath: metadata.jmesPath ?? [],
                  kubernetesSecret: {
                    type: secretTypeClass,
                    secretName,
                    data: metadata.data ?? [],
                  },
                };

                teamSecrets.push(teamSecret);
              }
            });

            const clusterTeam = new teamClassType({
              name,
              namespace,
              namespaceAnnotations,
              namespaceHardLimits,
              namespaceLabels,
              teamSecrets,
              serviceAccountName,
            });

            clusterTeams.push(clusterTeam);
          }
        );
      }
    }

    const managedNodeGroupRole = blueprints.getResource(({ scope }) => {
      const role = new iam.Role(scope, `${clusterName}-managed-nodeGroup-role`, {
        roleName: `${clusterName}-managed-worker-node-role`,
        description: "Base Managed node group role for EKS EC2 Worker nodes",

        assumedBy: new iam.ServicePrincipal("ec2.amazonaws.com"),
        managedPolicies: [
          iam.ManagedPolicy.fromAwsManagedPolicyName("AmazonEC2ContainerRegistryReadOnly"),
          iam.ManagedPolicy.fromAwsManagedPolicyName("AmazonEKS_CNI_Policy"),
          iam.ManagedPolicy.fromAwsManagedPolicyName("AmazonEKSWorkerNodePolicy"),
          iam.ManagedPolicy.fromAwsManagedPolicyName("AmazonSSMManagedInstanceCore"),
        ],
      });

      return role;
    });

    const managedNodeGroups = nodeGroups.map(
      (
        {
          name: nodeGroupName,
          ami,
          instanceType,
          desiredCapacity,
          minSize,
          maxSize,
          labels,
          tags,
          taints,
          storage,
          subnets: nodeGroupSubnets,
          isolated: useNodeIsolatedSubnets,
        },
        index
      ): blueprints.ManagedNodeGroup => {
        const nodeWorkerImage = ami
          ? ec2.MachineImage.lookup({
              name: "*",
              filters: Object.fromEntries(Object.entries(ami).map(([key, value]) => [key, [value]])),
            })
          : undefined;

        if (nodeWorkerImage)
          console.info(`[${clusterName}/${nodeGroupName}] - Node Image: ${nodeWorkerImage.getImage(this).imageId}`);
        else console.info(`[${clusterName}/${nodeGroupName}] - Node Image: DEFAULT`);

        const workerNodeRootKmsKey =
          storage?.encrypted && storage.kmsKeyId
            ? blueprints.getResource(({ scope }) => {
                return kms.Key.fromKeyArn(scope, `${this.node.id}-root-storage-key-${index}`, storage.kmsKeyId!);
              })
            : undefined;

        if (storage?.encrypted === false) {
          console.warn(`Node - ${nodeGroupName} is configured to have an unencrypted root storage`);
        }

        const blockDevices = [
          {
            deviceName: storage?.rootDeviceName ?? "/dev/xvda",
            volume: ec2.BlockDeviceVolume.ebs(storage?.sizeInGB ?? 20, {
              encrypted: storage?.encrypted ?? true,
              kmsKey: workerNodeRootKmsKey,
              deleteOnTermination: true,
              volumeType: this.getVolumeType(storage),
            }),
          },
        ];

        const eksLaunchTemplate = blueprints.getResource(({ scope }) => {
          const userData = ec2.UserData.forLinux();

          const maxPodsLimit = enxMaxPods[instanceType] ?? "15";

          const userDataCollection: string[] = [];

          let rawUserData = fs.readFileSync(path.join(__dirname, "scripts/worker-node-userdata.sh"), {
            encoding: "utf-8",
          });

          rawUserData = rawUserData.replace("{{clusterName}}", clusterName);
          rawUserData = rawUserData.replace("{{MAX_PODS}}", maxPodsLimit);

          if (this.props.environment.proxy) {
            const { httpProxy = "", httpsProxy = "", noProxy } = this.props.environment.proxy;

            const noProxyStr = this.createNoProxyString(noProxy);

            let rawProxyUserdata = fs
              .readFileSync(path.join(__dirname, "scripts/proxy-userdata.sh"), {
                encoding: "utf-8",
              })
              .replace(/{{HTTP_PROXY}}/g, httpProxy)
              .replace(/{{HTTPS_PROXY}}/g, httpsProxy)
              .replace(/{{NO_PROXY}}/g, noProxyStr);

            let rawProxyWorkerUserdata = fs.readFileSync(
              path.join(__dirname, "scripts/proxy-worker-node-userdata.sh"),
              {
                encoding: "utf-8",
              }
            );

            userDataCollection.push(rawProxyUserdata);
            userDataCollection.push(rawProxyWorkerUserdata);
          }

          userDataCollection.push(rawUserData);

          userData.addCommands(
            ...userDataCollection
              .join("\n")
              .split("\n")
              .filter(line => line.length != 0)
          );

          const keyPair = ec2.KeyPair.fromKeyPairAttributes(
            scope,
            `${scope.node.id}-cluster-ec2-KeyPair-${nodeGroupName}`,
            {
              keyPairName: (commonKeyPair.node.defaultChild as ec2.IKeyPair).keyPairName,
            }
          );

          const template = new ec2.LaunchTemplate(scope, `${clusterName}-lt-${nodeGroupName}`, {
            machineImage: nodeWorkerImage,
            userData: nodeWorkerImage ? userData : undefined,
            launchTemplateName: `${clusterName}-lt-${nodeGroupName}`,
            httpTokens: ec2.LaunchTemplateHttpTokens.REQUIRED,
            httpPutResponseHopLimit: 2,
            ebsOptimized: true,
            blockDevices,
            keyPair: keyPair,
          });

          return template;
        });

        console.debug(`[${nodeGroupName}] maxSize: ${maxSize}`);
        console.debug(`[${nodeGroupName}] minSize: ${minSize}`);
        console.debug(`[${nodeGroupName}] desiredCapacity: ${desiredCapacity}`);

        const nodeGroupSubnetFilter = nodeGroupSubnets
          ? {
              subnetType: useNodeIsolatedSubnets ? ec2.SubnetType.PRIVATE_ISOLATED : ec2.SubnetType.PRIVATE_WITH_EGRESS,
              subnetFilters: [ec2.SubnetFilter.byIds((nodeGroupSubnets ?? []).map(subnet => subnet.id))],
            }
          : clusterSubnetFilter;

        return {
          id: nodeGroupName,
          instanceTypes: [new ec2.InstanceType(instanceType)],
          launchTemplateSpec: {
            id: eksLaunchTemplate.launchTemplateId ?? "N/A",
            version: eksLaunchTemplate.defaultVersionNumber,
          },
          nodeGroupSubnets: nodeGroupSubnetFilter,
          minSize: minSize,
          desiredSize: desiredCapacity,
          maxSize: maxSize,
          labels,
          tags,
          nodeRole: managedNodeGroupRole,
          taints: taints?.map(({ key, value, effect: effectStr }) => {
            let effect = eks.TaintEffect.PREFER_NO_SCHEDULE;

            switch (effectStr) {
              case "NO_SCHEDULE":
                effect = eks.TaintEffect.NO_SCHEDULE;
                break;
              case "NO_EXECUTE":
                effect = eks.TaintEffect.NO_EXECUTE;
                break;
            }
            return { key, value, effect };
          }),
        };
      }
    );

    const clusterMasterRole = blueprints.getResource(({ scope }) => {
      const role = new iam.Role(scope, `${scope.node.id}-admin-role`, {
        roleName: `ClusterAdminRole-${clusterName}`,
        description: `Admin Role for Cluster: ${clusterName}`,
        assumedBy: new iam.AccountRootPrincipal(),
      });

      Tags.of(role).add("eks:cluster-name", clusterName);

      return role;
    });

    const clusterRole = blueprints.getResource(({ scope }) => {
      const role = new iam.Role(scope, `${clusterName}-cluster-role`, {
        roleName: `${clusterName}-cluster-role`,
        description: `Cluster IAM Role for EKS Cluster: ${clusterName}`,
        assumedBy: new iam.ServicePrincipal("eks.amazonaws.com"),
        managedPolicies: [
          iam.ManagedPolicy.fromAwsManagedPolicyName("AmazonEKSClusterPolicy"),
          iam.ManagedPolicy.fromAwsManagedPolicyName("AmazonEKSVPCResourceController"),
        ],
      });

      Tags.of(role).add("eks:cluster-name", clusterName);

      return role;
    });

    // Add an additional security group to the cluster
    const clusterSecurityGroup = blueprints.getResource(({ scope }) => {
      const securityGroup = new ec2.SecurityGroup(scope, `eks-${clusterName}-security-group`, {
        vpc: vpc,
        securityGroupName: `eks-cluster-sg-${clusterName}-security-group`,
        description: `EKS Control Plane Security Group for EKS Cluster: ${clusterName}`,
        allowAllOutbound: true,
      });

      securityGroup.addIngressRule(
        securityGroup,
        ec2.Port.HTTPS,
        "Grant Inbound access to anyone who has this security group"
      );

      Tags.of(securityGroup).add("eks:cluster-name", clusterName);
      Tags.of(securityGroup).add("Name", `sg-eks-cluster-${clusterName}`);

      return securityGroup;
    });

    const clusterProvider = new blueprints.GenericClusterProvider({
      version: clusterVersion ? eks.KubernetesVersion.of(clusterVersion) : eks.KubernetesVersion.V1_30,
      endpointAccess: isPrivateCluster ? eks.EndpointAccess.PRIVATE : eks.EndpointAccess.PUBLIC_AND_PRIVATE,
      privateCluster: isPrivateCluster ?? false,
      isolatedCluster: isClusterIsolated ?? false,
      clusterName,
      authenticationMode: eks.AuthenticationMode.API_AND_CONFIG_MAP,
      vpcSubnets: [clusterSubnetFilter],
      mastersRole: clusterMasterRole,
      role: clusterRole,
      secretsEncryptionKey: clusterKey,
      managedNodeGroups,
      clusterLogging: [
        eks.ClusterLoggingTypes.API,
        eks.ClusterLoggingTypes.AUDIT,
        eks.ClusterLoggingTypes.AUTHENTICATOR,
        eks.ClusterLoggingTypes.CONTROLLER_MANAGER,
        eks.ClusterLoggingTypes.SCHEDULER,
      ],
      placeClusterHandlerInVpc: (isClusterIsolated || isPrivateCluster) ?? false,
      securityGroup: clusterSecurityGroup,
      tags,
    });

    const eksBuilder = blueprints.EksBlueprint.builder();

    // Generate external-dns addon configuration
    if (hostedZones) {
      const privateHostedZones = hostedZones.filter(hostedZones => hostedZones.private);
      const publicHostedZones = hostedZones.filter(hostedZones => !hostedZones.private);

      let externalDnsConfig: blueprints.addons.ExternalDnsProps = {
        hostedZoneResources: hostedZones.map(({ zoneName }) => zoneName),
        values: {
          provider: {
            name: "aws",
          },
          logLevel: "debug",
          policy: "sync",
        },
      };

      if (privateHostedZones.length > 0) {
        externalDnsConfig.values = {
          ...externalDnsConfig.values,
          ...{
            extraArgs: ["--aws-zone-type=private"],
            txtPrefix: "txt-",
          },
        };

        if (this.props.environment.proxy) {
          const extraEnvVars: { name: string; value: string }[] = this.createHttpProxyEnv();

          Object.assign(externalDnsConfig.values, {
            env: extraEnvVars,
          });
        }
      }

      if (publicHostedZones.length > 0 && privateHostedZones.length > 0) {
        console.warn("Unsupported Capability for external-dns ...");
        console.warn("Cannot have both private and public hosted zones in the same cluster");
        console.warn("Only private hosted zones are prioritized");
      }

      /**
       * External DNS
       */
      {
        const chart = helm?.charts.find(chart => chart.chartName === "external-dns");
        if (chart) {
          const { chartName, images, repositoryUrl: chartRepository, version: chartVersion } = chart;

          if (isClusterIsolated) {
          }

          Object.assign(externalDnsConfig, {
            repository: chartRepository,
            version: chartVersion,
            values: {
              ...externalDnsConfig.values,
              image: {
                repository: images.find(image => image.repository.includes("external-dns"))?.repository,
                tag: images.find(image => image.repository.includes("external-dns"))?.tag,
              },
              // provider: {
              //   webhook: {
              //     repository: images.find(image => image.repository.includes("webhook"))?.repository,
              //     tag: images.find(image => image.repository.includes("webhook"))?.tag,
              //   },
              // },
            },
          });
        }
      }

      blueprintsAddons.push(new blueprints.addons.ExternalDnsAddOn(externalDnsConfig));

      hostedZones.forEach(hostedZones => {
        // Check extended data for generated hosted zone

        const { zoneName, private: isPrivateHostedZone } = hostedZones;
        const { extended } = this.props;

        const stackHostedZones = extended.hostedZones;

        console.warn(`Looking of hosted zone: ${zoneName}`);

        const results = stackHostedZones
          .filter(hostedZone => hostedZone.zoneName === zoneName)
          .filter(hostedZone => hostedZone.private);

        if (results.length > 1) {
          console.warn(`Found multiple hosted zones with the same name ${zoneName} and private property set to true`);
        }

        if (results.length > 0) {
          console.info(`Found hosted zone ${zoneName} in extended data`);
        }

        eksBuilder.resourceProvider(
          zoneName,
          new LookupHostedZoneProvider({
            domainName: zoneName,
            privateZone: isPrivateHostedZone,
            vpcId: isPrivateHostedZone ? vpc.vpcId : undefined,
          })
        );
      });
    }

    /**4
     * Nginx Ingress Controller
     */
    {
      const chart = helm?.charts.find(chart => chart.chartName === "nginx-ingress");
      if (chart) {
        const { chartName, images, repositoryUrl: chartRepository, version: chartVersion } = chart;

        const nginxControllerConfig: blueprints.addons.NginxAddOnProps = {
          repository: chartRepository,
          version: chartVersion,
          internetFacing: !isClusterIsolated,
          values: {
            controller: {
              image: {
                repository: images.find(image => image.repository.includes("nginx-ingress"))?.repository,
                tag: images.find(image => image.repository.includes("nginx-ingress"))?.tag,
              },
            },
          },
        };

        blueprintsAddons.push(new blueprints.addons.NginxAddOn(nginxControllerConfig));
      } else if (isClusterIsolated) {
        // Add NGINX addon ONLY for isolated clusters where ALB is not available
        blueprintsAddons.push(
          new blueprints.addons.NginxAddOn({
            internetFacing: false,
          })
        );
      }
    }

    const dynamicAddons: blueprints.ClusterAddOn[] = [
      new blueprints.addons.EbsCsiDriverAddOn({
        version: "auto",
        storageClass: undefined,
        kmsKeys: [clusterDataKey],
        configurationValues: {
          controller: {
            extraVolumeTags: {
              ...environmentTagsStr,
              ...tagsStr,
              "Managed By": "eks-ebs-csi-controller",
              "eks:cluster-name": `${clusterName}`,
            },
          },
        },
      }),
      new StorageClassDefaultAddon({
        storageClassPaths: globSync(`**/*.{yaml,yml}`, {
          cwd: path.resolve(__dirname, "..", "k8s/base/classes/storage"),
          absolute: true,
          ignore: ["*.disabled.{yaml,yml}", "kustomization.{yaml,yml}"],
        }),
        kmsKey: clusterDataKey,
      }),
    ];

    /**
     * Elastic File System CSI Driver
     */
    {
      const chart = helm?.charts.find(chart => chart.chartName === "aws-efs-csi-driver");
      if (chart) {
        const { chartName, images, repositoryUrl: chartRepository, version: chartVersion } = chart;

        const values: blueprints.Values = {
          image: {
            repository: images.find(image => image.repository.includes("aws-efs-csi-driver"))?.repository,
            tag: images.find(image => image.repository.includes("aws-efs-csi-driver"))?.tag,
          },
          sidecars: {
            livenessProbe: {
              image: {
                repository: images.find(image => image.repository.includes("livenessprobe"))?.repository,
                tag: images.find(image => image.repository.includes("livenessprobe"))?.tag,
              },
            },
            nodeDriverRegistrar: {
              image: {
                repository: images.find(image => image.repository.includes("node-driver-registrar"))?.repository,
                tag: images.find(image => image.repository.includes("node-driver-registrar"))?.tag,
              },
            },
            csiProvisioner: {
              image: {
                repository: images.find(image => image.repository.includes("external-provisioner"))?.repository,
                tag: images.find(image => image.repository.includes("external-provisioner"))?.tag,
              },
            },
          },
          useFIPS: false,
        };

        blueprintsAddons.push(
          new blueprints.addons.EfsCsiDriverAddOn({
            repository: chartRepository,
            version: chartVersion,
            values,
            kmsKeys: [clusterDataKey],
          })
        );
      } else {
        blueprintsAddons.push(
          new blueprints.addons.EfsCsiDriverAddOn({
            kmsKeys: [clusterDataKey],
          })
        );
      }
    }

    const clusterStack = eksBuilder
      .clusterProvider(clusterProvider)
      .region(this.props.environment?.region)
      .account(this.props.environment?.account)
      .teams(...clusterTeams)
      .resourceProvider(blueprints.GlobalResources.Vpc, new blueprints.DirectVpcProvider(vpc))
      .addOns(...blueprintsAddons, ...dynamicAddons)
      .useDefaultSecretEncryption(false)
      .build(this, `cluster-${clusterName}-stack`, {
        description: `Stack to create EKS Cluster: ${clusterName}`,
        synthesizer: this.props.environment?.synthesizeOverride
          ? new DefaultStackSynthesizer(this.props.environment.synthesizeOverride)
          : undefined,
      });

    if (isPrivateCluster) {
      new CfnOutput(clusterStack, `Cluster-${clusterName}-PrivateAccess`, {
        description: `Sample alternative access to Private Cluster Endpoint - ${clusterName} via SSM, Dynamic Port Forwarding`,
        value: `kubectl config set-cluster ${
          clusterStack.getClusterInfo().cluster.clusterArn
        } --proxy-url socks5://localhost:8080`,
      });
    }

    new CfnOutput(clusterStack, `Cluster-${clusterName}-ARN`, {
      value: clusterStack.getClusterInfo().cluster.clusterArn,
      description: `Cluster ARN of Cluster: ${clusterName}`,
    });

    return clusterStack;
  }

  private createHttpProxyEnv() {
    const extraEnvVars: { name: string; value: string }[] = [];

    if (this.props.environment.proxy) {
      const { httpProxy = "", httpsProxy = "", noProxy } = this.props.environment.proxy;

      const noProxyStr = this.createNoProxyString(noProxy);

      extraEnvVars.push(
        {
          name: "HTTP_PROXY",
          value: httpProxy,
        },
        {
          name: "HTTPS_PROXY",
          value: httpsProxy,
        },
        {
          name: "NO_PROXY",
          value: noProxyStr,
        }
      );

      extraEnvVars.forEach(({ name, value }) => {
        extraEnvVars.push({
          name: name.toLowerCase(),
          value: value,
        });
      });
    }

    return extraEnvVars;
  }

  private createNoProxyString(noProxy: string | string[] | undefined) {
    let noProxyStr = "";

    if (noProxy) {
      if (Array.isArray(noProxy)) {
        noProxyStr = noProxy.join(",");
      } else {
        noProxyStr = noProxy;
      }
    }
    return noProxyStr;
  }

  private getVolumeType(storage?: { rootDeviceName: string; sizeInGB: number; type: string }): ec2.EbsDeviceVolumeType {
    let volumeType = ec2.EbsDeviceVolumeType.GP3;

    switch (storage?.type) {
      case "gp2":
        volumeType = ec2.EbsDeviceVolumeType.GP2;
        break;

      case "io1":
        volumeType = ec2.EbsDeviceVolumeType.IO1;
        break;

      case "st1":
        volumeType = ec2.EbsDeviceVolumeType.ST1;
        break;

      case "sc1":
        volumeType = ec2.EbsDeviceVolumeType.SC1;
        break;

      case "standard":
        volumeType = ec2.EbsDeviceVolumeType.GP2;
        break;

      case "io2":
        volumeType = ec2.EbsDeviceVolumeType.IO2;
        break;
    }
    return volumeType;
  }
}
