interface Environment {
  name: string;
  region?: string;
  account?: string;
}

interface Cluster {
  name: string;
  vpc: {
    id: string;
  };
}

interface ConfigurationDocument {
  environment: Environment;
  cluster: Cluster;
}
