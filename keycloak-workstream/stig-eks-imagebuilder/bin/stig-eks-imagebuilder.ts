#!/opt/homebrew/opt/node/bin/node

/*
 * © 2025 Amazon Web Services, Inc. or its affiliates. All Rights Reserved.
 * This AWS Content is provided subject to the terms of the AWS Customer Agreement
 * available at http://aws.amazon.com/agreement or other written agreement between
 * Customer and either Amazon Web Services, Inc. or Amazon Web Services EMEA SARL or both.
 * -----
 * File: /bin/stig-eks-imagebuilder.ts
 * Created Date: Friday February 21st 2025
 * -----
 */

///<reference path="../lib/interfaces.d.ts" />

import { App, Aspects, Tags } from "aws-cdk-lib";
import { StigEksImageBuilderStack } from "../lib/stig-eks-imagebuilder-stack";
import * as path from "path";
import * as fs from "fs";
import * as yaml from "js-yaml";
import IamRoleAspect from "../lib/IamRoleAspect";
import IamPolicyAspect from "../lib/IamPolicyAspect";
import LambdaEnvAspect from "../lib/LambdaEnvAspect";

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

let doc: Configuration;

try {
  const environmentName = env.ENVIRONMENT ?? "dev";
  console.info(`Loading environment variables for environment: ${environmentName}`);
  doc = yaml.load(
    fs.readFileSync(path.normalize(path.join(__dirname, `../env/${environmentName}/configuration.yaml`)), "utf8")
  ) as Configuration;
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

new StigEksImageBuilderStack(app, "StigEksImagebuilderStack", environment);

Aspects.of(app).add(
  new IamRoleAspect({
    namePrefix: doc.environment?.iam?.prefix,
    permissionBoundaryArn: doc.environment?.iam?.permissionBoundaryArn,
    verbose: true,
  })
);

Aspects.of(app).add(
  new IamPolicyAspect({
    namePrefix: doc.environment?.iam?.prefix,
    verbose: true,
  })
);

Aspects.of(app).add(
  new LambdaEnvAspect({
    environmentVariables: {
      REQUESTS_CA_BUNDLE: "/etc/pki/ca-trust/extracted/pem/tls-ca-bundle.pem",
      NODE_EXTRA_CA_CERTS: "/etc/pki/ca-trust/extracted/pem/tls-ca-bundle.pem",
    },
    verbose: true,
  })
);
