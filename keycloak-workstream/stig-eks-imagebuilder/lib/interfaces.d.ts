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
  readonly name: string;
  readonly region?: string;
  readonly account?: string;
  readonly iam?: {
    readonly prefix?: string;
    readonly permissionBoundaryArn?: string;
  };
  readonly synthesizeOverride?: {
    /**
     * Uses the current user access to deploy. This configuration only applies reliably to new stack deployment only.
     * On existing stacks with defined IAM Role for execution, it will assume the user's IAM role.
     */
    readonly useCliCredentials?: boolean;
    /**
     * Name of the S3 bucket to hold file assets
     *
     * You must supply this if you have given a non-standard name to the staging bucket.
     *
     * The placeholders `${Qualifier}`, `${AWS::AccountId}` and `${AWS::Region}` will
     * be replaced with the values of qualifier and the stack's account and region,
     * respectively.
     *
     * @default DefaultStackSynthesizer.DEFAULT_FILE_ASSETS_BUCKET_NAME
     */
    readonly fileAssetsBucketName?: string;
    /**
     * Name of the ECR repository to hold Docker Image assets
     *
     * You must supply this if you have given a non-standard name to the ECR repository.
     *
     * The placeholders `${Qualifier}`, `${AWS::AccountId}` and `${AWS::Region}` will
     * be replaced with the values of qualifier and the stack's account and region,
     * respectively.
     *
     * @default DefaultStackSynthesizer.DEFAULT_IMAGE_ASSETS_REPOSITORY_NAME
     */
    readonly imageAssetsRepositoryName?: string;
    /**
     * The role to use to publish file assets to the S3 bucket in this environment
     *
     * You must supply this if you have given a non-standard name to the publishing role.
     *
     * The placeholders `${Qualifier}`, `${AWS::AccountId}` and `${AWS::Region}` will
     * be replaced with the values of qualifier and the stack's account and region,
     * respectively.
     *
     * @default DefaultStackSynthesizer.DEFAULT_FILE_ASSET_PUBLISHING_ROLE_ARN
     */
    readonly fileAssetPublishingRoleArn?: string;
    /**
     * External ID to use when assuming role for file asset publishing
     *
     * @default - No external ID
     */
    readonly fileAssetPublishingExternalId?: string;
    /**
     * The role to use to publish image assets to the ECR repository in this environment
     *
     * You must supply this if you have given a non-standard name to the publishing role.
     *
     * The placeholders `${Qualifier}`, `${AWS::AccountId}` and `${AWS::Region}` will
     * be replaced with the values of qualifier and the stack's account and region,
     * respectively.
     *
     * @default DefaultStackSynthesizer.DEFAULT_IMAGE_ASSET_PUBLISHING_ROLE_ARN
     */
    readonly imageAssetPublishingRoleArn?: string;
    /**
     * The role to use to look up values from the target AWS account during synthesis
     *
     * @default - None
     */
    readonly lookupRoleArn?: string;
    /**
     * External ID to use when assuming lookup role
     *
     * @default - No external ID
     */
    readonly lookupRoleExternalId?: string;
    /**
     * Use the bootstrapped lookup role for (read-only) stack operations
     *
     * Use the lookup role when performing a `cdk diff`. If set to `false`, the
     * `deploy role` credentials will be used to perform a `cdk diff`.
     *
     * Requires bootstrap stack version 8.
     *
     * @default true
     */
    readonly useLookupRoleForStackOperations?: boolean;
    /**
     * External ID to use when assuming role for image asset publishing
     *
     * @default - No external ID
     */
    readonly imageAssetPublishingExternalId?: string;
    /**
     * External ID to use when assuming role for cloudformation deployments
     *
     * @default - No external ID
     */
    readonly deployRoleExternalId?: string;
    /**
     * The role to assume to initiate a deployment in this environment
     *
     * You must supply this if you have given a non-standard name to the publishing role.
     *
     * The placeholders `${Qualifier}`, `${AWS::AccountId}` and `${AWS::Region}` will
     * be replaced with the values of qualifier and the stack's account and region,
     * respectively.
     *
     * @default DefaultStackSynthesizer.DEFAULT_DEPLOY_ROLE_ARN
     */
    readonly deployRoleArn?: string;
    /**
     * The role CloudFormation will assume when deploying the Stack
     *
     * You must supply this if you have given a non-standard name to the execution role.
     *
     * The placeholders `${Qualifier}`, `${AWS::AccountId}` and `${AWS::Region}` will
     * be replaced with the values of qualifier and the stack's account and region,
     * respectively.
     *
     * @default DefaultStackSynthesizer.DEFAULT_CLOUDFORMATION_ROLE_ARN
     */
    readonly cloudFormationExecutionRole?: string;
    /**
     * Qualifier to disambiguate multiple environments in the same account
     *
     * You can use this and leave the other naming properties empty if you have deployed
     * the bootstrap environment with standard names but only different qualifiers.
     *
     * @default - Value of context key '@aws-cdk/core:bootstrapQualifier' if set, otherwise `DefaultStackSynthesizer.DEFAULT_QUALIFIER`
     */
    readonly qualifier?: string;
    /**
     * Whether to add a Rule to the stack template verifying the bootstrap stack version
     *
     * This generally should be left set to `true`, unless you explicitly
     * want to be able to deploy to an unbootstrapped environment.
     *
     * @default true
     */
    readonly generateBootstrapVersionRule?: boolean;
    /**
     * bucketPrefix to use while storing S3 Assets
     *
     * @default - DefaultStackSynthesizer.DEFAULT_FILE_ASSET_PREFIX
     */
    readonly bucketPrefix?: string;
    /**
     * A prefix to use while tagging and uploading Docker images to ECR.
     *
     * This does not add any separators - the source hash will be appended to
     * this string directly.
     *
     * @default - DefaultStackSynthesizer.DEFAULT_DOCKER_ASSET_PREFIX
     */
    readonly dockerTagPrefix?: string;
    /**
     * Bootstrap stack version SSM parameter.
     *
     * The placeholder `${Qualifier}` will be replaced with the value of qualifier.
     *
     * @default DefaultStackSynthesizer.DEFAULT_BOOTSTRAP_STACK_VERSION_SSM_PARAMETER
     */
    readonly bootstrapStackVersionSsmParameter?: string;
    /**
     * Additional options to pass to STS when assuming the deploy role.
     *
     * - `RoleArn` should not be used. Use the dedicated `deployRoleArn` property instead.
     * - `ExternalId` should not be used. Use the dedicated `deployRoleExternalId` instead.
     * - `TransitiveTagKeys` defaults to use all keys (if any) specified in `Tags`. E.g, all tags are transitive by default.
     *
     * @see https://docs.aws.amazon.com/AWSJavaScriptSDK/latest/AWS/STS.html#assumeRole-property
     * @default - No additional options.
     */
    readonly deployRoleAdditionalOptions?: {
      [key: string]: any;
    };
    /**
     * Additional options to pass to STS when assuming the lookup role.
     *
     * - `RoleArn` should not be used. Use the dedicated `lookupRoleArn` property instead.
     * - `ExternalId` should not be used. Use the dedicated `lookupRoleExternalId` instead.
     * - `TransitiveTagKeys` defaults to use all keys (if any) specified in `Tags`. E.g, all tags are transitive by default.
     *
     * @see https://docs.aws.amazon.com/AWSJavaScriptSDK/latest/AWS/STS.html#assumeRole-property
     * @default - No additional options.
     */
    readonly lookupRoleAdditionalOptions?: {
      [key: string]: any;
    };
    /**
     * Additional options to pass to STS when assuming the file asset publishing.
     *
     * - `RoleArn` should not be used. Use the dedicated `fileAssetPublishingRoleArn` property instead.
     * - `ExternalId` should not be used. Use the dedicated `fileAssetPublishingExternalId` instead.
     * - `TransitiveTagKeys` defaults to use all keys (if any) specified in `Tags`. E.g, all tags are transitive by default.
     *
     * @see https://docs.aws.amazon.com/AWSJavaScriptSDK/latest/AWS/STS.html#assumeRole-property
     * @default - No additional options.
     */
    readonly fileAssetPublishingRoleAdditionalOptions?: {
      [key: string]: any;
    };
    /**
     * Additional options to pass to STS when assuming the image asset publishing.
     *
     * - `RoleArn` should not be used. Use the dedicated `imageAssetPublishingRoleArn` property instead.
     * - `ExternalId` should not be used. Use the dedicated `imageAssetPublishingExternalId` instead.
     * - `TransitiveTagKeys` defaults to use all keys (if any) specified in `Tags`. E.g, all tags are transitive by default.
     *
     * @see https://docs.aws.amazon.com/AWSJavaScriptSDK/latest/AWS/STS.html#assumeRole-property
     * @default - No additional options.
     */
    readonly imageAssetPublishingRoleAdditionalOptions?: {
      [key: string]: any;
    };
  };
  proxy?: {
    noProxy?: string[] | string;
    httpProxy?: string;
    httpsProxy?: string;
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
  test?: boolean;
  enhancedImageMetadata?: boolean;
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

interface ConfigurationDocument {
  environment: Environment;
  pipelines?: Pipeline[];
}
