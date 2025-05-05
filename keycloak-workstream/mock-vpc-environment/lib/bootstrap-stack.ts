import { Construct } from "constructs";
import {
  StackProps,
  Stack,
  aws_ec2 as ec2,
  CfnOutput,
  Tags,
  aws_route53 as route53,
  aws_iam as iam,
  aws_inspectorv2 as inspector2,
  aws_guardduty as guardduty,
} from "aws-cdk-lib";

export interface BootstrapStackProps extends StackProps {
  enableEndpoints: boolean;
  createBastion: boolean;
  createRoute53: boolean;
}

export class BootstrapStack extends Stack {
  constructor(scope: Construct, id: string, props: BootstrapStackProps) {
    super(scope, id, props);

    const vpc = new ec2.Vpc(this, "vpc", {
      vpcName: `vpc-${this.node.id}`,
      ipAddresses: ec2.IpAddresses.cidr("10.0.0.0/16"),
      maxAzs: 2,
      natGateways: 1,
      createInternetGateway: true,
      enableDnsHostnames: true,
      enableDnsSupport: true,
      restrictDefaultSecurityGroup: true,
      subnetConfiguration: [
        {
          name: "cluster-public-",
          subnetType: ec2.SubnetType.PUBLIC,
          cidrMask: 24,
          mapPublicIpOnLaunch: false,
        },
        {
          name: "cluster-api-",
          subnetType: ec2.SubnetType.PRIVATE_WITH_EGRESS,
          cidrMask: 24,
        },
        {
          name: "cluster-worker-nodes-",
          subnetType: ec2.SubnetType.PRIVATE_WITH_EGRESS,
          cidrMask: 19,
        },
        {
          name: "cluster-services-",
          subnetType: ec2.SubnetType.PRIVATE_WITH_EGRESS,
          cidrMask: 19,
        },
        {
          name: "cluster-pods-",
          subnetType: ec2.SubnetType.PRIVATE_WITH_EGRESS,
          cidrMask: 19,
        },
      ],
    });

    vpc.publicSubnets.forEach((subnet) => Tags.of(subnet).add("kubernetes.io/role/elb", "1"));
    vpc.privateSubnets.forEach((subnet) => {
      if (subnet.node.id.includes("cluster-services")) {
        Tags.of(subnet).add("kubernetes.io/role/internal-elb", "1");
      }
    });
    vpc.privateSubnets.forEach((subnet) => {
      if (subnet.node.id.includes("cluster-pods")) {
        Tags.of(subnet).add("kubernetes.io/role/cni", "");
      }
    });

    if (props.enableEndpoints) {
      // Attach vpc endpoints to vpc
      this.createVpcEndpoints(vpc);
    }

    if (props.createBastion) {
      // Create bastion host
      this.createBastion(vpc);
    }

    new CfnOutput(this, "vpcId", {
      value: vpc.vpcId,
      exportName: `${this.node.id}-vpcId`,
    });

    new CfnOutput(this, `${this.node.id}-publicSubnetIds`, {
      value: vpc.publicSubnets.map((s) => s.subnetId).join(","),
      exportName: `${this.node.id}-publicSubnetIds`,
    });

    new CfnOutput(this, "privateSubnetIds", {
      value: vpc.privateSubnets.map((s) => s.subnetId).join(","),
      exportName: `${this.node.id}-privateSubnetIds`,
    });

    if (props.createRoute53) {
      this.createRoute53Zone(vpc);
    }

    this.createInspector();
  }

  private createRoute53Zone(vpc: ec2.Vpc) {
    // Create a Route53 Private Hosted Zone with developer.local
    const privateHostedZone = new route53.PrivateHostedZone(this, "PrivateHostedZone", {
      zoneName: "developer.local",
      vpc: vpc,
    });

    new CfnOutput(this, "privateHostedZoneId", {
      value: privateHostedZone.hostedZoneId,
      exportName: `${this.node.id}-privateHostedZoneId`,
    });

    new CfnOutput(this, "privateHostedZoneDomain", {
      value: privateHostedZone.zoneName,
      exportName: `${this.node.id}-privateHostedZoneDomain`,
    });
  }

