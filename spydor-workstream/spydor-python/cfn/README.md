# Spydor Infrastructure Stack - Comprehensive Guide

## Overview

This CloudFormation template deploys a complete containerized application infrastructure on AWS, designed to host customer-provided applications in a secure, scalable environment. The stack includes a VPC with multiple subnet tiers, an Application Load Balancer, ECS Fargate containers, an Oracle RDS database, EFS shared storage, and S3 buckets for application data.

## Architecture Components

### 1. Virtual Private Cloud (VPC)
- **Purpose**: Provides isolated network environment for all resources
- **Configuration**: Uses customer-selected existing VPC
- **Security**: Network-level isolation with security groups controlling traffic flow

### 2. Subnets (Customer-Selected)
The stack requires three types of subnets across multiple Availability Zones:

#### Public Subnets (2 required)
- **Purpose**: Host the Application Load Balancer
- **Requirements**: Must have Transit Gateway route for internet access, different AZs
- **Traffic**: Inbound internet traffic on ports 80 and 443

#### Private Subnets - Fargate (2 required)  
- **Purpose**: Host ECS Fargate containers
- **Requirements**: Private subnets in different AZs (no internet access needed)
- **Traffic**: Receives traffic from ALB, connects to database and EFS

#### Private Subnets - Database (2 required)
- **Purpose**: Host RDS Oracle database
- **Requirements**: Isolated subnets with no internet access, different AZs
- **Traffic**: Only accepts connections from Fargate containers

### 3. Application Load Balancer (ALB)
- **Purpose**: Distributes incoming traffic to Fargate containers
- **Listeners**: 
  - HTTP (Port 80): Can forward to containers or redirect to HTTPS
  - HTTPS (Port 443): Terminates SSL and forwards to containers
- **Health Checks**: Monitors container health on specified path
- **Security**: Internet-facing with security group allowing ports 80/443

### 4. ECS Fargate Cluster
- **Purpose**: Runs containerized applications without managing servers
- **Task Definition**: Defines container specifications, CPU, memory, and volumes
- **Service**: Maintains desired number of running tasks with auto-recovery
- **Networking**: Uses AWS VPC networking mode for security
- **Logging**: Sends container logs to CloudWatch Logs

### 5. Oracle RDS Database
- **Purpose**: Provides managed Oracle database service
- **Configuration**: 
  - Multi-AZ deployment for high availability
  - Encrypted storage (gp3 for performance)
  - Automated backups and maintenance
- **Security**: 
  - Located in isolated database subnets
  - Security group allows only Fargate access on port 1521
  - Master credentials stored in AWS Secrets Manager

### 6. Elastic File System (EFS)
- **Purpose**: Provides shared, persistent file storage for containers
- **Features**:
  - Encrypted at rest and in transit
  - Scales automatically
  - Concurrent access from multiple containers
- **Mount Targets**: Deployed in Fargate subnets for container access
- **Security**: Security group allows NFS traffic (port 2049) from Fargate

### 7. S3 Buckets
Two S3 buckets are created for application use:

#### Logs Bucket
- **Purpose**: Store application logs or other logging data
- **Security**: SSL-only access policy enforced

#### MDL Bucket  
- **Purpose**: Store application data, files, or backups
- **Security**: SSL-only access policy enforced

### 8. Security Groups
Multiple security groups control network traffic:

#### ALB Security Group
- **Inbound**: Ports 80 and 443 from internet (0.0.0.0/0)
- **Outbound**: All traffic allowed

#### Fargate Security Group
- **Inbound**: Port 8080 from ALB security group only
- **Outbound**: All traffic allowed (for database, EFS, internet access)

#### Database Security Group
- **Inbound**: Port 1521 from Fargate security group only
- **Outbound**: Minimal ICMP traffic (effectively no outbound)

#### EFS Security Group
- **Inbound**: Port 2049 from Fargate security group only
- **Outbound**: Minimal ICMP traffic (effectively no outbound)

### 9. IAM Roles
Two IAM roles support the Fargate tasks:

#### Task Role
- **Purpose**: Provides permissions for the application running in the container
- **Permissions**: Currently minimal, can be expanded based on application needs

#### Execution Role
- **Purpose**: Allows ECS to manage the container (pull images, write logs)
- **Permissions**: AmazonECSTaskExecutionRolePolicy for basic ECS operations

## SSL Certificate Requirements

