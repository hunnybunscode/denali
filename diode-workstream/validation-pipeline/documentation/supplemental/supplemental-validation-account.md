# Validation Account - Security Scanning and Transfer Orchestration

This directory contains the complete CloudFormation templates, Lambda functions, and EC2 processing code for deploying the Validation Account infrastructure of the cross-account diode workstream. The Validation Account serves as the core security and validation pipeline, performing comprehensive file scanning, validation, and orchestrating the transfer process to the Diode Account.

## Overview

The Validation Account is the heart of the secure data transfer pipeline, responsible for:

- Receiving files from Customer Accounts via secure ingestion buckets
- Performing multi-layer security validation (file type, antivirus, content)
- Orchestrating scalable EC2-based processing infrastructure
- Managing transfer requests to the Diode Account
- Providing comprehensive monitoring and alerting
- Maintaining audit trails and compliance records

## Components Deployed

### 1. Core Infrastructure Stacks

#### Main Stack (`aftac_main_stack.yaml`)

Master orchestration template that deploys all sub-stacks:

**Sub-Stacks Deployed:**

- **Logging Stack**: Centralized S3 access logging
- **Ingest Stack**: File ingestion and initial processing infrastructure
- **Pipeline Stack**: Core validation and transfer pipeline
- **SFTP Stack**: Secure file transfer protocol server (low-side environments only)

**Key Parameters:**

- Network configuration (VPC, subnets, security groups)
- Cross-account integration settings
- Monitoring and alerting thresholds
- Lifecycle and retention policies

#### Logging Stack (`aftac_logging_stack.yaml`)

Centralized logging infrastructure:

- **Access Log Bucket**: S3 bucket for storing access logs from all other buckets
- **Lifecycle Policies**: Automatic transition to cheaper storage classes
- **Encryption**: KMS encryption for all log data

#### Ingest Stack (`aftac_ingest_stack.yaml`)

File ingestion and initial processing:

- **VPC Security Groups**: Network access controls for EC2 instances
- **SQS Queues**: Message queuing for asynchronous processing
- **Dead Letter Queues**: Capture failed messages for analysis

#### Pipeline Stack (`aftac_pipeline_stack.yaml`)

Core processing pipeline with comprehensive components:

- **S3 Buckets**: Multiple buckets for different processing stages
- **Lambda Functions**: Serverless processing functions
- **EC2 Auto Scaling**: Scalable virus scanning infrastructure
- **DynamoDB Table**: Transfer status and audit tracking
- **SNS Topics**: Notifications for various events
- **CloudWatch Alarms**: Monitoring and alerting

### 2. Ingestion Bucket (`aftac_ingestion_bucket.yaml`)

**Purpose**: Secure S3 bucket for receiving files from Customer Accounts

**Key Features:**

- **KMS Encryption**: Customer-managed key with strict access policies
- **Public Access Blocked**: All public access explicitly denied
- **Event Notifications**: Triggers Lambda functions on object creation
- **Lifecycle Management**: Automatic cleanup based on retention policies
- **Cross-Account Access**: Secure permissions for Customer Account uploads

**Bucket Tags (Metadata for Processing):**

- `MappingId`: UUID for transfer routing (mutually exclusive with DestinationBucket)
- `DestinationBucket`: Direct bucket destination (mutually exclusive with MappingId)
- `DestinationMappingKey`: Key for destination mapping lookup via SSM
- `DfdlBound`: Flag indicating DFDL pipeline processing ("Yes"/"No")
- `DataOwner`: Data ownership information for governance
- `DataSteward`: Data stewardship contact
- `GovPOC`: Government point of contact
- `KeyOwner`: Encryption key ownership information

**Security Policies:**

- TLS-only access (denies non-HTTPS requests)
- Presigned URL time limits (5 minutes maximum)
- Required KMS encryption for all uploads
- Cross-account role-based access control

### 3. EC2 Processing Infrastructure (`ec2-files/`)

**Purpose**: Scalable EC2 instances performing intensive file processing

#### Core Processing Files:

**`validation.py`** - File Type and Content Validation

