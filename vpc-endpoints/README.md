# VPC Endpoints CDK

This CDK project creates VPC endpoints for AWS services in an existing VPC.

## Zero Configuration Setup

**No configuration required!** The system auto-detects:
- AWS account (from your credentials)
- AWS region (from environment or defaults to us-east-1)
- VPC (finds suitable VPC automatically)
- All VPC details (subnets, route tables, etc.)

**Optional configuration** - only if you want to customize:

```yaml
# All settings are optional - system uses smart defaults
environment:
  name: dev                    # Auto-detected
  region: us-east-1           # Auto-detected
  account: "776732943381"     # Auto-detected
  
  # OPTIONAL: For specialized environments (GovCloud, etc.)
  # synthesizeOverride:
  #   deployRoleArn: arn:aws-us-gov:iam::123:role/custom-deploy-role
  #   fileAssetsBucketName: my-custom-assets-bucket
  #   qualifier: myqualifier

vpc:
  id: vpc-037578bc40b4ca79f   # Auto-detected (or specify your own)

vpcEndpoints:
  gatewayEndpoints:
    enabled: false            # Default: disabled (set to true to enable)
    services:
      - dynamodb
      - s3
```

## Setup

```bash
npm install
npm run build
```

## Deploy

**Zero configuration deployment:**

```bash
npm run build    # Auto-detects everything + compiles
npx cdk deploy   # Deploys with smart defaults
```

**For different environments:**

```bash
# Deploy to staging
ENVIRONMENT=staging npm run build && npx cdk deploy

# Deploy to production
ENVIRONMENT=prod npm run build && npx cdk deploy
```

**For specialized environments (GovCloud, etc.):**
Add `synthesizeOverride` section to your configuration.yaml with custom role ARNs.

## Destroy

To remove all VPC endpoints and clean up resources:

```bash
npx cdk destroy
```

**Note:** Destroy works even if VPC configuration is incomplete, making cleanup always possible.

## Testing

**Full End-to-End Test** (destroy → delete config → rebuild → redeploy):

```bash
npm run test-full-cycle
```

This single command will:
1. Destroy existing stack (with --force, no prompts)
2. Delete configuration.yaml file
3. Auto-detect and rebuild configuration
4. Deploy stack (with --require-approval never, no prompts)

Perfect for testing the complete zero-configuration workflow!

## Prerequisites

- AWS CLI configured with appropriate permissions
- Node.js 18+ installed
- CDK CLI installed: `npm install -g aws-cdk`
- **That's it!** No VPC setup required - system finds suitable VPC automatically

## Advanced Configuration

**Manual VPC Selection** (if auto-detection picks wrong VPC):

```bash
# Find your VPCs
aws ec2 describe-vpcs --query 'Vpcs[*].[VpcId,CidrBlock,IsDefault]' --output table

# Then specify the VPC ID in configuration.yaml
```

**Custom CDK Roles** (for GovCloud/Enterprise):

```yaml
environment:
  synthesizeOverride:
    deployRoleArn: arn:aws-us-gov:iam::123:role/my-deploy-role
    fileAssetsBucketName: my-custom-assets-bucket
    qualifier: myqualifier
```

## What Gets Created

This stack creates:
- **25 Interface VPC Endpoints** for AWS services (Lambda, S3, EC2, etc.)
- **2 Gateway VPC Endpoints** (DynamoDB, S3) - configurable
- **Security Group** allowing HTTPS traffic from VPC CIDR
- **Proper naming tags** for all endpoints

## Troubleshooting

**Common Issues:**

1. **"VPC not found"** - Verify VPC ID in configuration
2. **"Subnet not found"** - Ensure subnet IDs are correct and in the specified VPC
3. **"Route table not found"** - Check route table IDs match your VPC
4. **"Number of subnets must be multiple of AZs"** - Ensure subnet count matches AZ count

## Usage

The `VpcEndpointsConstruct` can be imported and used in other stacks:

```typescript
import { VpcEndpointsConstruct } from './lib/vpc-endpoints-construct';

// In your stack
new VpcEndpointsConstruct(this, 'VpcEndpoints', existingVpc, config);
```