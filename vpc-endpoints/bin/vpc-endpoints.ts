#!/usr/bin/env node
import 'source-map-support/register';
import * as cdk from 'aws-cdk-lib';
import { VpcEndpointsStack } from '../lib/vpc-endpoints-stack';
import { loadConfig } from '../lib/config';

const app = new cdk.App();
const env = process.env.ENVIRONMENT || 'dev';
const config = loadConfig(env);

new VpcEndpointsStack(app, 'VpcEndpointsStack', {
  config,
  env: {
    account: config.environment.account,
    region: config.environment.region,
  },
});