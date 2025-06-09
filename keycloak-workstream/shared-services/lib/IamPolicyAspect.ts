import { IAspect, AspectOptions, Stack, CfnResource } from "aws-cdk-lib";
import { IConstruct } from "constructs";
import { CfnPolicy } from "aws-cdk-lib/aws-iam";
// import * as util from "util";

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
    }
  }
}
