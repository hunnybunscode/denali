import {
  Stack,
  StackProps,
  aws_ecs as ecs,
  aws_ecs_patterns as ecs_patterns,
  aws_ec2 as ec2,
  aws_elasticloadbalancingv2 as elb,
  aws_logs as logs,
  CfnOutput,
  Duration,
  RemovalPolicy,
} from "aws-cdk-lib";
import { Construct } from "constructs";

import * as path from "path";

export interface SquidEcsFargateStackProps extends StackProps, ConfigurationDocument {}

export class SquidEcsFargateStack extends Stack {
  constructor(scope: Construct, id: string, props: SquidEcsFargateStackProps) {
    super(scope, id, { description: "Create a Fargate ECS Cluster to run Squid Proxy", ...props });

    const { environment, cluster: clusterConfiguration } = props;

    // Identity current system architecture
    const cpuArch = process.arch === "x64" ? ecs.CpuArchitecture.X86_64 : ecs.CpuArchitecture.ARM64;
    // const cpuArch = ecs.CpuArchitecture.X86_64;

    const squidContainerImage = ecs.ContainerImage.fromAsset(path.join(__dirname), {
      assetName: "SquidProxyImage",
      buildArgs: {
        ARCH: cpuArch === ecs.CpuArchitecture.X86_64 ? "amd64" : "arm64",
      },
    });

    const vpc = ec2.Vpc.fromLookup(this, "squid-vpc", {
      vpcId: clusterConfiguration.vpc.id,
    });

    const squidIngressSecurityGroup = new ec2.SecurityGroup(this, "squid-ingress-security-group", {
      vpc,
      description: "Squid Ingress Security Group",
      allowAllOutbound: false,
    });

    squidIngressSecurityGroup.addIngressRule(ec2.Peer.anyIpv4(), ec2.Port.tcp(3128), "Allow Squid Ingress");
    squidIngressSecurityGroup.addEgressRule(ec2.Peer.anyIpv4(), ec2.Port.tcp(3128), "Allow Squid Egress");

    const squidContainerSecurityGroup = new ec2.SecurityGroup(this, "squid-container-security-group", {
      vpc,
      description: "Squid Container Service Security Group",
      allowAllOutbound: true,
    });

    squidContainerSecurityGroup.addIngressRule(squidIngressSecurityGroup, ec2.Port.tcp(3128), "Allow Squid Ingress");

    const clusterLogGroup = new logs.LogGroup(this, "squid-cluster-log-group", {
      logGroupName: `/aws/ecs/${environment.name}/${clusterConfiguration.name}`,
      retention: logs.RetentionDays.ONE_MONTH,
      removalPolicy: RemovalPolicy.DESTROY,
    });

    const cluster = new ecs.Cluster(this, "squid-cluster", {
      vpc,
      clusterName: clusterConfiguration.name,
      enableFargateCapacityProviders: true,
      containerInsightsV2: ecs.ContainerInsights.ENHANCED,
      executeCommandConfiguration: {
        logging: ecs.ExecuteCommandLogging.OVERRIDE,
        logConfiguration: {
          cloudWatchLogGroup: clusterLogGroup,
        },
      },
    });
    const squidTaskDefinition = new ecs.FargateTaskDefinition(this, "squid-task-definition", {
      cpu: 1024,
      memoryLimitMiB: 4096,
      runtimePlatform: {
        cpuArchitecture: cpuArch,
      },
      ephemeralStorageGiB: 30,
    });

    squidTaskDefinition.addContainer("squid-container", {
      image: squidContainerImage,
      containerName: "squid",
      logging: ecs.LogDriver.awsLogs({
        streamPrefix: "squid-container",
        logGroup: clusterLogGroup,
      }),
      startTimeout: Duration.minutes(1),
      stopTimeout: Duration.minutes(2),
      portMappings: [
        {
          containerPort: 3128,
          protocol: ecs.Protocol.TCP,
        },
      ],
      linuxParameters: new ecs.LinuxParameters(this, "squid-linux-parameters", {
        initProcessEnabled: true,
      }),
      // healthCheck: {
      //   retries: 3,
      //   timeout: Duration.seconds(10),
      //   interval: Duration.seconds(15),
      //   startPeriod: Duration.seconds(15),
      //   command: ["CMD-SHELL", "curl -f http://localhost:3128/ || exit 1"],
      // },
    });

    const squidService = new ecs_patterns.NetworkLoadBalancedFargateService(this, "squid-nlb-service", {
      cluster,
      taskDefinition: squidTaskDefinition,
      desiredCount: 1,
      taskSubnets: {
        subnetType: ec2.SubnetType.PRIVATE_WITH_EGRESS,
      },
      listenerPort: 3128,
      securityGroups: [squidContainerSecurityGroup],
      loadBalancer: new elb.NetworkLoadBalancer(this, "squid-nlb", {
        vpc,
        vpcSubnets: {
          subnetType: ec2.SubnetType.PRIVATE_WITH_EGRESS,
          onePerAz: true,
        },
        securityGroups: [squidIngressSecurityGroup],
      }),
      enableExecuteCommand: true,
    });

    squidService.targetGroup.configureHealthCheck({
      enabled: true,
      healthyHttpCodes: "400,200-299",
      path: "/",
      port: "3128",
      protocol: elb.Protocol.HTTP,
      timeout: Duration.seconds(30),
    });

    new CfnOutput(this, "squid-nlb-service-url", {
      value: `http://${squidService.loadBalancer.loadBalancerDnsName}:3128`,
    });

    new CfnOutput(this, "squid-sample-bash-output", {
      value:
        `export HTTPS_PROXY=http://${squidService.loadBalancer.loadBalancerDnsName}:3128; \n` +
        `export HTTP_PROXY=http://${squidService.loadBalancer.loadBalancerDnsName}:3128; \n` +
        `export NO_PROXY=localhost,127.0.0.1,169.254.169.254; \n`,
    });

    new CfnOutput(this, "squid-sample-bash-eks-output", {
      value:
        `export HTTPS_PROXY=http://${squidService.loadBalancer.loadBalancerDnsName}:3128; \n` +
        `export HTTP_PROXY=http://${squidService.loadBalancer.loadBalancerDnsName}:3128; \n` +
        `export NO_PROXY=172.20.0.0/16,localhost,127.0.0.1,169.254.169.254,169.254.170.2,${vpc.vpcCidrBlock},.internal,s3.amazonaws.com,.s3.${this.region}.amazonaws.com,api.ecr.${this.region}.amazonaws.com,dkr.ecr.${this.region}.amazonaws.com,ec2.${this.region}.amazonaws.com; \n`,
    });
  }
}
