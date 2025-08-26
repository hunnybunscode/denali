# Customer Requirements Checklist

## Pre-Deployment Information Required from Customer

This document outlines all information that must be collected from the customer before deploying the Spydor infrastructure stack.

## 1. Network Configuration

### VPC and Subnet Information
- [ ] **VPC ID**: Which existing VPC should be used?
- [ ] **Public Subnet IDs** (2 required): Subnets with Transit Gateway routes for ALB
  - Must be in different Availability Zones
  - Must have internet access via Transit Gateway
- [ ] **Private Subnet IDs - Fargate** (2 required): Subnets for containers
  - Must be in different Availability Zones  
  - No internet access required
- [ ] **Private Subnet IDs - Database** (2 required): Isolated subnets for RDS
  - Must be in different Availability Zones
  - Must be completely isolated (no internet access)

### PROJADMIN Requirements
- [ ] **IAM Role Prefix**: Required prefix for all IAM roles (e.g., `AFC2S_`)
- [ ] **Permissions Boundary ARN**: ARN of the IAM permissions boundary policy

### VPC Endpoints
- [ ] **S3 VPC Endpoint**: Does the VPC have an S3 VPC endpoint configured?
  - Required for: Container image pulls from ECR, application S3 access
  - Type: Gateway endpoint for S3
- [ ] **ECR VPC Endpoints**: Are ECR VPC endpoints configured?
  - Required for: Private container image pulls
  - Endpoints needed: `com.amazonaws.region.ecr.dkr`, `com.amazonaws.region.ecr.api`
- [ ] **CloudWatch VPC Endpoints**: Are CloudWatch VPC endpoints configured?
  - Required for: Application logging and metrics
  - Endpoints needed: `com.amazonaws.region.logs`, `com.amazonaws.region.monitoring`
- [ ] **SSM VPC Endpoints**: Are Systems Manager VPC endpoints configured?
  - Required for: Parameter Store access, session management
  - Endpoints needed: `com.amazonaws.region.ssm`, `com.amazonaws.region.ssmmessages`
- [ ] **Secrets Manager VPC Endpoint**: Is Secrets Manager VPC endpoint configured?
  - Required for: Database credentials and application secrets
  - Endpoint needed: `com.amazonaws.region.secretsmanager`

## 2. Application Configuration

### Container Specifications
- [ ] **Container Image URI**: Full path to container image
  - ECR: `123456789012.dkr.ecr.region.amazonaws.com/app:tag`
  - Docker Hub: `organization/image:tag`
  - Other registry: Full URI with credentials if private
- [ ] **Container Port**: Port the application listens on (default: 8080)
- [ ] **Application Protocol**: HTTP, HTTPS, or both?

### Resource Requirements
- [ ] **CPU Requirements**: Select appropriate Fargate CPU units
  - `256` (0.25 vCPU) - Light applications
  - `512` (0.5 vCPU) - Small applications  
  - `1024` (1 vCPU) - Medium applications
  - `2048` (2 vCPU) - Large applications
  - `4096` (4 vCPU) - Heavy applications
  - `8192` (8 vCPU) - Very heavy applications