- Validates file types against approved whitelists
- Performs MIME type verification
- Handles ZIP file recursive validation
- Implements maximum depth protection for nested archives
- Routes files based on validation results

**`clamscan.py`** - Antivirus Scanning

- Integrates with ClamAV daemon for malware detection
- Processes scan results (clean, infected, error)
- Routes files to appropriate destination buckets
- Sends SNS notifications for security events
- Maintains detailed scan logs

**`utils.py`** - Shared Utilities

- S3 operations (upload, download, delete, tagging)
- SQS message handling (receive, delete, visibility timeout)
- SNS notification publishing
- SSM parameter retrieval
- Bucket tag processing and combination
- File validation helper functions

**`config.py`** - Configuration Management

- SSM parameter definitions
- Resource suffix handling
- Instance information tracking
- Logging configuration

**`sqs_poller.py`** - SQS Message Polling Service

- Continuous polling of AV scan queue
- Message processing coordination
- Error handling and retry logic
- Service lifecycle management

#### Processing Flow:

1. **File Reception**: Files uploaded to ingestion bucket trigger processing
2. **Initial Validation**: File type and format validation
3. **ZIP Handling**: Recursive validation of compressed archives (with depth limits)
4. **Antivirus Scanning**: ClamAV malware detection
5. **Routing Decision**: Based on scan results and bucket tags:
   - **Clean Files**: → Data Transfer bucket or DFDL pipeline
   - **Infected Files**: → Quarantine bucket + SNS alert
   - **Invalid Files**: → Invalid files bucket + detailed error tags
   - **Scan Errors**: → Invalid files bucket + error notification

### 4. Lambda Functions (`lambda/`)

#### Object Tagger (`object_tagger.py`)

- **Trigger**: S3 events on ingestion bucket uploads
- **Purpose**: Routes file metadata to SQS queue for EC2 processing
- **Features**:
  - Lightweight event processing
  - SQS message publishing
  - Error handling and logging

#### Presigner (`presigner.py`)

- **Trigger**: API Gateway requests
- **Purpose**: Generates pre-signed URLs for secure file uploads
- **Features**:
  - KMS encryption enforcement
  - Configurable expiration times
  - S3v4 signature support
  - Query parameter validation

#### Transfer Result (`transfer_result.py`)

- **Trigger**: SQS messages from Diode Account
- **Purpose**: Processes transfer completion notifications
- **Features**:
  - DynamoDB audit logging
  - Failed transfer handling
  - File cleanup operations
  - SNS notifications for failures
  - Data governance tag extraction

#### Destination Parser (`dest-parser/`)

- **Purpose**: Multi-destination file copying based on mapping keys
- **Features**:
  - SSM parameter-based destination lookup
  - Batch file copying to multiple buckets
  - Error handling for individual copy operations
  - Support for space-separated mapping keys

### 5. Additional Infrastructure Components

#### SFTP Stack (`aftac_sftp_stack.yaml`)

- **Purpose**: Secure file transfer protocol server for direct uploads
- **Deployment**: Low-side environments only (excluded from high-side)
- **Features**:
  - AWS Transfer Family integration
  - VPC endpoint configuration
  - User management and SSH key handling
  - Integration with ingestion bucket

#### DFDL Stack (`aftac_dfdl_stack.yaml`)

- **Purpose**: Data Format Description Language processing pipeline
- **Features**:
  - Specialized file format processing
  - Integration with main processing pipeline
  - Custom validation rules for DFDL-bound files

#### Image Builder Stack (`aftac_image_builder_stack.yaml`)

- **Purpose**: Automated AMI creation for EC2 processing instances
- **Features**:
  - Automated security patching
  - ClamAV installation and configuration
  - Custom application deployment
  - Compliance and hardening

## Configuration Parameters

### Main Stack Parameters

#### General Configuration

| Parameter                      | Description                        | Default | Required |
| ------------------------------ | ---------------------------------- | ------- | -------- |
| `IamPrefix`                    | Required prefix for IAM resources  | `AFC2S` | Yes      |
| `PermissionsBoundaryPolicyArn` | ARN of permissions boundary policy | -       | Yes      |
| `ResourceSuffix`               | Suffix for AWS resource names      | -       | Yes      |

