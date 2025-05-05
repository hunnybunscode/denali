#!/usr/bin/env node
import "source-map-support/register";
import * as cdk from "aws-cdk-lib";
import { BootstrapStack } from "../lib/bootstrap-stack";

import { aws_iam as iam, aws_ec2 as ec2, Tags } from "aws-cdk-lib";

const { env } = process;
const app = new cdk.App();

console.info("CDK_DEFAULT_ACCOUNT:", env!.CDK_DEFAULT_ACCOUNT);
console.info("CDK_DEFAULT_REGION:", env!.CDK_DEFAULT_REGION);

const tags = {
  "Managed by": "aws-cdk",
  Owner: `${env.USER}`,
};

for (const [key, value] of Object.entries(tags)) {
  console.info(`Adding Key Value: "${key}" // "${value}"`);
  Tags.of(app).add(key, value, {
    includeResourceTypes: [],
  });
}

new BootstrapStack(app, "BootstrapStack", {
  env: {
    account: env!.CDK_DEFAULT_ACCOUNT,
    region: env!.CDK_DEFAULT_REGION,
  },
  enableEndpoints: false,
  createBastion: false,
  createRoute53: false,
});
