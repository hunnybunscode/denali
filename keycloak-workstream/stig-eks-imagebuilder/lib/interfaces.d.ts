/*
 * © 2025 Amazon Web Services, Inc. or its affiliates. All Rights Reserved.
 * This AWS Content is provided subject to the terms of the AWS Customer Agreement
 * available at http://aws.amazon.com/agreement or other written agreement between
 * Customer and either Amazon Web Services, Inc. or Amazon Web Services EMEA SARL or both.
 * -----
 * File: /lib/interfaces.d.ts
 * Created Date: Monday February 24th 2025
 * -----
 */

interface Environment {
  name: string;
  region?: string;
  account?: string;
  iam?: {
    prefix?: string;
    permissionBoundaryArn?: string;
  };
}

interface Component {
  name: string;
  version: string;
  parameters?: {
    name: string;
    value: string | string[];
  }[];
}

interface Pipeline {
  name: string;
  ami: { [key: string]: string };
  instanceTypes: string[];
  version: string;
  vpc?: {
    id: string;
    subnet: { id: string };
  };
  storages?: {
    type: string;
    deviceName: string;
    sizeInGB: number;
    iops?: number;
  }[];
  components: (Component | string)[];
  tags?: { [key: string]: string };
  description?: string;
  scan?: boolean;
  distributions?: {
    amiDistributionConfiguration: {
      launchPermissionConfiguration?: {
        organizationalUnitArns?: string[];
        organizationArns?: string[];
        userIds?: string[];
        userGroups?: string[];
      };
      targetAccountIds?: string[];
    };
    region: string;
  }[];
}

interface Configuration {
  environment: Environment;
  pipelines?: Pipeline[];
}
