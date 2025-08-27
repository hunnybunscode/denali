#!/usr/bin/env node
///<reference path="../lib/interfaces.d.ts" />

import "source-map-support/register";
import { App, Aspects, CliCredentialsStackSynthesizer, DefaultStackSynthesizer, Tags } from "aws-cdk-lib";
import { AwsSolutionsChecks, NIST80053R4Checks, NagSuppressions } from "cdk-nag";
import * as path from "path";
import * as fs from "fs";
import * as yaml from "js-yaml";
import { SharedServicesStack } from "../lib/shared-services-stack";
import IamRoleAspect from "../lib/IamRoleAspect";
import IamInstanceProfileAspect from "../lib/IamInstanceProfileAspect";
import IamPolicyAspect from "../lib/IamPolicyAspect";
import LambdaEnvAspect from "../lib/LambdaEnvAspect";

const { env } = process;
const app = new App();

console.info("CDK_DEFAULT_ACCOUNT:", env!.CDK_DEFAULT_ACCOUNT);
console.info("CDK_DEFAULT_REGION:", env!.CDK_DEFAULT_REGION);

let doc: ConfigurationDocument;

try {
  const environmentName = env.ENVIRONMENT ?? "dev";
  console.info(`Loading environment variables for environment: ${environmentName}`);
  doc = yaml.load(
    fs.readFileSync(path.join(__dirname, `../env/${environmentName}/configuration.yaml`), "utf8")
  ) as ConfigurationDocument;
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
  synthesizer: doc.environment.synthesizeOverride
    ? doc.environment.synthesizeOverride.useCliCredentials
      ? (() => {
          console.warn("Using CLI Credentials ...");
          return new CliCredentialsStackSynthesizer(doc.environment.synthesizeOverride);
        })()
      : new DefaultStackSynthesizer(doc.environment.synthesizeOverride)
    : undefined,
};

const tags = {
  "Managed by": "aws-cdk",
  Owner: `${env.USER}`,
};

// Parse the tags for the environment
if (doc.environment.tags) {
  Object.assign(tags, doc.environment.tags);
}

for (const [key, value] of Object.entries(tags)) {
  console.info(`Adding Key Value: "${key}" // "${value}"`);
  Tags.of(app).add(key, `${value}`, {
    includeResourceTypes: [],
    excludeResourceTypes: [],
  });
}

new SharedServicesStack(app, "SharedServicesStack", environment);

Aspects.of(app).add(new NIST80053R4Checks({ verbose: true }));
Aspects.of(app).add(new AwsSolutionsChecks({ verbose: true }));

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
  new IamInstanceProfileAspect({
    namePrefix: doc.environment?.iam?.prefix,
    verbose: true,
  })
);

const useProxy = doc.environment.proxy ? true : false;
const proxyConfig: { [key: string]: string } = {};

if (useProxy) {
  proxyConfig["HTTP_PROXY"] = doc.environment.proxy?.httpProxy ?? "";
  proxyConfig["HTTPS_PROXY"] = doc.environment.proxy?.httpsProxy ?? "";

  if (doc.environment.proxy?.noProxy) {
    let noProxyStr = "";

    if (Array.isArray(doc.environment.proxy?.noProxy)) {
      noProxyStr = doc.environment.proxy?.noProxy.join(",");
    } else {
      noProxyStr = doc.environment.proxy?.noProxy;
    }

    proxyConfig["NO_PROXY"] = noProxyStr;
  }
}

Aspects.of(app).add(
  new LambdaEnvAspect({
    environmentVariables: {
      ...{
        REQUESTS_CA_BUNDLE: "/etc/pki/ca-trust/extracted/pem/tls-ca-bundle.pem",
        NODE_EXTRA_CA_CERTS: "/etc/pki/ca-trust/extracted/pem/tls-ca-bundle.pem",
      },
      ...(useProxy ? proxyConfig : {}),
    },
    verbose: true,
  })
);

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
