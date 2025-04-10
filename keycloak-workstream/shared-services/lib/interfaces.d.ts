interface Environment {
  name: string;
  region?: string;
  account?: string;
  iam?: {
    prefix?: string
    permissionBoundaryArn?: string
  }
}

interface HostedZone {
  zoneName: string;
  private: boolean;
  account?: string;
  createCertificate?: boolean;
  vpc?: {
    // vpc data needs to be entered if private is being used
    id: string;
  };
}

type ExtendedHostedZone = HostedZone & { id?: string };

interface Cluster {
  name: string;
  version?: "1.27" | "1.28" | "1.29" | "1.30";
  private?: boolean;
  vpc: {
    id?: string;
    cidr?: string;
    subnets?: { id: string; cidr: string }[];
  };
  nodeGroups: NodeGroup[];
  tags?: { [key: string]: string };
  hostedZones?: ExtendedHostedZone[];
}

interface ConfigurationDocument {
  environment: Environment;
  hostedZones?: HostedZone[];
  clusters?: Cluster[];
  bastions?: Bastion[];
}

interface NodeGroup {
  name: string;
  instanceType: string;
  // Refer to (Filters) https://docs.aws.amazon.com/AWSEC2/latest/APIReference/API_DescribeImages.html#API_DescribeImages_RequestParameters
  ami?: { [key: string]: string };
  storage?: {
    rootDeviceName: string;
    sizeInGB: number;
    type: string;
  };
  subnets?: {
    id: string;
  }[];
  desiredCapacity?: number;
  minSize?: number;
  maxSize?: number;
  labels?: { [key: string]: string };
  tags?: { [key: string]: string };
  taints?: { key: string; value: string; effect: string }[];
}

interface Bastion {
  name: string;
  instanceType?: string;
  // Refer to (Filters) https://docs.aws.amazon.com/AWSEC2/latest/APIReference/API_DescribeImages.html#API_DescribeImages_RequestParameters
  ami?: { [key: string]: string };
  storage?: {
    rootDeviceName: string;
    sizeInGB: number;
    type: string;
  };
  tags?: { [key: string]: string };
}