#### Networking Configuration

| Parameter          | Description                     | Example                           |
| ------------------ | ------------------------------- | --------------------------------- |
| `VpcId`            | VPC ID for deployment           | `vpc-12345678`                    |
| `VpcCidr`          | CIDR block of the VPC           | `10.0.0.0/16`                     |
| `PrivateSubnetIds` | List of private subnet IDs      | `subnet-12345678,subnet-87654321` |
| `S3PrefixListId`   | S3 service prefix list ID       | `pl-7a3a1b0f`                     |
| `DDBPrefixListId`  | DynamoDB service prefix list ID | `pl-1b4c2f9e`                     |

#### Pipeline Configuration

| Parameter                            | Description                     | Default |
| ------------------------------------ | ------------------------------- | ------- |
| `PipelineStackDiodeAccountId`        | Account ID for Diode Account    | -       |
| `PipelineStackPipelineAmiId`         | AMI ID for EC2 instances        | -       |
| `PipelineStackDfdlApprovedFileTypes` | DFDL-approved file extensions   | `xml`   |
| `PipelineExemptFileTypes`            | File types bypassing validation | `csv`   |
| `EmailEndPoint`                      | Email for SNS notifications     | -       |

#### Monitoring Configuration

| Parameter                 | Description                        | Default            |
| ------------------------- | ---------------------------------- | ------------------ |
| `AvScanQueueThreshold`    | Alert threshold for AV scan queue  | 50                 |
| `TransferQueueThreshold`  | Alert threshold for transfer queue | 50                 |
| `ResultQueueThreshold`    | Alert threshold for result queue   | 50                 |
| `QueueMonitoringInterval` | Queue monitoring frequency         | `rate(30 minutes)` |

#### Lifecycle Configuration

| Parameter                              | Description                        | Default |
| -------------------------------------- | ---------------------------------- | ------- |
| `TranstionToGlacierIR`                 | Days to transition to Glacier IR   | 60      |
| `TransitionToDeepArchive`              | Days to transition to Deep Archive | 150     |
| `FailedTransferBucketExpirationInDays` | Failed transfer retention          | 365     |
| `DataTransferBucketExpirationInDays`   | Data transfer retention            | 365     |
| `DfdlInputBucketExpirationInDays`      | DFDL input retention               | 365     |
| `InvalidFilesBucketExpirationInDays`   | Invalid files retention            | 365     |
| `AccessLogBucketExpirationInDays`      | Access log retention               | 365     |

### Ingestion Bucket Parameters

| Parameter                           | Description                  | Example                                |
| ----------------------------------- | ---------------------------- | -------------------------------------- |
| `IngestBucketMappingId`             | UUID for transfer routing    | `12346789-abcd-1234-abcd-123456789012` |
| `DfdlBound`                         | DFDL pipeline flag           | `Yes` or `No`                          |
| `IngestBucketDestinationBucket`     | Direct destination bucket    | `my-destination-bucket`                |
| `IngestBucketDestinationMappingKey` | Mapping key for destinations | `key1 key2 key3`                       |
| `IngestBucketDataOwner`             | Data owner information       | `John Doe`                             |
| `IngestBucketDataSteward`           | Data steward contact         | `Jane Smith`                           |
| `IngestBucketGovPoc`                | Government POC               | `Gov Contact`                          |
| `IngestBucketKeyOwner`              | Key owner information        | `Security Team`                        |

## Prerequisites

Before deploying the Validation Account infrastructure:

### 1. AWS Account Setup

- Administrative permissions in the Validation Account
- VPC with private subnets configured
- Internet Gateway or NAT Gateway for EC2 internet access
- Route tables properly configured

### 2. Network Requirements

- **Private Subnets**: At least 2 subnets in different AZs for high availability
- **Internet Access**: EC2 instances need internet access for:
  - ClamAV signature updates
  - AWS service API calls
  - SSM agent communication
- **Service Endpoints**: VPC endpoints for S3 and DynamoDB (recommended for security)

