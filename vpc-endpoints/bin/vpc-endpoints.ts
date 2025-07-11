#!/usr/bin/env node
import 'source-map-support/register';
import * as cdk from 'aws-cdk-lib';
import { AwsSolutionsChecks, NagSuppressions, NIST80053R5Checks } from 'cdk-nag';
import { Aspects } from 'aws-cdk-lib';
import { VpcEndpointsStack } from '../lib/vpc-endpoints-stack';
import { loadConfig } from '../lib/config';

async function main() {
  const app = new cdk.App();
  const env = process.env.ENVIRONMENT || 'dev';
  const config = await loadConfig(env);

// Create synthesizer based on configuration
let synthesizer;
if (config.environment.synthesizeOverride) {
  // Use custom synthesizer with all provided options
  synthesizer = new cdk.DefaultStackSynthesizer(config.environment.synthesizeOverride);
} else if (config.cdk?.toolkitStackName) {
  // Legacy support for simple toolkit name override
  synthesizer = new cdk.DefaultStackSynthesizer({
    bootstrapStackVersionSsmParameter: `/cdk-bootstrap/${config.cdk.toolkitStackName}/version`,
    fileAssetsBucketName: `${config.cdk.toolkitStackName}-assets-\${AWS::AccountId}-\${AWS::Region}`,
    bucketPrefix: '',
  });
}

const stack = new VpcEndpointsStack(app, 'VpcEndpointsStack', {
  config,
  env: {
    account: config.environment.account,
    region: config.environment.region,
  },
  synthesizer,
});

  Aspects.of(app).add(new AwsSolutionsChecks({ verbose: true }));
  Aspects.of(app).add(new NIST80053R5Checks({ verbose: true }));
  console.log('CDK-nag applied to app - AWS Solutions and NIST 800-53 R5 checks enabled');
}

main().catch(console.error);