# VPC Endpoints CDK

This CDK project creates VPC endpoints for AWS services in an existing VPC.

## Configuration

Minimal `shared-services/env/dev/configuration.yaml` (only VPC ID required):

```yaml
environment:
  name: dev
  region: us-east-1
  account: "776732943381"

vpc:
  id: vpc-037578bc40b4ca79f  # Only this is required!

vpcEndpoints:
  gatewayEndpoints:
    enabled:
      - dynamodb
      - s3
```

**Note:** VPC CIDR and availability zones are automatically populated during build.

## Setup

```bash
npm install
npm run build
```

## Deploy

Update the VPC ID in `shared-services/env/dev/configuration.yaml`, then:

```bash
npm run build    # Populates VPC config + compiles
npx cdk deploy   # Deploys stack
```

For different environments:

```bash
# One-time environment variable
ENVIRONMENT=dev npx cdk deploy

# Or export for multiple commands
export ENVIRONMENT=dev
npx cdk deploy
```

With custom CDK toolkit:

```bash
CUSTOM_TOOLKIT=MyCompany-CDK-Toolkit npx cdk deploy
```

## Destroy

To remove all VPC endpoints and clean up resources:

```bash
npx cdk destroy
```

**Note:** Destroy works even if VPC configuration is incomplete, making cleanup always possible.

## Prerequisites

- Existing VPC with private subnets
- AWS CLI configured with appropriate permissions
- Node.js 18+ installed
- CDK CLI installed: `npm install -g aws-cdk`

## Getting VPC Information

To find your VPC details for configuration:

```bash
# Get VPC ID and CIDR
aws ec2 describe-vpcs --query 'Vpcs[*].[VpcId,CidrBlock]' --output table

# Get private subnet IDs
aws ec2 describe-subnets --filters "Name=vpc-id,Values=YOUR_VPC_ID" "Name=map-public-ip-on-launch,Values=false" --query 'Subnets[*].SubnetId' --output text

# Get route table IDs
aws ec2 describe-route-tables --filters "Name=vpc-id,Values=YOUR_VPC_ID" --query 'RouteTables[*].RouteTableId' --output text
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

## Cost Considerations

- Interface endpoints: ~$7.20/month per endpoint
- Gateway endpoints: Free (data processing charges apply)
- Total estimated cost: ~$180/month for all interface endpoints

## Usage

The `VpcEndpointsConstruct` can be imported and used in other stacks:

```typescript
import { VpcEndpointsConstruct } from './lib/vpc-endpoints-construct';

// In your stack
new VpcEndpointsConstruct(this, 'VpcEndpoints', existingVpc, config);
```