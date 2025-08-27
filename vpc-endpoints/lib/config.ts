import * as fs from 'fs';
import * as yaml from 'js-yaml';
import * as path from 'path';
import { STSClient, GetCallerIdentityCommand } from '@aws-sdk/client-sts';

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

export async function loadConfig(env: string = 'dev'): Promise<Config> {
  const configPath = path.join(__dirname, '..', 'env', env, 'configuration.yaml');
  
  // Return minimal config if file doesn't exist (allows destroy to work)
  if (!fs.existsSync(configPath)) {
    // Auto-detect account for dummy config
    let account = '000000000000';
    try {
      const sts = new STSClient({});
      const identity = await sts.send(new GetCallerIdentityCommand({}));
      account = identity.Account || '000000000000';
    } catch (error) {
      // Fallback to dummy account if detection fails
    }
    
    return {
      environment: {
        name: env,
        region: 'us-east-1',
        account
      },
      vpc: {
        id: 'vpc-dummy',
        cidr: '10.0.0.0/16',
        availabilityZones: ['us-east-1a'],
        privateSubnetIds: ['subnet-dummy'],
        publicSubnetIds: undefined,
        privateSubnetRouteTableIds: ['rtb-dummy'],
        publicSubnetRouteTableIds: undefined
      },
      vpcEndpoints: {
        gatewayEndpoints: {
          enabled: false,
          services: []
        }
      }
    };
  }
  
  const fileContents = fs.readFileSync(configPath, 'utf8');
  return yaml.load(fileContents) as Config;
}