### 3. External Dependencies

- **AMI ID**: Custom AMI with ClamAV and processing software pre-installed
- **Template Storage**: S3 bucket containing all CloudFormation templates
- **Permissions Boundary**: Organization-specific IAM permissions boundary policy

### 4. Cross-Account Integration

- **Customer Account**: Must be configured to write to ingestion bucket
- **Diode Account**: Must be deployed to receive transfer requests

## Deployment Steps

### Option 1: AWS Console Deployment

#### Step 1: Prepare Template Storage

1. Create or identify S3 bucket for CloudFormation templates
2. Upload all `.yaml` files from the validation-account directory
3. Note the bucket name and prefix path

#### Step 2: Access CloudFormation Console

1. Log into AWS Management Console for Validation Account
2. Navigate to **CloudFormation** service
3. Select appropriate region for deployment

#### Step 3: Deploy Main Stack

1. Click **Create stack** → **With new resources (standard)**
2. **Template source**: Upload `aftac_main_stack.yaml`
3. Click **Next**

#### Step 4: Configure Main Stack Parameters

1. **Stack name**: `validation-account-main-stack`
2. **General Parameters**:
   - **IAM Prefix**: `AFC2S`
   - **Permissions Boundary Policy ARN**: Your organization's boundary policy
   - **Resource Suffix**: Unique identifier (e.g., `prod-east-1`)
3. **Templates Location**:
   - **Template Bucket Name**: S3 bucket containing templates
   - **Template Prefix**: Path prefix to templates
4. **Networking**:
   - **VPC ID**: Select your VPC
   - **VPC CIDR**: Enter VPC CIDR block
   - **Private Subnet IDs**: Select 2+ private subnets
   - **S3 Prefix List ID**: AWS S3 service prefix list
   - **DDB Prefix List ID**: AWS DynamoDB service prefix list
5. **Pipeline Stack**:
   - **Diode Account ID**: 12-digit account ID
   - **Pipeline AMI ID**: Custom AMI for EC2 instances
   - **DFDL Approved File Types**: `xml` (or customize)
   - **Exempt File Types**: `csv` (or customize)
   - **Email End Point**: Notification email address
6. **Monitoring Configuration**:
   - **Queue Thresholds**: Set alert thresholds (default: 50)
   - **Queue Monitoring Interval**: `rate(30 minutes)`
7. **Lifecycle Configuration**:
   - **Transition Days**: Configure storage class transitions
   - **Expiration Days**: Set retention periods for each bucket type
8. Click **Next**

#### Step 5: Configure Stack Options

1. **Tags** (Recommended):
   - `Environment`: `Production`
   - `Project`: `DiodeWorkstream`
   - `Account`: `Validation`
2. **Permissions**: Use current role
3. **Advanced options**: Leave defaults
4. Click **Next**

#### Step 6: Review and Deploy

1. Review all parameters carefully
2. **Capabilities**: Check all IAM-related acknowledgments
3. Click **Create stack**

#### Step 7: Monitor Deployment

1. Watch **Events** tab for progress
2. Deployment takes 15-30 minutes depending on complexity
3. Nested stacks will appear as deployment progresses
4. Status shows **CREATE_COMPLETE** when finished

#### Step 8: Deploy Individual Ingestion Buckets

For each ingestion bucket needed:

1. Create new stack using `aftac_ingestion_bucket.yaml`
2. Configure bucket-specific parameters
3. Deploy and verify

## Security Features

### 1. Multi-Layer File Validation

#### File Type Validation

- **Whitelist Approach**: Only approved file types allowed
- **MIME Type Verification**: Content-based validation beyond file extensions
- **Configurable Lists**: Separate lists for standard and DFDL-approved types
- **Exempt Types**: Bypass validation for specific file types (e.g., CSV)

#### ZIP File Handling

- **Recursive Validation**: Validates contents of compressed archives
- **Depth Protection**: Prevents zip bomb attacks with maximum depth limits
- **Individual File Validation**: Each file within archive validated separately
- **Rejection Policy**: Entire archive rejected if any file fails validation

