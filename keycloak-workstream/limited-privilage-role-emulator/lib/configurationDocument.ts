interface Environment {
  name: string;
  region?: string;
  account?: string;
}

export default interface ConfigurationDocument {
  environment: Environment;
}
