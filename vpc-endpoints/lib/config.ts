import * as fs from 'fs';
import * as yaml from 'js-yaml';
import * as path from 'path';

export interface Config {
  environment: {
    name: string;
    region: string;
    account: string;
    synthesizeOverride?: {
      cloudFormationExecutionRole?: string;
      deployRoleArn?: string;
      fileAssetPublishingRoleArn?: string;
      imageAssetPublishingRoleArn?: string;
      lookupRoleArn?: string;
      fileAssetsBucketName?: string;
      qualifier?: string;
      [key: string]: any; // Allow any other synthesizer options
    };
  };
  cdk?: {
    toolkitStackName?: string;
  };
  vpc: {
    id: string;
    cidr?: string;
    availabilityZones?: string[];
    privateSubnetIds?: string[];
    publicSubnetIds?: string[];
    privateSubnetRouteTableIds?: string[];
    publicSubnetRouteTableIds?: string[];
  };
  vpcEndpoints: {
    gatewayEndpoints: {
      enabled: boolean;
      services: string[];
    };
  };
}

export function loadConfig(env: string = 'dev'): Config {
  const configPath = path.join(__dirname, '..', 'shared-services', 'env', env, 'configuration.yaml');
  const fileContents = fs.readFileSync(configPath, 'utf8');
  return yaml.load(fileContents) as Config;
}