### For HTTPS Support
If you want to enable HTTPS (recommended for production), you must provide an SSL certificate.

#### Option 1: Self-Signed Certificate (Testing Only)
For testing purposes, you can create a self-signed certificate:

1. **Generate Certificate**:
   ```bash
   # Generate private key
   openssl genrsa -out private-key.pem 2048
   
   # Generate self-signed certificate
   openssl req -new -x509 -key private-key.pem -out cert.pem -days 365 \
     -subj "/C=US/ST=State/L=City/O=Organization/CN=your-domain.com"
   ```

2. **Upload to IAM**:
   ```bash
   aws iam upload-server-certificate \
     --server-certificate-name your-cert-name \
     --certificate-body file://cert.pem \
     --private-key file://private-key.pem
   ```

#### Option 2: Commercial Certificate
For production use, obtain a certificate from a trusted Certificate Authority:

1. **Generate Certificate Signing Request (CSR)**:
   ```bash
   openssl genrsa -out private-key.pem 2048
   openssl req -new -key private-key.pem -out cert.csr
   ```

2. **Submit CSR to Certificate Authority** and receive signed certificate

3. **Upload to IAM**:
   ```bash
   aws iam upload-server-certificate \
     --server-certificate-name your-cert-name \
     --certificate-body file://cert.pem \
     --private-key file://private-key.pem \
     --certificate-chain file://chain.pem  # If intermediate certificates exist
   ```

#### Certificate Management
- Certificate names in IAM must be unique within your account
- Certificates can be updated by uploading new versions
- Old certificates should be deleted after successful deployment of new ones

## Traffic Flow

### HTTPS Request Flow
1. **User → ALB (Port 443)**: User makes HTTPS request to ALB's DNS name
2. **SSL Termination**: ALB decrypts traffic using IAM server certificate
3. **ALB → Fargate (Port 8080)**: ALB forwards HTTP traffic to healthy containers
4. **Container Processing**: Application processes request, may access database/EFS
5. **Response**: ALB encrypts response and sends HTTPS back to user

### HTTP Request Flow
1. **User → ALB (Port 80)**: User makes HTTP request
2. **ALB → Fargate (Port 8080)**: ALB forwards HTTP traffic directly (no encryption)
3. **Container Processing**: Same as HTTPS flow
4. **Response**: Plain HTTP response sent back to user

### Internal Communication
- **Fargate ↔ RDS**: Port 1521 for Oracle database connections
- **Fargate ↔ EFS**: Port 2049 for NFS file system access
- **Fargate**: No direct internet access required (container images pulled via VPC endpoints if needed)

## Customer Container Requirements

When the customer provides their container, several aspects may need adjustment:

### Required Information from Customer

#### Container Specifications
- **Container Image URI**: ECR repository URL or Docker Hub image
- **Container Port**: Port the application listens on (currently defaulted to 8080)
- **Resource Requirements**: 
  - CPU units (256, 512, 1024, 2048, 4096, 8192)
  - Memory in MB (512-8192, must be compatible with CPU)

#### Application Configuration
- **Health Check Endpoint**: Path for ALB health checks (currently "/")
- **Health Check Success Codes**: HTTP codes indicating healthy status (currently "404")
- **Environment Variables**: Any required environment variables
- **Startup Time**: How long the application takes to start (affects health check grace period)

#### Database Requirements
- **Database Usage**: Does the application use the Oracle database?
- **Database Schema**: Required database objects, users, permissions
- **Connection Method**: How the application connects (JDBC URL, connection pooling)

#### File System Requirements
- **EFS Usage**: Does the application need shared file storage?
- **Mount Points**: Where in the container to mount EFS (currently "/mnt/efs")
- **File Permissions**: Required file system permissions and ownership

#### External Dependencies
- **Outbound Connections**: External services, APIs, or repositories the application needs
- **Additional Ports**: Any additional ports the application uses
- **Load Balancer Configuration**: Any special ALB configuration needed

### Potential Changes Required

#### Task Definition Updates
```yaml
# May need to update:
ContainerDefinitions:
  - Image: customer-provided-image
    PortMappings:
      - ContainerPort: customer-port  # May not be 8080
    Environment:  # May need environment variables
      - Name: DATABASE_URL
        Value: !Sub "jdbc:oracle:thin:@${DatabaseEndpoint}:1521:ORCL"
    MountPoints:  # May need different mount points
      - ContainerPath: /app/data
        SourceVolume: efs-volume
```