#### Antivirus Scanning

- **ClamAV Integration**: Industry-standard open-source antivirus
- **Real-time Updates**: Automatic signature updates
- **Quarantine Process**: Infected files isolated immediately
- **Scan Logging**: Detailed logs of all scan results

### 2. Access Control and Encryption

#### IAM Security

- **Least Privilege**: All roles follow minimum required permissions
- **Cross-Account Policies**: Secure integration between accounts
- **Permissions Boundaries**: Organization-level permission limits
- **Service-Linked Roles**: AWS service integration with proper scoping

#### Encryption at Rest

- **Customer-Managed KMS**: All S3 buckets use customer-managed keys
- **Key Rotation**: Automatic annual key rotation enabled
- **Access Policies**: Strict key usage policies
- **Lambda Encryption**: Function environment variables encrypted

#### Encryption in Transit

- **TLS Enforcement**: All communications require HTTPS/TLS
- **Presigned URL Limits**: Time-limited secure upload URLs
- **API Gateway Integration**: Secure programmatic access

### 3. Network Security

#### VPC Isolation

- **Private Subnets**: EC2 instances in private subnets only
- **Security Groups**: Restrictive inbound/outbound rules
- **NACLs**: Additional network-level access controls
- **VPC Endpoints**: Direct AWS service access without internet

#### Monitoring and Logging

- **CloudWatch Integration**: Comprehensive metrics and alarms
- **CloudTrail Logging**: All API calls audited
- **VPC Flow Logs**: Network traffic monitoring
- **S3 Access Logging**: Detailed bucket access records

## Monitoring and Alerting

### 1. CloudWatch Metrics

#### Queue Monitoring

- **Queue Depth**: Number of messages waiting for processing
- **Message Age**: Time messages have been in queue
- **Processing Rate**: Messages processed per minute
- **Error Rate**: Failed message processing percentage

#### Lambda Metrics

- **Invocation Count**: Number of function executions
- **Duration**: Function execution time
- **Error Rate**: Function failure percentage
- **Throttles**: Rate limiting occurrences

#### EC2 Metrics

- **Instance Health**: Auto Scaling Group health checks
- **CPU Utilization**: Processing load monitoring
- **Memory Usage**: Memory consumption tracking
- **Network I/O**: Data transfer monitoring

### 2. SNS Notifications

#### Security Alerts

- **Infected Files**: Immediate notification of malware detection
- **Invalid Files**: Alerts for file validation failures
- **Failed Transfers**: Notification of transfer failures
- **System Errors**: Critical system component failures

#### Operational Alerts

- **Queue Thresholds**: Alerts when queues exceed configured limits
- **Processing Delays**: Notifications of processing backlogs
- **Resource Scaling**: Auto Scaling Group scaling events
- **Maintenance Windows**: Scheduled maintenance notifications

### 3. DynamoDB Audit Trail

#### Transfer Records

- **File Metadata**: Complete file information and tags
- **Processing Timeline**: Timestamps for each processing stage
- **Transfer Status**: Success/failure status with details
- **Error Information**: Detailed error messages for failures
- **Data Governance**: Owner, steward, and POC information

## Troubleshooting

### Common Issues

#### 1. File Processing Delays

**Symptoms**: Files uploaded but not processed quickly
**Causes**:

- EC2 instances not scaling properly
- SQS queue backlog
- Network connectivity issues
- ClamAV signature update delays

**Solutions**:

```bash
# Check Auto Scaling Group
aws autoscaling describe-auto-scaling-groups \
  --auto-scaling-group-names your-asg-name

# Check SQS queue depth
aws sqs get-queue-attributes \
  --queue-url your-queue-url \
  --attribute-names ApproximateNumberOfMessages

# Check EC2 instance logs
aws ssm start-session --target i-1234567890abcdef0
sudo tail -f /var/log/sqs_poller.log
```

#### 2. Cross-Account Access Issues

**Symptoms**: Customer Account uploads fail
**Causes**:

- Incorrect bucket policies
- KMS key access denied
- IAM role trust relationships

**Solutions**:

