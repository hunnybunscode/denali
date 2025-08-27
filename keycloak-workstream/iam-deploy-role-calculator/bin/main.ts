#!/opt/homebrew/opt/node/bin/node
import "source-map-support/register";
import { Tags, App, Aspects } from "aws-cdk-lib";
import { AwsSolutionsChecks, NIST80053R4Checks, NagSuppressions } from "cdk-nag";
import { IamDeployRoleCalculatorStack } from "../lib/iam-deploy-role-calculator-stack";

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

new IamDeployRoleCalculatorStack(app, "IamDeployRoleCalculatorStack", {
  env: {
    account: env!.CDK_DEFAULT_ACCOUNT,
    region: env!.CDK_DEFAULT_REGION,
  },
});

Aspects.of(app).add(new NIST80053R4Checks({ verbose: true }));
Aspects.of(app).add(new AwsSolutionsChecks({ verbose: true }));

// Generalized Suppression
NagSuppressions.addResourceSuppressions(
  app,
  [
    {
      id: "NIST.800.53.R4-IAMNoInlinePolicy",
      reason:
        "Using infrastructure as code, where inline policy is make practical sense for security and grant access",
    },
    {
      id: "AwsSolutions-L1",
      reason: "Not using the latest runtime as it is not available in certain target region",
    },
  ],
  true
);