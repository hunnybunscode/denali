import * as cdk from 'aws-cdk-lib';
import { Construct } from 'constructs';
import * as ec2 from 'aws-cdk-lib/aws-ec2';
import { VpcEndpointsConstruct } from './vpc-endpoints-construct';

export interface VpcEndpointsStackProps extends cdk.StackProps {
  config: any;
}

export class VpcEndpointsStack extends cdk.Stack {
  constructor(scope: Construct, id: string, props: VpcEndpointsStackProps) {
    super(scope, id, props);

    // Validate required VPC configuration
    this.validateVpcConfig(props.config.vpc);

    const vpc = ec2.Vpc.fromVpcAttributes(this, 'VPC', {
      vpcId: props.config.vpc.id,
      vpcCidrBlock: props.config.vpc.cidr,
      availabilityZones: props.config.vpc.availabilityZones,
      privateSubnetIds: props.config.vpc.privateSubnetIds,
      privateSubnetRouteTableIds: props.config.vpc.privateSubnetRouteTableIds,
    });

    new VpcEndpointsConstruct(this, 'VpcEndpoints', vpc, props.config);
  }

  private validateVpcConfig(vpcConfig: any): void {
    const requiredFields = [
      'id',
      'cidr', 
      'availabilityZones',
      'privateSubnetIds',
      'privateSubnetRouteTableIds'
    ];

    const missingFields = requiredFields.filter(field => 
      !vpcConfig[field] || 
      (Array.isArray(vpcConfig[field]) && vpcConfig[field].length === 0)
    );

    if (missingFields.length > 0) {
      throw new Error(
        `Missing required VPC configuration fields: ${missingFields.join(', ')}. ` +
        `Please ensure all required fields are provided in your configuration.yaml`
      );
    }

    // Validate subnet and route table counts match
    if (vpcConfig.privateSubnetIds.length !== vpcConfig.privateSubnetRouteTableIds.length) {
      throw new Error(
        `Number of privateSubnetIds (${vpcConfig.privateSubnetIds.length}) ` +
        `must match privateSubnetRouteTableIds (${vpcConfig.privateSubnetRouteTableIds.length})`
      );
    }
  }
}