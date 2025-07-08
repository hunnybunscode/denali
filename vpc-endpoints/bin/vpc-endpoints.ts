#!/usr/bin/env node
import 'source-map-support/register';
import * as cdk from 'aws-cdk-lib';
import { AwsSolutionsChecks, NagSuppressions, NIST80053R5Checks } from 'cdk-nag';
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

// Apply tags to all resources in the app
Object.entries(tags).forEach(([key, value]) => {
  cdk.Tags.of(app).add(key, value);
});

const stack = new VpcEndpointsStack(app, 'VpcEndpointsStack', {
  config,
  env: {
    account: config.environment.account,
    region: config.environment.region,
  },
  ...(config.cdk?.toolkitStackName && {
    synthesizer: new cdk.DefaultStackSynthesizer({
      bootstrapStackVersionSsmParameter: `/cdk-bootstrap/${config.cdk.toolkitStackName}/version`,
      fileAssetsBucketName: `${config.cdk.toolkitStackName}-assets-\${AWS::AccountId}-\${AWS::Region}`,
      bucketPrefix: '',
    })
  }),
});

Aspects.of(app).add(new AwsSolutionsChecks({ verbose: true }));
Aspects.of(app).add(new NIST80053R5Checks({ verbose: true }));
console.log('CDK-nag applied to app - AWS Solutions and NIST 800-53 R5 checks enabled');