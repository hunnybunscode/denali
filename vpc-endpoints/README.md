# VPC Endpoints CDK

This CDK project creates VPC endpoints for AWS services in an existing VPC.

## Setup

```bash
npm install
npm run build
```

## Deploy

Update the VPC ID in `config/dev.yaml`, then deploy:

```bash
npx cdk deploy
```

For different environments:

```bash
npx cdk deploy --context env=prod
```

## Usage

The `VpcEndpointsConstruct` can be imported and used in other stacks:

```typescript
import { VpcEndpointsConstruct } from './lib/vpc-endpoints-construct';

// In your stack
new VpcEndpointsConstruct(this, 'VpcEndpoints', existingVpc);
```