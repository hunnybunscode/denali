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

    const vpc = ec2.Vpc.fromLookup(this, 'VPC', {
      vpcId: props.config.vpc.id,
    });

    new VpcEndpointsConstruct(this, 'VpcEndpoints', vpc, props.config);
  }
}