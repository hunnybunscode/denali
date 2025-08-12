# Spydor Infrastructure Stack - Deployment Guide

## Prerequisites

Before deploying the stack, ensure you have:

1. **AWS Console Access**: Appropriate permissions to create CloudFormation stacks and all required resources
2. **VPC and Subnets**: Existing VPC with properly configured subnets (see requirements below)
3. **SSL Certificate** (Optional): If enabling HTTPS, upload certificate to IAM first
4. **Container Image**: Access to the container image (ECR or public registry)

## Pre-Deployment Requirements

### 1. VPC and Subnet Preparation

#### VPC Requirements
- Existing VPC with DNS hostnames and DNS resolution enabled
- Transit Gateway attachment configured for internet access
- Appropriate route tables configured for Transit Gateway routing

#### Subnet Requirements
You need **6 subnets total** across **2 Availability Zones**:

**Public Subnets (2 required)**
- Must be in different Availability Zones
- Must have route to Transit Gateway for internet access
- Used for Application Load Balancer
- Example CIDR: 10.0.1.0/24, 10.0.2.0/24

**Private Subnets - Fargate (2 required)**
- Must be in different Availability Zones (same AZs as public subnets)
- Private subnets with no internet access required
- Used for ECS Fargate containers
- Example CIDR: 10.0.3.0/24, 10.0.4.0/24

**Private Subnets - Database (2 required)**
- Must be in different Availability Zones (same AZs as others)
- Should NOT have internet access (isolated)
- Used for RDS Oracle database
- Example CIDR: 10.0.5.0/24, 10.0.6.0/24

### 2. SSL Certificate Setup (Optional)

If you want HTTPS support, upload your SSL certificate to IAM before deployment:

#### Using AWS CLI
```bash
aws iam upload-server-certificate \
  --server-certificate-name spydor-ssl-cert \
  --certificate-body file://certificate.pem \
  --private-key file://private-key.pem \
  --certificate-chain file://certificate-chain.pem
```

#### Using AWS Console
1. Navigate to **IAM Console** → **Server Certificates**
2. Click **Upload a server certificate**
3. Provide certificate name (e.g., "spydor-ssl-cert")
4. Upload certificate body, private key, and certificate chain
5. Note the certificate name for deployment parameters

### 3. Container Image Preparation

Ensure your container image is:
- Accessible from the deployment region
- Tagged appropriately (e.g., `your-repo/app:latest`)
- Tested and working on the expected port

## Deployment Steps

### Step 1: Access CloudFormation Console

1. Log into AWS Console
2. Navigate to **CloudFormation** service
3. Ensure you're in the correct AWS region
4. Click **Create stack** → **With new resources (standard)**

### Step 2: Upload Template

1. **Template source**: Select **Upload a template file**
2. **Choose file**: Upload `spydor_deployment_w_projadmin.yaml`
3. Click **Next**

### Step 3: Configure Stack Parameters

#### Stack Details
- **Stack name**: Enter a descriptive name (e.g., `spydor-prod-infrastructure`)

#### PROJADMIN Requirements
- **RolePrefix**: Enter required IAM role prefix (e.g., `AFC2S_`)
- **PermissionsBoundaryArn**: Enter the ARN of your permissions boundary policy

#### Application Configuration
- **ContainerImage**: Enter container image URI
  - ECR example: `123456789012.dkr.ecr.us-east-1.amazonaws.com/myapp:latest`
  - Docker Hub example: `nginx:latest`
- **ContainerPort**: Port your application listens on (default: `8080`)
- **HealthCheckPath**: Health check endpoint path (default: `/`)
- **HealthCheckSuccessCode**: HTTP codes indicating health (default: `404`)

#### Task Configuration
- **TaskCpu**: Select CPU units based on application needs
  - Light applications: `256` or `512`
  - Medium applications: `1024` or `2048`
  - Heavy applications: `4096` or `8192`
