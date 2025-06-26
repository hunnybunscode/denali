import { IAspect, AspectOptions, Stack, CfnResource } from "aws-cdk-lib";
import { IConstruct } from "constructs";
import { CfnManagedPolicy, CfnPolicy } from "aws-cdk-lib/aws-iam";
import * as util from "util";

export interface IamPolicyAspectOptions extends AspectOptions {
  readonly namePrefix?: string;
  verbose?: boolean;
}

export default class IamPolicyAspect implements IAspect {
  private readonly options: IamPolicyAspectOptions = { verbose: false };

  constructor(options?: IamPolicyAspectOptions) {
    this.options = { ...this.options, ...options };

    if (this.options.verbose) console.debug(this.options);
  }

  public visit(node: IConstruct): void {
    if (node instanceof CfnResource) {
      const cfnResourceNode: CfnResource = node;
      const resolvedNodeLogicalId = Stack.of(node).resolve(cfnResourceNode.logicalId);

      if (cfnResourceNode.cfnResourceType == "AWS::IAM::Policy") {
        const cfnPolicy = node as CfnPolicy;

        // Check if Policy Name starts with the namePrefix
        const policyName = Stack.of(node).resolve(cfnPolicy.policyName);

        if (this.options.namePrefix && !policyName.startsWith(this.options.namePrefix)) {
          const newPolicyName = `${this.options.namePrefix}-${policyName}`;

          if (this.options.verbose) console.debug(`Updating policy name: ${policyName} to ${newPolicyName}`);

          cfnPolicy.addPropertyOverride("PolicyName", newPolicyName);
        }
      }

      if (cfnResourceNode.cfnResourceType == "AWS::IAM::ManagedPolicy") {
        const cfnPolicy = node as CfnManagedPolicy;

        // Check if Policy Name starts with the namePrefix
        let policyName: string | undefined = Stack.of(node).resolve(cfnPolicy.managedPolicyName);

        if (policyName == undefined) {
          // Get the logical ID of the resource
          const logicalId = Stack.of(node).resolve(cfnPolicy.logicalId) as string;
          policyName = logicalId;

          if (this.options.verbose) console.debug(`Setting Undefined Managed policy name: ${policyName}`);
        }

        if (this.options.namePrefix && !policyName.startsWith(this.options.namePrefix)) {
          const newPolicyName = `${this.options.namePrefix}-${policyName}`;

          if (this.options.verbose) console.debug(`Updating policy name: ${policyName} to ${newPolicyName}`);

          cfnPolicy.addPropertyOverride("ManagedPolicyName", newPolicyName);
        }
      }
    }
  }
}
