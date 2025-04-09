import { Stack, StackProps, aws_iam as iam, CfnOutput } from "aws-cdk-lib";
import { Construct } from "constructs";
import ConfigurationDocument from "../lib/configurationDocument";
import * as fs from "fs";
import * as path from "path";
import * as glob from "glob";

interface LimitedPrivilegedRoleEmulatorStackProps extends StackProps, ConfigurationDocument {}

export class LimitedPrivilegedRoleEmulatorStack extends Stack {
  constructor(scope: Construct, id: string, props?: LimitedPrivilegedRoleEmulatorStackProps) {
    super(scope, id, props);

    const { region, partition, account } = this;

    // Read all json files in lib/policies using glob, replace all account and region and create new policies
    const policyFiles = glob.sync(path.join(__dirname, "policies", "*.json"));
    const policies = policyFiles.map((policyFile) => {
      let policy = fs.readFileSync(policyFile, "utf8");
      policy = policy.replace(/{{account}}/g, account);
      policy = policy.replace(/{{region}}/g, region);
      policy = policy.replace(/{{partition}}/g, partition);
      return JSON.parse(policy);
    });

    const managedPolicies = policies.map((policy, index) => {
      const policyName = path.basename(policyFiles[index], ".json");

      const policyDocument = iam.PolicyDocument.fromJson(policy);

      const managedPolicy = new iam.ManagedPolicy(this, `ManagedPolicy-${policyName}`, {
        managedPolicyName: `${policyName}`,
        document: policyDocument,
      });

      return managedPolicy;
    });

    const role = new iam.Role(this, "LimitedAccessRole", {
      roleName: "LimitedAccessRole",
      description: "Limited Privileged Role Emulator",
      assumedBy: new iam.CompositePrincipal(
        new iam.AccountRootPrincipal(),
        new iam.ServicePrincipal("lambda.amazonaws.com"),
        new iam.ServicePrincipal("ec2.amazonaws.com"),
        new iam.ServicePrincipal("cloudformation.amazonaws.com")
      ),
      managedPolicies,
    });

    new CfnOutput(this, "LimitedAccessRoleArn", {
      value: role.roleArn,
    });
  }
}
