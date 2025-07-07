#!/usr/bin/env node
import 'source-map-support/register';
import * as cdk from 'aws-cdk-lib';
import { VpcEndpointsStack } from '../lib/vpc-endpoints-stack';
import { loadConfig } from '../lib/config';

const app = new cdk.App();
const env = app.node.tryGetContext('env') || 'dev';
const config = loadConfig(env);

new VpcEndpointsStack(app, 'VpcEndpointsStack', {
  vpcId: config.vpcId,
  env: {
    account: config.account,
    region: config.region,
  },
});