```bash
# Check bucket policy
aws s3api get-bucket-policy --bucket your-ingestion-bucket

# Verify KMS key policy
aws kms get-key-policy \
  --key-id your-key-id \
  --policy-name default

# Test cross-account access
aws sts assume-role \
  --role-arn arn:aws:iam::customer-account:role/customer-role \
  --role-session-name test-session
```

#### 3. Lambda Function Errors

**Symptoms**: Object tagger or other Lambda functions failing
**Causes**:

- Permission issues
- Environment variable misconfiguration
- Code deployment problems

**Solutions**:

```bash
# Check function configuration
aws lambda get-function-configuration \
  --function-name your-function-name

# View recent errors
aws logs filter-log-events \
  --log-group-name "/aws/lambda/your-function-name" \
  --filter-pattern "ERROR"

# Test function manually
aws lambda invoke \
  --function-name your-function-name \
  --payload file://test-event.json \
  response.json
```

#### 4. Antivirus Scanning Issues

**Symptoms**: Files stuck in processing, scan errors
**Causes**:

- ClamAV daemon not running
- Signature database outdated
- File size limitations
- Memory constraints

**Solutions**:

```bash
# Connect to EC2 instance
aws ssm start-session --target i-1234567890abcdef0

# Check ClamAV status
sudo systemctl status clamd
sudo systemctl status freshclam

# Update virus signatures
sudo freshclam

# Check scan logs
sudo tail -f /var/log/clamav/clamd.log
```

### Debugging Commands

#### System Health Checks

```bash
# Overall stack health
aws cloudformation describe-stacks \
  --stack-name validation-account-main-stack \
  --query 'Stacks[0].StackStatus'

# Check all nested stacks
aws cloudformation list-stacks \
  --stack-status-filter CREATE_COMPLETE UPDATE_COMPLETE \
  --query 'StackSummaries[?contains(StackName, `validation`)].{Name:StackName,Status:StackStatus}'

# Verify critical resources
aws s3 ls | grep -E "(ingestion|transfer|quarantine)"
aws lambda list-functions --query 'Functions[?contains(FunctionName, `tagger`)].FunctionName'
aws sqs list-queues --query 'QueueUrls[?contains(@, `av-scan`)]'
```

#### Performance Monitoring

```bash
# Queue metrics
aws cloudwatch get-metric-statistics \
  --namespace AWS/SQS \
  --metric-name ApproximateNumberOfMessages \
  --dimensions Name=QueueName,Value=your-queue-name \
  --start-time $(date -d '1 hour ago' --iso-8601) \
  --end-time $(date --iso-8601) \
  --period 300 \
  --statistics Average,Maximum

# Lambda performance
aws cloudwatch get-metric-statistics \
  --namespace AWS/Lambda \
  --metric-name Duration \
  --dimensions Name=FunctionName,Value=your-function-name \
  --start-time $(date -d '1 hour ago' --iso-8601) \
  --end-time $(date --iso-8601) \
  --period 300 \
  --statistics Average,Maximum

# EC2 Auto Scaling metrics
aws cloudwatch get-metric-statistics \
  --namespace AWS/AutoScaling \
  --metric-name GroupDesiredCapacity \
  --dimensions Name=AutoScalingGroupName,Value=your-asg-name \
  --start-time $(date -d '1 hour ago' --iso-8601) \
  --end-time $(date --iso-8601) \
  --period 300 \
  --statistics Average
```

## Performance Optimization

### 1. EC2 Auto Scaling Configuration

- **Scaling Policies**: Configure based on SQS queue depth
- **Instance Types**: Choose appropriate instance types for workload
- **Warm Pool**: Pre-warmed instances for faster scaling
- **Health Checks**: Proper health check configuration

### 2. Lambda Optimization

- **Memory Allocation**: Right-size memory for performance vs. cost
- **Timeout Settings**: Appropriate timeouts for each function
- **Concurrent Executions**: Reserved concurrency for critical functions
- **Dead Letter Queues**: Proper error handling and retry logic

### 3. Storage Optimization

