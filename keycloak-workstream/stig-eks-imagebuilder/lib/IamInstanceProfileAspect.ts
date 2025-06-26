import { IAspect, AspectOptions, Stack, CfnResource } from "aws-cdk-lib";
import { IConstruct } from "constructs";
import { CfnInstanceProfile, CfnManagedPolicy, CfnPolicy } from "aws-cdk-lib/aws-iam";
import * as util from "util";

export interface IamInstanceProfileAspectOptions extends AspectOptions {
  readonly namePrefix?: string;
  verbose?: boolean;
}

export default class IamInstanceProfileAspect implements IAspect {
  private readonly pattern = /\${Token\[TOKEN.\d+\]}/;
  private readonly options: IamInstanceProfileAspectOptions = { verbose: false };

  constructor(options?: IamInstanceProfileAspectOptions) {
    this.options = { ...this.options, ...options };

    if (this.options.verbose) console.debug(this.options);
  }

  public visit(node: IConstruct): void {
    if (node instanceof CfnResource) {
      const cfnResourceNode: CfnResource = node;

      if (cfnResourceNode.cfnResourceType == "AWS::IAM::InstanceProfile") {
        const cfnInstanceProfile = node as CfnInstanceProfile;
        const resolvedLogicalId = Stack.of(node).resolve(cfnInstanceProfile.logicalId);

        const { options, pattern } = this;

        if (options.verbose) {
          console.debug("****************");
          // console.debug(util.inspect(node, { depth: 2 }));
          console.debug(resolvedLogicalId);
        }

        if (options.namePrefix !== undefined) {
          let newProfileName = cfnInstanceProfile.instanceProfileName!;
          const oldProfileName = newProfileName;

          if (this.options.verbose) console.debug(`Updating Instance Profile Name: ${oldProfileName}`);

          if (pattern.test(newProfileName)) {
            if (this.options.verbose) console.debug(`Instance Profile Name contains CDK token: ${newProfileName}`);
            newProfileName = resolvedLogicalId;
          }

          if (!newProfileName.startsWith(options.namePrefix)) {
            if (this.options.verbose)
              console.debug(`Instance Profile Name does not start with prefix: ${newProfileName}, adding prefix ...`);
            newProfileName = `${options.namePrefix}-${newProfileName}`;
          }

          console.debug(`Updating Instance Profile Name: ${newProfileName}`);

          // Update the Instance Profile Name property
          cfnInstanceProfile.addPropertyOverride(
            "InstanceProfileName",
            newProfileName.substring(0, 128 - `${options.namePrefix}-`.length)
          );
        }
      }
    }
  }
}
