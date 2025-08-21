import * as cdk from 'aws-cdk-lib';
import * as ec2 from 'aws-cdk-lib/aws-ec2';
import * as ecs from 'aws-cdk-lib/aws-ecs';
import * as ecsPatterns from 'aws-cdk-lib/aws-ecs-patterns';
import * as elbv2 from 'aws-cdk-lib/aws-elasticloadbalancingv2';
import * as rds from 'aws-cdk-lib/aws-rds';
import * as s3 from 'aws-cdk-lib/aws-s3';
import { Construct } from 'constructs';

export class SpydorInfraStack extends cdk.Stack {
  constructor(scope: Construct, id: string, props?: cdk.StackProps) {
    super(scope, id, props);

    const sypdor_infra_vpc: ec2.Vpc = new ec2.Vpc(this, 'spydor_infra_vpc', {
      maxAzs: 2,
      subnetConfiguration: [
        {
          cidrMask: 24,
          name: 'Public',
          subnetType: ec2.SubnetType.PUBLIC,
        },
        {
          cidrMask: 24,
          name: 'Fargate',
          subnetType: ec2.SubnetType.PRIVATE_ISOLATED,
        },
        {
          cidrMask: 24,
          name: 'Database',
          subnetType: ec2.SubnetType.PRIVATE_WITH_EGRESS,
        },
      ],
    });

    const spydor_infra_alb_sg: ec2.SecurityGroup = new ec2.SecurityGroup(this, 'spydor_infra_alb_sg', {
      vpc: sypdor_infra_vpc,
      allowAllOutbound: true,
    });

    spydor_infra_alb_sg.addIngressRule(ec2.Peer.anyIpv4(), ec2.Port.tcp(80));
    spydor_infra_alb_sg.addIngressRule(ec2.Peer.anyIpv4(), ec2.Port.tcp(443));

    const spydor_infra_fargate_sg: ec2.SecurityGroup = new ec2.SecurityGroup(this, 'spydor_infra_fargate_sg', {
      vpc: sypdor_infra_vpc,
      allowAllOutbound: true,
    });

    const spydor_infra_database_sg: ec2.SecurityGroup = new ec2.SecurityGroup(this, 'spydor_infra_database_sg', {
      vpc: sypdor_infra_vpc,
      allowAllOutbound: false,
    });

    spydor_infra_fargate_sg.addIngressRule(spydor_infra_alb_sg, ec2.Port.tcp(80));
    spydor_infra_database_sg.addIngressRule(spydor_infra_fargate_sg, ec2.Port.tcp(1521));

    const spydor_infra_cluster: ecs.Cluster = new ecs.Cluster(this, 'spydor_infra_cluster', {
      vpc: sypdor_infra_vpc,
    });

    const spydor_infra_logs_bucket: s3.Bucket = new s3.Bucket(this, 'spydor_infra_logs_bucket', {
      removalPolicy: cdk.RemovalPolicy.RETAIN,
      encryption: s3.BucketEncryption.S3_MANAGED
    });

    const spydor_infra_mdl_bucket: s3.Bucket = new s3.Bucket(this, 'spydor_infra_mdl_bucket', {
      removalPolicy: cdk.RemovalPolicy.RETAIN,
      encryption: s3.BucketEncryption.S3_MANAGED
    });

    const spydor_infra_db: rds.DatabaseInstance = new rds.DatabaseInstance(this, 'spydor_infra_db', {
      engine: rds.DatabaseInstanceEngine.oracleEe({ version: rds.OracleEngineVersion.VER_19_0_0_0_2023_04_R1 }),
      instanceType: ec2.InstanceType.of(ec2.InstanceClass.T3, ec2.InstanceSize.MEDIUM),
      vpc: sypdor_infra_vpc,
      vpcSubnets: { subnetGroupName: 'Database' },
      securityGroups: [spydor_infra_database_sg],
      multiAz: true,
      removalPolicy: cdk.RemovalPolicy.RETAIN
    });

    const spydor_infra_fargate_task: ecs.FargateTaskDefinition = new ecs.FargateTaskDefinition(this, 'spydor_infra_fargate_task', {
      memoryLimitMiB: 512,
      cpu: 256,
    });

    spydor_infra_fargate_task.addContainer('spydor_infra_fargate_container', {
      image: ecs.ContainerImage.fromRegistry('tomcat:9.0'),
      portMappings: [{ containerPort: 8080 }],
    });

    const spydor_infra_alb = new elbv2.ApplicationLoadBalancer(this, 'spydor_infra_alb', {
      vpc: sypdor_infra_vpc,
      internetFacing: true,
      securityGroup: spydor_infra_alb_sg,
    });

    const spydor_infra_fargate_service = new ecs.FargateService(this, 'spydor_infra_fargate_service', {
      cluster: spydor_infra_cluster,
      taskDefinition: spydor_infra_fargate_task,
      securityGroups: [spydor_infra_fargate_sg],
    });
  }
}
