import * as cdk from 'aws-cdk-lib';
import { Construct } from 'constructs';
import * as ec2 from 'aws-cdk-lib/aws-ec2';
import { VpcEndpointsConstruct } from './vpc-endpoints-construct';
import { Config } from './config';

export interface VpcEndpointsStackProps extends cdk.StackProps {
  config: Config;
}

export class VpcEndpointsStack extends cdk.Stack {
  constructor(scope: Construct, id: string, props: VpcEndpointsStackProps) {
    super(scope, id, props);

    const vpc = ec2.Vpc.fromVpcAttributes(this, 'VPC', {
      vpcId: props.config.vpc.id,
      vpcCidrBlock: props.config.vpc.cidr ?? '',
      availabilityZones: props.config.vpc.availabilityZones ?? [],
      privateSubnetIds: props.config.vpc.privateSubnetIds,
      publicSubnetIds: props.config.vpc.publicSubnetIds,
      privateSubnetRouteTableIds: props.config.vpc.privateSubnetRouteTableIds,
      publicSubnetRouteTableIds: props.config.vpc.publicSubnetRouteTableIds,
    });

    new VpcEndpointsConstruct(this, 'VpcEndpoints', vpc, props.config);
  }


}