import { Construct } from "constructs";
import { aws_lambda as lambda, aws_s3_assets as s3_asset } from "aws-cdk-lib";
import * as path from "path";

export class OrasLambdaLayer extends lambda.LayerVersion {
  constructor(scope: Construct, id: string) {
    super(scope, id, {
      code: lambda.Code.fromAsset(path.join(__dirname, "..", "binary/amd64/bin")),
      compatibleRuntimes: [lambda.Runtime.NODEJS_18_X, lambda.Runtime.PYTHON_3_11],
      description: "ORAS Lambda Layer",
      layerVersionName: "oras-lambda-layer",
    });
  }
}