- **TaskMemory**: Select memory based on application needs
  - Must be compatible with selected CPU
  - Refer to [AWS Fargate task sizing](https://docs.aws.amazon.com/AmazonECS/latest/developerguide/task-cpu-memory-error.html)

#### Network Configuration
- **VpcId**: Select your existing VPC from dropdown
- **PublicSubnetIds**: Select 2 public subnets in different AZs
- **FargateSubnetIds**: Select 2 private subnets in different AZs
- **DatabaseSubnetIds**: Select 2 isolated private subnets in different AZs

#### Database Configuration
- **RdsLicenseModel**: Choose Oracle license model
  - `bring-your-own-license`: If you have Oracle licenses
  - `license-included`: AWS-provided Oracle licenses (more expensive)
- **RdsInstanceClass**: Select database instance size
  - Development: `db.t3.medium`
  - Production: `db.m5.large` or larger
- **RdsProvisionedStorage**: Database storage in GB (minimum: `100`)

#### SSL Configuration (Optional)
- **ServerCertificateName**: Enter IAM certificate name (leave blank for HTTP only)

### Step 4: Configure Stack Options

#### Tags (Recommended)
Add tags for resource management:
- **Environment**: `prod`, `dev`, `test`
- **Project**: `spydor`
- **Owner**: Your team/department
- **CostCenter**: Billing code

#### Permissions
- **IAM role**: Select appropriate IAM role if required
- **Stack policy**: Leave default unless specific restrictions needed

#### Advanced Options
- **Stack failure options**: Select **Roll back all stack resources**
- **Termination protection**: Enable for production stacks

Click **Next**

### Step 5: Review and Deploy

#### Review Configuration
1. **Template**: Verify correct template is selected
2. **Parameters**: Review all parameter values carefully
3. **Tags**: Confirm tags are correct
4. **Estimated cost**: Review cost estimate if available

#### Capabilities and Acknowledgments
Check the following boxes:
- ☑️ **I acknowledge that AWS CloudFormation might create IAM resources**
- ☑️ **I acknowledge that AWS CloudFormation might create IAM resources with custom names**
- ☑️ **I acknowledge that AWS CloudFormation might require the following capability: CAPABILITY_AUTO_EXPAND**

#### Deploy Stack
1. Click **Submit** to start deployment
2. Monitor deployment progress in the **Events** tab
3. Deployment typically takes 15-25 minutes

### Step 6: Monitor Deployment Progress

#### CloudFormation Events
Watch the **Events** tab for:
- **CREATE_IN_PROGRESS**: Resources being created
- **CREATE_COMPLETE**: Resources successfully created
- **CREATE_FAILED**: Any failures (see troubleshooting section)

#### Key Milestones
1. **VPC Resources**: Security groups created first
2. **Storage Resources**: S3 buckets, EFS file system
3. **Database**: RDS instance creation (longest step, ~10-15 minutes)
4. **Compute**: ECS cluster, task definition
5. **Load Balancer**: ALB and listeners
6. **Service**: ECS service starts containers

### Step 7: Verify Deployment

#### Check Stack Status
- Stack status should show **CREATE_COMPLETE**
- All resources should show **CREATE_COMPLETE** status

#### Verify Application Load Balancer
1. Navigate to **EC2 Console** → **Load Balancers**
2. Find your ALB (named with stack prefix)
3. Copy the **DNS name**
4. Test HTTP access: `http://your-alb-dns-name`
5. Test HTTPS access (if configured): `https://your-alb-dns-name`

#### Check ECS Service
1. Navigate to **ECS Console** → **Clusters**
2. Click on your cluster
3. Check **Services** tab - should show **ACTIVE** status
4. Check **Tasks** tab - should show **RUNNING** tasks
5. Review **Events** for any issues

#### Verify Database
1. Navigate to **RDS Console** → **Databases**
2. Find your Oracle instance
3. Status should be **Available**
4. Note the **Endpoint** for application configuration

#### Check Application Logs
1. Navigate to **CloudWatch Console** → **Log groups**
2. Find log group: `/aws/ecs/spydor-infra-fargate`
3. Check recent log streams for application startup messages

## Post-Deployment Configuration

### 1. Database Setup

#### Connect to Database
Use the RDS endpoint and credentials from AWS Secrets Manager:
```bash
# Get database credentials
aws secretsmanager get-secret-value --secret-id <secret-arn>

# Connect using Oracle client
sqlplus admin/<password>@<rds-endpoint>:1521/ORCL
```

#### Create Application Schema
Run your application's database setup scripts:
- Create required tables, indexes, sequences
- Create application users and grant permissions
- Load initial data if required

### 2. Application Configuration

#### Environment Variables
If your application needs environment variables, update the task definition:
1. Navigate to **ECS Console** → **Task Definitions**
2. Create new revision with environment variables
3. Update service to use new task definition

#### Application Secrets
Store sensitive configuration in AWS Secrets Manager:
1. Create secrets for API keys, passwords, etc.
2. Grant task role permission to read secrets
3. Update application to retrieve secrets at runtime

### 3. DNS Configuration

#### Custom Domain (Optional)
To use a custom domain name:
1. **Route 53**: Create hosted zone for your domain
2. **DNS Records**: Create CNAME or ALIAS record pointing to ALB DNS name
3. **SSL Certificate**: Ensure certificate matches your domain name

### 4. Monitoring Setup

#### CloudWatch Alarms
Create alarms for:
- **ECS Service**: CPU/Memory utilization
- **ALB**: Target health, response time
- **RDS**: CPU, connections, storage
- **Application**: Custom metrics if available

#### Log Monitoring
- Set up log filters for error patterns
- Create alarms for application errors
- Configure log retention policies

## Troubleshooting Common Deployment Issues

### Stack Creation Failures

#### Insufficient Permissions
**Error**: Access denied creating resources
**Solution**: 
- Verify IAM permissions include all required services
- Check permissions boundary allows required actions
- Ensure role prefix matches requirements

#### VPC/Subnet Configuration Issues
**Error**: Invalid subnet configuration
**Solution**:
- Verify subnets are in different AZs
- Check route tables have correct routes
- Ensure subnets have sufficient IP addresses

#### Database Creation Failures
**Error**: DB subnet group invalid
**Solution**:
- Verify database subnets are in different AZs
- Check subnet group doesn't already exist
- Ensure subnets have sufficient IP space

### Service Deployment Issues

#### Tasks Not Starting
**Symptoms**: ECS service shows 0 running tasks
**Troubleshooting**:
1. Check ECS service events for error messages
2. Review CloudWatch logs for container startup errors
3. Verify container image is accessible
4. Check task definition resource allocation

#### Health Check Failures
**Symptoms**: Tasks start but ALB shows unhealthy targets
**Troubleshooting**:
1. Verify health check path returns expected status code
2. Check container port matches ALB target group port
3. Ensure application starts within grace period
4. Review security group rules allow ALB → container traffic

#### Database Connection Issues
**Symptoms**: Application can't connect to database
**Troubleshooting**:
1. Verify database security group allows Fargate access
2. Check database endpoint and port in application config
3. Verify credentials in Secrets Manager
4. Test network connectivity between subnets

### SSL Certificate Issues

#### Certificate Not Found
**Error**: Certificate ARN invalid
**Solution**:
- Verify certificate name is correct
- Check certificate was uploaded to correct region
- Ensure certificate is in IAM (not ACM)

#### HTTPS Listener Fails
**Error**: Certificate validation failed
**Solution**:
- Verify certificate format is correct
- Check private key matches certificate
- Ensure certificate chain is complete

## Updating the Stack

### Parameter Updates
To update stack parameters:
1. Navigate to **CloudFormation Console**
2. Select your stack
3. Click **Update** → **Use current template**
4. Modify parameters as needed
5. Review changes and update

### Template Updates
To deploy template changes:
1. Click **Update** → **Replace current template**
2. Upload new template file
3. Review parameter changes
4. Deploy update

### Rolling Updates
ECS services support rolling updates:
- New task definition versions deploy gradually
- Old tasks drain connections before termination
- Zero-downtime deployments for application updates

## Stack Deletion

### Pre-Deletion Checklist
Before deleting the stack:
- ☑️ Backup any important data from RDS
- ☑️ Export any required files from EFS
- ☑️ Save any important logs from CloudWatch
- ☑️ Document any custom configurations

### Deletion Process
1. Navigate to **CloudFormation Console**
2. Select your stack
3. Click **Delete**
4. Confirm deletion
5. Monitor deletion progress

### Manual Cleanup
Some resources may require manual cleanup:
- **S3 Buckets**: Empty buckets if they contain data
- **EFS**: Delete file system if it has data
- **Secrets Manager**: Delete secrets if no longer needed
- **IAM Certificates**: Remove uploaded certificates

## Best Practices

### Security
- Use HTTPS in production environments
- Regularly rotate database credentials
- Monitor CloudTrail for API access
- Enable VPC Flow Logs for network monitoring

### Performance
- Monitor CloudWatch metrics and adjust resources
- Use appropriate instance sizes for workload
- Consider auto-scaling for variable loads
- Optimize database queries and indexing

### Cost Management
- Right-size resources based on actual usage
- Use Reserved Instances for predictable workloads
- Implement lifecycle policies for logs and backups
- Monitor costs with AWS Cost Explorer

### Operational Excellence
- Tag all resources consistently
- Document custom configurations
- Implement proper backup strategies
- Plan for disaster recovery scenarios

This deployment guide provides step-by-step instructions for successfully deploying the Spydor infrastructure stack through the AWS Console. Follow each section carefully and refer to the troubleshooting section if you encounter any issues during deployment.