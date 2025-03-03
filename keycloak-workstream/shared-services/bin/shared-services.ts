#!/usr/bin/env node
///<reference path="../lib/interfaces.d.ts" />

import "source-map-support/register";
import { App, Aspects, Tags } from "aws-cdk-lib";
import { AwsSolutionsChecks, NIST80053R4Checks, NagSuppressions } from "cdk-nag";
import * as path from "path";
import * as fs from "fs";
import * as yaml from "js-yaml";
import { SharedServicesStack } from "../lib/shared-services-stack";

const { env } = process;
const app = new App();

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

let doc: Document;

try {
  const environmentName = env.ENVIRONMENT ?? "dev";
  console.info(`Loading environment variables for environment: ${environmentName}`);
  doc = yaml.load(
    fs.readFileSync(path.join(__dirname, `../env/${environmentName}/configuration.yaml`), "utf8")
  ) as Document;
} catch (e) {
  console.error(e);
  throw e;
}

console.info("Loading environment variables for account:", doc.environment.account);
console.info("Loading environment variables for region:", doc.environment.region);

console.info("Environment variables loaded successfully");

const environment = {
  env: {
    account: doc.environment.account ?? env!.CDK_DEFAULT_ACCOUNT,
    region: doc.environment.region ?? env!.CDK_DEFAULT_REGION,
  },
  ...doc,
};

new SharedServicesStack(app, "SharedServicesStack", environment);

Aspects.of(app).add(new NIST80053R4Checks({ verbose: true }));
Aspects.of(app).add(new AwsSolutionsChecks({ verbose: true }));

// Generalized Suppression
NagSuppressions.addResourceSuppressions(
  app,
  [
    {
      id: "NIST.800.53.R4-IAMNoInlinePolicy",
      reason:
        "Using infrastructure as code, where inline policy is make practical sense for security and grant grand access",
    },
    {
      id: "AwsSolutions-L1",
      reason: "Not using the latest runtime as it is not available in certain target region",
    },
  ],
  true
);