- [ ] **Memory Requirements**: Must be compatible with CPU selection
  - Refer to [AWS Fargate task sizing guide](https://docs.aws.amazon.com/AmazonECS/latest/developerguide/task-cpu-memory-error.html)
  - Typical ranges: 512MB - 8192MB

### Health Check Configuration
- [ ] **Health Check Path**: Endpoint for ALB health checks (e.g., `/health`, `/status`)
- [ ] **Health Check Success Codes**: HTTP status codes indicating healthy application
  - Common: `200`, `200-299`
- [ ] **Application Startup Time**: How long does the application take to start?
  - Used to configure health check grace period

## 3. Database Requirements

### Oracle Database Configuration
- [ ] **Database Usage**: Does the application require the Oracle database?
- [ ] **License Model**: 
  - `bring-your-own-license` - Customer provides Oracle licenses
  - `license-included` - AWS provides Oracle licenses (higher cost)
- [ ] **Instance Class**: Database performance requirements
  - `db.t3.medium` - Development/testing
  - `db.t3.large` - Small production
  - `db.m5.large` - Medium production
  - `db.m5.xlarge` - Large production
- [ ] **Storage Requirements**: Initial storage size in GB (minimum 100GB)
- [ ] **Engine Version**: Preferred Oracle version (default: 19.0.0.0.ru-2025-07.rur-2025-07.r1)



## 4. File Storage Requirements

### EFS Configuration
- [ ] **File Storage Usage**: Does the application require shared file storage?
- [ ] **Mount Points**: Where should EFS be mounted in the container?
  - Default: `/mnt/efs`
  - Custom path: Specify required path
- [ ] **File Permissions**: Required file system permissions and ownership


## 5. SSL Certificate Requirements

### HTTPS Configuration
- [ ] **HTTPS Required**: Does the application require HTTPS?
- [ ] **IAM Server Certificate ARN**: ARN of certificate uploaded to IAM
  - Format: `arn:aws-us-gov:iam::account-id:server-certificate/certificate-name`

#### Instructions for Customer: Uploading SSL Certificate to IAM

If you require HTTPS, you must upload your SSL certificate to AWS IAM before deployment:

**Using AWS CLI:**
```bash
aws iam upload-server-certificate \
  --server-certificate-name your-certificate-name \
  --certificate-body file://certificate.pem \
  --private-key file://private-key.pem \
  --certificate-chain file://certificate-chain.pem
```

**Using AWS Console:**
1. Navigate to IAM Console → Server Certificates
2. Click "Upload a server certificate"
3. Provide certificate name, certificate body, private key, and certificate chain
4. Note the certificate ARN for deployment

**After upload, provide us with the certificate ARN from the IAM console.**

## 6. Required Application Endpoints

### Mandatory Endpoints
The customer application **MUST** implement the following endpoints for proper infrastructure operation:

- [ ] **Health Check Endpoint**: Application must provide a health check endpoint
  - Path: `/health`, `/status`, or custom path specified by customer
  - Response: HTTP 200 status code when application is healthy
  - Content: Can be simple text ("OK") or JSON health status
  - Purpose: Used by ALB for health checks and auto-scaling decisions

- [ ] **Root Endpoint**: Application should respond to root path requests
  - Path: `/` 
  - Response: HTTP 200 or appropriate application response
  - Purpose: Basic connectivity testing and load balancer verification

### Optional but Recommended Endpoints
- [ ] **Metrics Endpoint**: For monitoring and observability
  - Path: `/metrics` or `/actuator/metrics`
  - Response: Application metrics in Prometheus or JSON format
  - Purpose: CloudWatch custom metrics and monitoring

- [ ] **Info Endpoint**: Application information
  - Path: `/info` or `/actuator/info`
  - Response: Application version, build info, etc.
  - Purpose: Deployment verification and troubleshooting

### Endpoint Requirements
- All endpoints must be accessible on the configured container port
- Health check endpoint must respond within 5 seconds
- Endpoints should not require authentication for infrastructure testing
- Must handle HTTP requests (HTTPS termination handled by ALB)

## 7. Testing and Validation

### Infrastructure Testing
- [ ] **Test Endpoints**: Verify all required endpoints are implemented
- [ ] **Load Balancer Testing**: Verify ALB can reach container health check
- [ ] **Database Connectivity**: Test database connection from container
- [ ] **File System Access**: Verify EFS mount functionality

## Pre-Deployment Checklist

Before beginning deployment, ensure you have collected:

### Required Information
- [ ] All network configuration details
- [ ] Container image and specifications
- [ ] Database requirements (usage and sizing)
- [ ] SSL certificate (if HTTPS required)
- [ ] PROJADMIN compliance requirements

### Customer Responsibilities
- [ ] Provide container image access
- [ ] Deliver SSL certificates (if required)
- [ ] Participate in infrastructure testing
- [ ] Approve final deployment

## Information Collection Template

Use this template when gathering information from the customer:

```
Customer: ___________________________
Project: ____________________________
Date: _______________________________

NETWORK CONFIGURATION
VPC ID: _____________________________
Public Subnet 1: ____________________
Public Subnet 2: ____________________
Fargate Subnet 1: ___________________
Fargate Subnet 2: ___________________
Database Subnet 1: __________________
Database Subnet 2: __________________

PROJADMIN REQUIREMENTS
Role Prefix: ________________________
Permissions Boundary ARN: ___________

APPLICATION DETAILS
Container Image: ____________________
Container Port: _____________________
CPU Requirements: ___________________
Memory Requirements: ________________
Health Check Path: __________________
Health Check Success Codes: _________

DATABASE CONFIGURATION
License Model: ______________________
Instance Class: ____________________
Storage Size: _______________________
Engine Version: ____________________

SSL CERTIFICATE
HTTPS Required: _____________________
IAM Certificate ARN: ________________

ADDITIONAL REQUIREMENTS
Special Network Requirements: _______
Custom Infrastructure Needs: ________
```

## Next Steps

Once all information is collected:

1. **Review and Validate**: Confirm all requirements with customer
2. **Prepare Deployment**: Set up deployment parameters
3. **Schedule Deployment**: Coordinate deployment timing
4. **Execute Deployment**: Follow deployment guide
5. **Test and Validate**: Verify all functionality works as expected
6. **Hand Over**: Transfer operational responsibility to customer team

This comprehensive checklist ensures all necessary information is collected before deployment, reducing the risk of deployment issues and post-deployment changes.