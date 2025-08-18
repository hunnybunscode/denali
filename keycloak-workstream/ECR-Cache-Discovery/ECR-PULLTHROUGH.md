# ECR Pull Through Cache

## What is ECR Pull Through Cache?

### Simple Definition
ECR Pull Through Cache is an AWS feature that makes ECR act like a **smart mirror** of external container registries.

### How It Works

**Without Pull Through Cache:**
```
Your App → Docker Hub → Downloads nginx:latest
Your App → Docker Hub → Downloads nginx:latest (again)
Your App → Docker Hub → Downloads nginx:latest (again)
```

**With Pull Through Cache:**
```
Your App → ECR → Docker Hub → Downloads nginx:latest (first time)
Your App → ECR → Returns cached nginx:latest (fast!)
Your App → ECR → Returns cached nginx:latest (fast!)
```

### What Actually Happens

1. **You configure ECR** to cache images from Docker Hub
2. **First time**: Your app requests `nginx:latest` → ECR doesn't have it → ECR fetches from Docker Hub → ECR stores it → ECR gives it to your app
3. **Next times**: Your app requests `nginx:latest` → ECR already has it → ECR gives cached copy immediately

### Key Point
**You change your image URLs** from:
- `docker.io/nginx:latest` 
- **TO**: `123456789.dkr.ecr.us-west-2.amazonaws.com/docker-hub/nginx:latest`

### Why Use It?
- **Faster**: Cached images download quicker
- **Safer**: ECR scans all images for vulnerabilities  
- **More reliable**: Works even if Docker Hub is down
- **Cheaper**: Less external bandwidth usage
- **Compliant**: All images go through your AWS account

## Programmatic Implementation

### Implementation Strategy

1. **Infrastructure Setup**
   - Create ECR pull through cache rules for each external registry
   - Configure IAM permissions for EKS nodes to access ECR
   - Set up monitoring and logging

2. **Application Migration**
   - Update container image references in Kubernetes manifests
   - Modify Helm charts to use ECR-cached images
   - Update CDK constructs with new image URLs

3. **Automation & Governance**
   - Create CDK constructs for pull through cache management
   - Implement image scanning policies
   - Set up automated vulnerability reporting

### Supported Registries
- **Docker Hub** (`docker.io`)
- **Quay** (`quay.io`)
- **GitHub Container Registry** (`ghcr.io`)
- **Microsoft Container Registry** (`mcr.microsoft.com`)
- **Kubernetes Registry** (`registry.k8s.io`)
- **Red Hat Registry** (`registry.access.redhat.com`)

### Migration Process
1. **Create cache rules** for each registry
2. **Test with non-critical workloads** first
3. **Update image references** in manifests
4. **Deploy and validate** functionality
5. **Monitor performance** and costs

## Code Examples and Services

### AWS CLI Commands

**Create Pull Through Cache Rule:**
```bash
# Docker Hub
aws ecr create-pull-through-cache-rule \
    --ecr-repository-prefix docker-hub \
    --upstream-registry-url docker.io \
    --region us-west-2

# Quay.io
aws ecr create-pull-through-cache-rule \
    --ecr-repository-prefix quay \
    --upstream-registry-url quay.io \
    --region us-west-2

# GitHub Container Registry
aws ecr create-pull-through-cache-rule \
    --ecr-repository-prefix ghcr \
    --upstream-registry-url ghcr.io \
    --region us-west-2
```

**List Existing Rules:**
```bash
aws ecr describe-pull-through-cache-rules --region us-west-2
```

**Delete Rule:**
```bash
aws ecr delete-pull-through-cache-rule \
    --ecr-repository-prefix docker-hub \
    --region us-west-2
```

### CDK Implementation

**ECR Pull Through Cache Construct:**
```typescript
import * as ecr from 'aws-cdk-lib/aws-ecr';
import { Construct } from 'constructs';

export class ECRPullThroughCacheConstruct extends Construct {
  constructor(scope: Construct, id: string) {
    super(scope, id);

    // Docker Hub cache
    new ecr.CfnPullThroughCacheRule(this, 'DockerHubCache', {
      ecrRepositoryPrefix: 'docker-hub',
      upstreamRegistryUrl: 'docker.io',
    });

    // Quay cache
    new ecr.CfnPullThroughCacheRule(this, 'QuayCache', {
      ecrRepositoryPrefix: 'quay',
      upstreamRegistryUrl: 'quay.io',
    });

    // GitHub Container Registry cache
    new ecr.CfnPullThroughCacheRule(this, 'GHCRCache', {
      ecrRepositoryPrefix: 'ghcr',
      upstreamRegistryUrl: 'ghcr.io',
    });
  }
}
```

**Usage in Stack:**
```typescript
import { ECRPullThroughCacheConstruct } from './ecr-cache-construct';

export class MyStack extends Stack {
  constructor(scope: Construct, id: string, props?: StackProps) {
    super(scope, id, props);

    // Add ECR pull through cache
    new ECRPullThroughCacheConstruct(this, 'ECRCache');
  }
}
```

### Kubernetes Manifest Updates

**Before (Direct Registry):**
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: nginx-deployment
spec:
  template:
    spec:
      containers:
      - name: nginx
        image: docker.io/nginx:latest
      - name: postgres
        image: postgres:16
```

**After (ECR Cached):**
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: nginx-deployment
spec:
  template:
    spec:
      containers:
      - name: nginx
        image: 123456789.dkr.ecr.us-west-2.amazonaws.com/docker-hub/nginx:latest
      - name: postgres
        image: 123456789.dkr.ecr.us-west-2.amazonaws.com/docker-hub/postgres:16
```

### Helm Chart Updates

**values.yaml:**
```yaml
# Before
image:
  repository: docker.io/nginx
  tag: latest

# After
image:
  repository: 123456789.dkr.ecr.us-west-2.amazonaws.com/docker-hub/nginx
  tag: latest
```

### IAM Permissions

**EKS Node Group Role Policy:**
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "ecr:GetAuthorizationToken",
        "ecr:BatchCheckLayerAvailability",
        "ecr:GetDownloadUrlForLayer",
        "ecr:BatchGetImage"
      ],
      "Resource": "*"
    }
  ]
}
```

### Monitoring and Automation

**CloudWatch Metrics:**
```typescript
// Monitor ECR repository usage
const ecrMetric = new cloudwatch.Metric({
  namespace: 'AWS/ECR',
  metricName: 'RepositoryPullCount',
  dimensionsMap: {
    RepositoryName: 'docker-hub/nginx'
  }
});
```

**Lambda Function for Image Scanning:**
```typescript
export const handler = async (event: any) => {
  const ecr = new ECRClient({ region: 'us-west-2' });
  
  // Trigger scan on new cached images
  await ecr.send(new StartImageScanCommand({
    repositoryName: event.repositoryName,
    imageId: { imageTag: event.imageTag }
  }));
};
```

### Required AWS Services

1. **Amazon ECR** - Container registry with pull through cache
2. **Amazon EKS** - Kubernetes service using cached images
3. **AWS IAM** - Permissions for ECR access
4. **AWS CloudWatch** - Monitoring and logging
5. **AWS Lambda** - Automation and scanning triggers
6. **AWS CDK/CloudFormation** - Infrastructure as code