import * as fs from 'fs';
import * as yaml from 'js-yaml';
import * as path from 'path';

export interface Config {
  vpcId: string;
  account: string;
  region: string;
}

export function loadConfig(env: string = 'dev'): Config {
  const configPath = path.join(__dirname, '..', 'config', `${env}.yaml`);
  const fileContents = fs.readFileSync(configPath, 'utf8');
  return yaml.load(fileContents) as Config;
}