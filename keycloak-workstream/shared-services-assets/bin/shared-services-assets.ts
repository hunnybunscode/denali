#!/opt/homebrew/opt/node/bin/node
import "source-map-support/register";
import { App, Aspects, CliCredentialsStackSynthesizer, DefaultStackSynthesizer, Tags } from "aws-cdk-lib";
import * as path from "path";
import * as fs from "fs";
import * as yaml from "js-yaml";
import type { ConfigurationDocument } from "../lib/interface.types";
import { SharedServicesAssetsStack } from "../lib/shared-services-assets-stack";
import IamRoleAspect from "../lib/IamRoleAspect";
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

new SharedServicesAssetsStack(app, "SharedServicesAssetsStack", environment);

Aspects.of(app).add(
  new IamRoleAspect({
    namePrefix: doc.environment?.iam?.prefix,
    permissionBoundaryArn: doc.environment?.iam?.permissionBoundaryArn,
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
