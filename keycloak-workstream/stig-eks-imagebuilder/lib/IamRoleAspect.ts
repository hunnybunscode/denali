import { IAspect, AspectOptions, Stack, CfnResource } from "aws-cdk-lib";
import { IConstruct } from "constructs";
import { CfnRole } from "aws-cdk-lib/aws-iam";
// import * as util from "util";

export interface IamRoleAspectOptions extends AspectOptions {
  readonly namePrefix?: string;
  readonly permissionBoundaryArn?: string;
  verbose?: boolean;
}

export default class IamRoleAspect implements IAspect {
  private readonly pattern = /\${Token\[TOKEN.\d+\]}/;
  private readonly maxLength = 64;
  private readonly suffixLength = 8;
  private readonly roleNameCache: string[] = [];
  private readonly options: IamRoleAspectOptions = { verbose: false };

  constructor(options?: IamRoleAspectOptions) {
    this.options = { ...this.options, ...options };

    if (this.options.verbose) console.debug(this.options);
  }

  public visit(node: IConstruct): void {
    if (node instanceof CfnResource) {
      const cfnResourceNode: CfnResource = node;

      if (cfnResourceNode.cfnResourceType == "AWS::IAM::Role") {
        const cfnRole = node as CfnRole;
        const resolvedLogicalId = Stack.of(node).resolve(cfnRole.logicalId);

        const { options, maxLength, suffixLength, pattern } = this;

        if (options.verbose) {
          console.debug("****************");
          // console.debug(util.inspect(node, { depth: 2 }));
          console.debug(resolvedLogicalId);
        }

        // Skip if roleName is not defined (using CloudFormation generated name)
        if (!cfnRole.roleName) {
          console.debug(`RoleName is not defined - Node ID: ${resolvedLogicalId}`);
          cfnRole.roleName = resolvedLogicalId;
        }

        // Check prefix is defined
        if (options.namePrefix !== undefined) {
          let newRoleName = cfnRole.roleName!;
          const oldRoleName = newRoleName;

          if (this.options.verbose) console.debug(`Updating role name: ${oldRoleName}`);

          if (pattern.test(newRoleName)) {
            if (this.options.verbose) console.debug(`Role name contains CDK token: ${newRoleName}`);
            newRoleName = resolvedLogicalId;
          }

          // Add AFC2S prefix if not present
          if (!newRoleName.startsWith(`${options.namePrefix}-`)) {
            if (this.options.verbose)
              console.debug(`Role name does not start with prefix: ${newRoleName}, adding prefix ...`);
            newRoleName = `${options.namePrefix}-${newRoleName}`;
          }

          // Ensure the name doesn't exceed 64 characters
          if (newRoleName.length > this.maxLength) {
            // Remove characters from the middle of the name while preserving prefix and suffix

            const prefixLength = `${this.options.namePrefix}-`.length;

            const middleSection = newRoleName.slice(prefixLength, -suffixLength);
            const shortenedMiddle = middleSection.slice(0, maxLength - prefixLength - suffixLength);

            newRoleName = `${this.options.namePrefix}-${shortenedMiddle}${newRoleName.slice(-suffixLength)}`.substring(
              0,
              maxLength - 1
            );

            // Check if the new role name is already in use
            if (this.roleNameCache.includes(newRoleName)) {
              if (this.options.verbose) console.debug(`Role name already in use: ${newRoleName}, alternating ...`);
              // If the role name is already in use, remove the suffix
              newRoleName = `${this.options.namePrefix}-${shortenedMiddle}`.substring(0, maxLength - 1);
            }
          }

          if (this.roleNameCache.includes(newRoleName)) {
            console.warn(`[${node.stack.node.id}] Detected duplicated role name: ${newRoleName}`);
            if (this.options.verbose) console.debug(`Role name already in use: ${newRoleName}, incrementing ...`);

            // Increment the last letter by 1 and replace
            do {
              const lastLetter = newRoleName.slice(-1);
              let letterCode = (lastLetter.charCodeAt(0) + 1) % 26;

              const newLastLetter = String.fromCharCode(letterCode + 65);
              newRoleName = `${newRoleName.slice(0, -1)}${newLastLetter}`;
              console.log(`testing new role name: ${newRoleName}`);
            } while (this.roleNameCache.includes(newRoleName));
          }

          // Update the role name
          cfnRole.addPropertyOverride("RoleName", newRoleName);
          console.debug(`Updated role name: ${newRoleName}`);

          this.roleNameCache.push(newRoleName);
        }

        // Update the permission boundary to the role if not set
        if (this.options.permissionBoundaryArn !== undefined && cfnRole.permissionsBoundary === undefined) {
          cfnRole.addPropertyOverride("PermissionsBoundary", this.options.permissionBoundaryArn);
          if (this.options.verbose) console.debug(`Updated permission boundary: ${this.options.permissionBoundaryArn}`);
        }
      }
    }
  }
}
