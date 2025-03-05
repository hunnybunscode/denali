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
} from "aws-cdk-lib";

import { globSync } from "glob";
import * as blueprints from "@aws-quickstart/eks-blueprints";
import { StorageClassDefaultAddon } from "./eks-blueprints/addons/storage-class-default-addon";

import { NagSuppressions } from "cdk-nag";

export interface EksClustersConstructProps extends StackProps, Document {
  keyPair: ec2.IKeyPair;
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

    for (const clusterMetadata of clusters) {
      const clusterStack = this.createCluster(clusterMetadata, env);
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

  private createCluster(clusterMetadata: Cluster, environment?: Omit<Environment, "name">) {
    const {
      name: clusterName,
      vpc: vpcData,
      tags,
      version: clusterVersion,
      nodeGroups,
      hostedZones,
      private: isPrivateCluster,
    } = clusterMetadata;

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

    const vpc = ec2.Vpc.fromLookup(this, `VPC-${clusterName}`, {
      vpcId: vpcData.id,
    });

    const clusterSubnetFilter = {
      subnetType: ec2.SubnetType.PRIVATE_WITH_EGRESS,
      subnetFilters: [ec2.SubnetFilter.byIds((vpcData.subnets ?? []).map(subnet => subnet.id))],
    };

    const fargateProfiles = [
      { fargateProfileName: "serverless-defaults", selectors: [{ namespace: "default" }] },
      { fargateProfileName: "serverless-apps", selectors: [{ namespace: "serverless-apps" }] },
    ];

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
      new blueprints.addons.MetricsServerAddOn(),
      new blueprints.addons.AwsLoadBalancerControllerAddOn(),
      new blueprints.addons.CertManagerAddOn(),
      new blueprints.addons.ClusterAutoScalerAddOn(),
      new blueprints.addons.CloudWatchInsights({
        ebsPerformanceLogs: true,
      }),
      new blueprints.SecretsStoreAddOn(),
    ];

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
      ({
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
      }): blueprints.ManagedNodeGroup => {
        const nodeWorkerImage = ami
          ? ec2.MachineImage.lookup({
              name: "*",
              filters: Object.fromEntries(Object.entries(ami).map(([key, value]) => [key, [value]])),
            })
          : undefined;

        if (nodeWorkerImage)
          console.info(`[${clusterName}/${nodeGroupName}] - Node Image: ${nodeWorkerImage.getImage(this).imageId}`);
        else console.info(`[${clusterName}/${nodeGroupName}] - Node Image: DEFAULT`);

        const blockDevices = [
          {
            deviceName: storage?.rootDeviceName ?? "/dev/xvda",
            volume: ec2.BlockDeviceVolume.ebs(storage?.sizeInGB ?? 20, {
              encrypted: true,
              deleteOnTermination: true,
              volumeType: this.getVolumeType(storage),
            }),
          },
        ];

        const eksLaunchTemplate = blueprints.getResource(({ scope }) => {
          const userData = ec2.UserData.forLinux();

          const maxPodsLimit = enxMaxPods[instanceType] ?? "15";

          let rawUserData = fs.readFileSync(path.join(__dirname, "scripts/worker-node-userdata.sh"), {
            encoding: "utf-8",
          });

          rawUserData = rawUserData.replace("{{clusterName}}", clusterName);
          rawUserData = rawUserData.replace("{{MAX_PODS}}", maxPodsLimit);

          userData.addCommands(...rawUserData.split("\n").filter(line => line.length != 0));

          const keyPairName = (this.node.scope?.node.tryFindChild(this.props.keyPair.node.id) as ec2.IKeyPair)
            .keyPairName;

          const keyPair = ec2.KeyPair.fromKeyPairName(scope, `${scope.node.id}-${nodeGroupName}-keypair`, keyPairName);

          const template = new ec2.LaunchTemplate(scope, `${clusterName}-lt-${nodeGroupName}`, {
            machineImage: nodeWorkerImage,
            userData: nodeWorkerImage ? userData : undefined,
            launchTemplateName: `${clusterName}-lt-${nodeGroupName}`,
            httpTokens: ec2.LaunchTemplateHttpTokens.REQUIRED,
            httpPutResponseHopLimit: 2,
            ebsOptimized: true,
            blockDevices,
            keyPair,
          });

          return template;
        });

        console.debug(`[${nodeGroupName}] maxSize: ${maxSize}`);
        console.debug(`[${nodeGroupName}] minSize: ${minSize}`);
        console.debug(`[${nodeGroupName}] desiredCapacity: ${desiredCapacity}`);

        const nodeGroupSubnetFilter = nodeGroupSubnets
          ? {
              subnetType: ec2.SubnetType.PRIVATE_WITH_EGRESS,
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

    const clusterProvider = new blueprints.GenericClusterProvider({
      version: clusterVersion ? eks.KubernetesVersion.of(clusterVersion) : eks.KubernetesVersion.V1_30,
      endpointAccess: isPrivateCluster ? eks.EndpointAccess.PRIVATE : eks.EndpointAccess.PUBLIC_AND_PRIVATE,
      clusterName,
      vpcSubnets: [clusterSubnetFilter],
      mastersRole: clusterMasterRole,
      secretsEncryptionKey: clusterKey,
      managedNodeGroups,
      clusterLogging: [
        eks.ClusterLoggingTypes.API,
        eks.ClusterLoggingTypes.AUDIT,
        eks.ClusterLoggingTypes.AUTHENTICATOR,
        eks.ClusterLoggingTypes.CONTROLLER_MANAGER,
        eks.ClusterLoggingTypes.SCHEDULER,
      ],
      placeClusterHandlerInVpc: false,
      tags,
      // fargateProfiles: fargateProfiles.reduce((accumulator, fargateProfile) => {
      //   accumulator[fargateProfile.fargateProfileName] = fargateProfile;
      //   return accumulator;
      // }, {} as { [key: string]: eks.FargateProfileOptions }),
    });

    const eksBuilder = blueprints.EksBlueprint.builder();

    // Generate external-dns addon configuration
    if (hostedZones) {
      const privateHostedZones = hostedZones.filter(hostedZones => hostedZones.private);
      const publicHostedZones = hostedZones.filter(hostedZones => !hostedZones.private);

      const externalDnsConfig: blueprints.addons.ExternalDnsProps = {
        hostedZoneResources: hostedZones.map(({ zoneName }) => zoneName),
        values: {
          logLevel: "debug",
          policy: "sync",
        },
      };

      if (privateHostedZones.length > 0) {
        externalDnsConfig.values = {
          ...externalDnsConfig.values,
          ...{
            // extraArgs: ["--aws-prefer-cname", "--aws-zone-type=private"],
            extraArgs: ["--aws-zone-type=private"],
            txtPrefix: "txt-",
          },
        };
      }

      if (publicHostedZones.length > 0 && privateHostedZones.length > 0) {
        console.warn("Unsupported Capability for external-dns ...");
        console.warn("Cannot have both private and public hosted zones in the same cluster");
        console.warn("Only private hosted zones are prioritized");
      }

      blueprintsAddons.push(new blueprints.addons.ExternalDnsAddOn(externalDnsConfig));

      hostedZones.forEach(hostedZones => {
        // Check extended data for generated hosted zone

        const { zoneName } = hostedZones;
        const { extended } = this.props;

        const stackHostedZones = extended.hostedZones;

        console.warn(`Looking of hostzone of ${zoneName}`);

        const results = stackHostedZones
          .filter(hostedZone => hostedZone.zoneName === zoneName)
          .filter(hostedZone => hostedZone.private);

        if (results.length > 1)
          console.warn(`Found multiple hosted zones with the same name ${zoneName} and private property set to true`);

        if (results.length > 0) {
          console.info(`Found hosted zone ${zoneName} in extended data`);
          const resourceZone = results[0].zone;

          eksBuilder.resourceProvider(
            hostedZones.zoneName,
            new blueprints.ImportHostedZoneProvider(resourceZone.hostedZoneId)
          );

          return;
        }

        eksBuilder.resourceProvider(
          hostedZones.zoneName,
          new blueprints.LookupHostedZoneProvider(hostedZones.zoneName)
        );
      });
    }

    const clusterStack = eksBuilder
      .clusterProvider(clusterProvider)
      .region(environment?.region)
      .account(environment?.account)
      .resourceProvider(blueprints.GlobalResources.Vpc, new blueprints.DirectVpcProvider(vpc))
      .addOns(
        ...blueprintsAddons,
        new blueprints.addons.EbsCsiDriverAddOn({
          version: "auto",
          storageClass: undefined,
          kmsKeys: [clusterDataKey],
        }),
        new StorageClassDefaultAddon({
          storageClassPaths: globSync(`**/*.{yaml,yml}`, {
            cwd: path.resolve(__dirname, "..", "k8s/base/classes/storage"),
            absolute: true,
            ignore: ["*.disabled.{yaml,yml}", "kustomization.{yaml,yml}"],
          }),
          kmsKey: clusterDataKey,
        }),
        new blueprints.EfsCsiDriverAddOn({
          kmsKeys: [clusterDataKey],
        })
      )
      .useDefaultSecretEncryption(false)
      .build(this, `cluster-${clusterName}-stack`);

    return clusterStack;
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