- **Lifecycle Policies**: Automatic transition to cheaper storage classes
- **Intelligent Tiering**: Automatic optimization based on access patterns
- **Compression**: Enable compression for log files
- **Cleanup Automation**: Automated deletion of processed files

## Integration Testing

### 1. End-to-End Testing

```bash
# Create test file
echo "This is a test file for the diode pipeline" > test-file.txt

# Upload to ingestion bucket
aws s3 cp test-file.txt s3://your-ingestion-bucket-name/test-file.txt

# Monitor processing
aws logs tail /aws/lambda/object-tagger-function-suffix --follow

# Check processing results
aws s3 ls s3://your-data-transfer-bucket-name/
aws s3 ls s3://your-quarantine-bucket-name/
aws s3 ls s3://your-invalid-files-bucket-name/
```

### 2. Load Testing

```bash
# Upload multiple test files
for i in {1..10}; do
  echo "Test file $i content" > test-file-$i.txt
  aws s3 cp test-file-$i.txt s3://your-ingestion-bucket-name/
done

# Monitor queue depth
aws sqs get-queue-attributes \
  --queue-url your-av-scan-queue-url \
  --attribute-names ApproximateNumberOfMessages

# Monitor Auto Scaling
aws autoscaling describe-auto-scaling-groups \
  --auto-scaling-group-names your-asg-name \
  --query 'AutoScalingGroups[0].{Desired:DesiredCapacity,Running:Instances[?LifecycleState==`InService`]|length(@)}'
```

### 3. Security Testing

```bash
# Test malware detection (use EICAR test file)
echo 'X5O!P%@AP[4\PZX54(P^)7CC)7}$EICAR-STANDARD-ANTIVIRUS-TEST-FILE!$H+H*' > eicar.txt
aws s3 cp eicar.txt s3://your-ingestion-bucket-name/

# Verify quarantine
aws s3 ls s3://your-quarantine-bucket-name/

# Check SNS notifications
aws sns list-subscriptions-by-topic \
  --topic-arn your-quarantine-topic-arn
```

## Cleanup

### Console Method

1. Delete ingestion bucket stacks first
2. Delete main stack (will delete all nested stacks)
3. Manually delete any remaining S3 objects if needed

### CLI Method

```bash
# Delete ingestion bucket stacks
aws cloudformation delete-stack \
  --stack-name validation-ingestion-bucket-customer1

# Wait for deletion
aws cloudformation wait stack-delete-complete \
  --stack-name validation-ingestion-bucket-customer1

# Delete main stack
aws cloudformation delete-stack \
  --stack-name validation-account-main-stack

# Monitor deletion
aws cloudformation describe-stack-events \
  --stack-name validation-account-main-stack
```

**Important**: Empty all S3 buckets before stack deletion:

```bash
# List all buckets created by the stack
aws s3 ls | grep -E "(ingestion|transfer|quarantine|invalid|dfdl|access-logs)"

# Empty each bucket
aws s3 rm s3://bucket-name --recursive

# Then proceed with stack deletion
```

## Support and Maintenance

### Regular Maintenance Tasks

1. **Monitor Queue Depths**: Check for processing backlogs
2. **Review CloudWatch Alarms**: Address any triggered alarms
3. **Update AMIs**: Keep EC2 instances updated with latest security patches
4. **Review Access Logs**: Audit S3 access patterns
5. **Update ClamAV Signatures**: Ensure antivirus definitions are current
6. **Review DynamoDB Records**: Audit transfer success rates

### Scaling Considerations

- **Auto Scaling Policies**: Adjust based on actual usage patterns
- **Lambda Concurrency**: Monitor and adjust reserved concurrency
- **Storage Classes**: Optimize based on access patterns
- **Network Bandwidth**: Monitor and optimize data transfer costs

### Security Reviews

- **IAM Permissions**: Quarterly review of all roles and policies
- **KMS Key Rotation**: Ensure automatic rotation is functioning
- **Network Security**: Review security group and NACL rules
- **Compliance Auditing**: Regular compliance checks and documentation

For additional support, refer to the main cross-account README or contact the infrastructure team.
