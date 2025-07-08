#!/usr/bin/env node
import 'source-map-support/register';
import * as cdk from 'aws-cdk-lib';
import { AwsSolutionsChecks, NagSuppressions } from 'cdk-nag';
import { Aspects } from 'aws-cdk-lib';
import { VpcEndpointsStack } from '../lib/vpc-endpoints-stack';
import { loadConfig } from '../lib/config';

const app = new cdk.App();
const env = process.env.ENVIRONMENT || 'dev';
const config = loadConfig(env);

const tags = {
  "Managed-by": "aws-cdk",
  "Owner": process.env.USER || 'unknown',
  "Environment": env,
};

const stack = new VpcEndpointsStack(app, 'VpcEndpointsStack', {
  config,
  env: {
    account: config.environment.account,
    region: config.environment.region,
  },
  tags,
  ...(process.env.CUSTOM_TOOLKIT && {
    toolkitStackName: process.env.CUSTOM_TOOLKIT
  }),
});

Aspects.of(app).add(new AwsSolutionsChecks({ verbose: true }));
console.log('CDK-nag applied to app - should show findings during deployment');