  private createVpcEndpoints(vpc: ec2.Vpc) {
    // Create VPC Endpoint Security Group
    const securityGroup = new ec2.SecurityGroup(this, "vpc-endpoint-security-group", {
      vpc,
      allowAllOutbound: true,
      description: "Security Group for VPC Endpoint",
      securityGroupName: "vpc-endpoint-sg",
    });

    // List of VPC Interface Endpoints
    const vpcInterfaceEndpointServices = [
      ec2.InterfaceVpcEndpointAwsService.CLOUDWATCH_LOGS,
      ec2.InterfaceVpcEndpointAwsService.CLOUDFORMATION,
      ec2.InterfaceVpcEndpointAwsService.SSM,
      ec2.InterfaceVpcEndpointAwsService.EC2_MESSAGES,
      ec2.InterfaceVpcEndpointAwsService.SSM_MESSAGES,
      ec2.InterfaceVpcEndpointAwsService.ECR,
      ec2.InterfaceVpcEndpointAwsService.ECR_DOCKER,
      ec2.InterfaceVpcEndpointAwsService.STS,
      ec2.InterfaceVpcEndpointAwsService.EC2,
      ec2.InterfaceVpcEndpointAwsService.EKS,
      ec2.InterfaceVpcEndpointAwsService.EKS_AUTH,
    ];

    vpcInterfaceEndpointServices.forEach((service) => {
      vpc.addInterfaceEndpoint(`endpoint-${service.shortName}`, {
        service,
        securityGroups: [securityGroup],
      });
    });

    // List of VPC Gateway Endpoints
    // const vpcGatewayEndpointServices = [
    //   { name: "dynamoDB", service: ec2.GatewayVpcEndpointAwsService.DYNAMODB },
    //   { name: "s3", service: ec2.GatewayVpcEndpointAwsService.S3 },
    // ];

    // vpcGatewayEndpointServices.forEach((service) => {
    //   vpc.addGatewayEndpoint(`endpoint-${service.name}`, {
    //     service: service.service,
    //   });
    // });
  }

  private createBastion(vpc: ec2.Vpc) {
    // Create an EC2 IAM Role with Administrative Role
    const adminEc2Role = new iam.Role(this, "admin-ec2-role", {
      assumedBy: new iam.ServicePrincipal("ec2.amazonaws.com"),
      managedPolicies: [iam.ManagedPolicy.fromAwsManagedPolicyName("AdministratorAccess")],
      roleName: "admin-ec2-role",
    });

    // Create an EC2
    const instance = new ec2.Instance(this, "admin-ec2", {
      vpc,
      instanceType: ec2.InstanceType.of(ec2.InstanceClass.T3A, ec2.InstanceSize.XLARGE),
      machineImage: new ec2.AmazonLinuxImage({ generation: ec2.AmazonLinuxGeneration.AMAZON_LINUX_2 }),
      role: adminEc2Role,
      vpcSubnets: { subnetType: ec2.SubnetType.PRIVATE_WITH_EGRESS },
      allowAllOutbound: true,
      requireImdsv2: true,
      ssmSessionPermissions: true,
      userDataCausesReplacement: true,
      userData: ec2.UserData.custom(`#!/bin/bash
              yum update -y
              yum install -y docker vim wget curl
              systemctl enable docker
              systemctl start docker
              usermod -aG docker ec2-user
            `),
      blockDevices: [
        {
          deviceName: "/dev/xvda",
          volume: ec2.BlockDeviceVolume.ebs(40, {
            encrypted: true,
            volumeType: ec2.EbsDeviceVolumeType.GP3,
          }),
        },
      ],
    });

    new CfnOutput(this, "admin-ec2-instance-id", {
      value: instance.instanceId,
      exportName: "admin-ec2-instance-id",
    });
  }

  createInspector() {
    new inspector2.CfnCisScanConfiguration(this, "cis-scan-configuration", {
      scanName: "daily-cis-scan",
      securityLevel: "LEVEL_2",
      schedule: {
        daily: {
          startTime: {
            timeOfDay: "00:00",
            timeZone: "UTC",
          },
        },
      },
      targets: {
        accountIds: [this.account], // Uses the current account
        targetResourceTags: {
          "Managed By": ["cdk"],
        },
      },
    });
  }
}
