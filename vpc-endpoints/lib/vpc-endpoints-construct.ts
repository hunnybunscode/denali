import { Construct } from 'constructs';
import * as ec2 from 'aws-cdk-lib/aws-ec2';
import { Tags } from 'aws-cdk-lib';
import * as packageJson from '../package.json';
import { Config } from './config';

export class VpcEndpointsConstruct extends Construct {
  constructor(scope: Construct, id: string, vpc: ec2.IVpc, config: Config) {
    super(scope, id);

    this.createVpcEndpoints(vpc, config);
    
    Tags.of(this).add('Component', 'VpcEndpoints');
    Tags.of(this).add('Version', packageJson.version);
  }

  private createVpcEndpoints(vpc: ec2.IVpc, config: Config) {
    const securityGroup = new ec2.SecurityGroup(this, "vpc-endpoint-security-group", {
      vpc,
      allowAllOutbound: true,
      description: "Security Group for VPC Endpoint",
      securityGroupName: "vpc-endpoint-sg",
    });

    const vpcInterfaceEndpointServices = [
      ec2.InterfaceVpcEndpointAwsService.APIGATEWAY,
      ec2.InterfaceVpcEndpointAwsService.AUTOSCALING,
      ec2.InterfaceVpcEndpointAwsService.CLOUDFORMATION,
      ec2.InterfaceVpcEndpointAwsService.CLOUDWATCH_LOGS,
      ec2.InterfaceVpcEndpointAwsService.CLOUDWATCH_MONITORING,
      ec2.InterfaceVpcEndpointAwsService.EC2_MESSAGES,
      ec2.InterfaceVpcEndpointAwsService.EC2,
      ec2.InterfaceVpcEndpointAwsService.ECR_DOCKER,
      ec2.InterfaceVpcEndpointAwsService.ECR,
      ec2.InterfaceVpcEndpointAwsService.EKS_AUTH,
      ec2.InterfaceVpcEndpointAwsService.EKS,
      ec2.InterfaceVpcEndpointAwsService.ELASTIC_LOAD_BALANCING,
      ec2.InterfaceVpcEndpointAwsService.LAMBDA,
      ec2.InterfaceVpcEndpointAwsService.SSM_MESSAGES,
      ec2.InterfaceVpcEndpointAwsService.SSM,
      ec2.InterfaceVpcEndpointAwsService.STEP_FUNCTIONS_SYNC,
      ec2.InterfaceVpcEndpointAwsService.STEP_FUNCTIONS,
      ec2.InterfaceVpcEndpointAwsService.STS,
      ec2.InterfaceVpcEndpointAwsService.ELASTIC_FILESYSTEM,
      ec2.InterfaceVpcEndpointAwsService.IMAGE_BUILDER,
      ec2.InterfaceVpcEndpointAwsService.KMS,
      ec2.InterfaceVpcEndpointAwsService.RDS_DATA,
      ec2.InterfaceVpcEndpointAwsService.RDS,
      ec2.InterfaceVpcEndpointAwsService.SECRETS_MANAGER,
      ec2.InterfaceVpcEndpointAwsService.XRAY,
    ];

    vpcInterfaceEndpointServices.forEach((service) => {
      const endpoint = new ec2.InterfaceVpcEndpoint(this, `VpcEndpoint-${service.shortName}`, {
        vpc,
        service,
        securityGroups: [securityGroup],
        privateDnsEnabled: true,
      });
      
      const cfnEndpoint = endpoint.node.defaultChild as ec2.CfnVPCEndpoint;
      cfnEndpoint.addPropertyOverride('Tags', [{
        Key: 'Name',
        Value: `VpcEndpoint-${service.shortName}`
      }]);
    });

    const vpcGatewayEndpointServices = [
      { name: "dynamodb", service: ec2.GatewayVpcEndpointAwsService.DYNAMODB },
      { name: "s3", service: ec2.GatewayVpcEndpointAwsService.S3 },
    ];

    vpcGatewayEndpointServices.forEach((service) => {
      const isEnabled = config.vpcEndpoints.gatewayEndpoints.enabled && 
                         config.vpcEndpoints.gatewayEndpoints.services.includes(service.name);
      
      if (isEnabled) {
        const endpoint = new ec2.GatewayVpcEndpoint(this, `VpcEndpoint-${service.name}`, {
          vpc,
          service: service.service,
        });
        
        const cfnEndpoint = endpoint.node.defaultChild as ec2.CfnVPCEndpoint;
        cfnEndpoint.addPropertyOverride('Tags', [{
          Key: 'Name',
          Value: `VpcEndpoint-${service.name}`
        }]);
      }
    });
  }
}