#### Security Group Adjustments
```yaml
# May need additional ports
SecurityGroupIngress:
  - FromPort: customer-port
    ToPort: customer-port
    SourceSecurityGroupId: !Ref ALBSecurityGroup
```

#### Health Check Configuration
```yaml
# May need different health check settings
HealthCheckPath: /health  # Customer's health endpoint
Matcher:
  HttpCode: "200"  # Customer's success codes
HealthCheckIntervalSeconds: 30
HealthCheckTimeoutSeconds: 5
HealthyThresholdCount: 2
UnhealthyThresholdCount: 5
```

#### Resource Requirements
- **CPU/Memory**: May need adjustment based on application requirements
- **Storage**: May need additional EBS volumes for application data
- **Network**: May need additional security group rules for external services

#### Database Configuration
- **Schema Setup**: May need custom database initialization scripts
- **User Permissions**: May need specific database users and permissions
- **Connection Pooling**: May need to configure connection pool settings

#### Additional AWS Services
Customer applications might require:
- **ElastiCache**: For caching layer
- **SQS/SNS**: For message queuing
- **Lambda**: For serverless functions
- **API Gateway**: For API management
- **CloudFront**: For content delivery
- **Route 53**: For DNS management

## Monitoring and Logging

### CloudWatch Logs
- Container logs are automatically sent to CloudWatch Logs
- Log group: `/aws/ecs/spydor-infra-fargate`
- Retention: 7 days (configurable)

### Monitoring Capabilities
- **ECS Service Metrics**: CPU, memory, task count
- **ALB Metrics**: Request count, latency, error rates
- **RDS Metrics**: Database performance, connections
- **EFS Metrics**: File system usage, throughput

### Recommended Monitoring Setup
- CloudWatch Alarms for high CPU/memory usage
- ALB target health monitoring
- Database connection monitoring
- Custom application metrics (if supported by customer application)

## Security Considerations

### Network Security
- Multi-tier architecture with proper subnet isolation
- Security groups follow principle of least privilege
- No direct internet access to application or database tiers

### Data Security
- Encryption at rest for RDS, EFS, and S3
- Encryption in transit for HTTPS traffic
- Database credentials managed by AWS Secrets Manager

### Access Control
- IAM roles with minimal required permissions
- No hardcoded credentials in configuration
- Separate roles for task execution and application permissions

### Compliance
- VPC Flow Logs can be enabled for network monitoring
- CloudTrail integration for API call logging
- AWS Config for compliance monitoring

## Scalability and High Availability

### Auto Scaling
- ECS Service can be configured for auto scaling based on CPU/memory
- ALB automatically distributes traffic across healthy targets
- RDS Multi-AZ provides database failover capability

### Disaster Recovery
- Multi-AZ deployment across different availability zones
- RDS automated backups with point-in-time recovery
- EFS automatically replicates across AZs

### Performance Optimization
- gp3 storage for RDS provides better performance than gp2
- EFS provides high throughput for file operations
- ALB connection draining for graceful deployments

## Cost Optimization

### Resource Sizing
- Start with smaller instance sizes and scale up as needed
- Monitor CloudWatch metrics to right-size resources
- Use Fargate Spot for non-critical workloads (if applicable)

### Storage Optimization
- EFS Intelligent Tiering for cost optimization
- S3 lifecycle policies for log archival
- RDS storage auto-scaling to avoid over-provisioning

## Troubleshooting Common Issues

### Container Won't Start
- Check CloudWatch Logs for container startup errors
- Verify container image is accessible
- Check resource allocation (CPU/memory)
- Verify environment variables and configuration

### Health Check Failures
- Verify health check path returns expected status code
- Check container port configuration
- Ensure application starts within health check grace period
- Review security group rules

### Database Connection Issues
- Verify database security group allows Fargate access
- Check database endpoint and port configuration
- Verify credentials in Secrets Manager
- Check VPC routing between subnets

### EFS Mount Issues
- Verify EFS mount targets are in correct subnets
- Check EFS security group allows NFS traffic
- Verify EFS file system policy allows access
- Check container mount point configuration

This comprehensive guide provides the foundation for deploying and managing the Spydor infrastructure stack. The modular design allows for easy customization based on specific customer requirements while maintaining security and scalability best practices.