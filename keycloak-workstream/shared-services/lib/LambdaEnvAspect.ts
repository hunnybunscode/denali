import { AspectOptions, CfnResource, IAspect, Stack, aws_lambda as lambda } from "aws-cdk-lib";
import { IConstruct } from "constructs";

export interface LambdaEnvAspectOptions extends AspectOptions {
  environmentVariables?: { [key: string]: string };
  verbose?: boolean;
}

export default class LambdaEnvAspect implements IAspect {
  private readonly options: LambdaEnvAspectOptions = { verbose: false };

  constructor(options?: LambdaEnvAspectOptions) {
    this.options = { ...this.options, ...options };
    if (options?.verbose) console.debug(options);
  }

  visit(node: IConstruct): void {
    if (node instanceof CfnResource && node.cfnResourceType == "AWS::Lambda::Function") {
      const environment = (node as lambda.CfnFunction).environment;
      const resolved: lambda.CfnFunction.EnvironmentProperty | undefined = Stack.of(node).resolve(environment);

      if (resolved?.variables) {
        if (this.options.environmentVariables) {
          node.addPropertyOverride("Environment.Variables", { ...resolved.variables, ...this.options.environmentVariables });
        }
      } else {
        if (this.options.environmentVariables) {
          node.addPropertyOverride("Environment.Variables", { ...this.options.environmentVariables });
        }
      }
    }
  }
}
