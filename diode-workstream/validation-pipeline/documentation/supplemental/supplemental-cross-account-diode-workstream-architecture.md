# Cross-Account Diode Workstream Architecture

This directory contains the complete infrastructure and application code for a secure, cross-account data transfer pipeline using AWS Diode technology. The architecture spans three AWS accounts, each with specific roles and responsibilities in the data validation and transfer process.

## Architecture Overview

The system implements a secure data transfer pipeline across three AWS accounts:

1. **Customer Account** - Data ingestion and initial processing
2. **Validation Account** - Security scanning, validation, and transfer orchestration
3. **Diode Account** - Cross-domain data transfer via AWS Diode

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│ Customer Account│    │Validation Account│   │  Diode Account  │
│                 │    │                 │    │                 │
│ Source Bucket   │───▶│ Ingestion       │───▶│ Data Transfer   │
│ Lambda Function │    │ AV Scanning     │    │ Lambda Function │
│                 │    │ File Validation │    │ Diode Service   │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

## Customer Account

### Purpose

The Customer Account serves as the entry point for data into the pipeline. It provides a secure S3 bucket where customers can upload files that need to be transferred across security domains.

### Components

#### Infrastructure (`customer-source-bucket-template.yaml`)

- **Source S3 Bucket**: KMS-encrypted bucket for customer file uploads
- **Lambda Function**: Automatically copies uploaded files to the Validation Account
- **IAM Roles**: Cross-account permissions for secure file transfer
- **KMS Key**: Customer-managed encryption key for data at rest
- **Lifecycle Policies**: Automatic cleanup of old files

#### Key Features

- **Automatic File Transfer**: Files uploaded to the source bucket trigger a Lambda function that copies them to the Validation Account's ingestion bucket
- **Security**: All data encrypted at rest and in transit using KMS
- **Configurable Cleanup**: Optional deletion of source files after successful copy
- **Cross-Account Access**: Secure IAM roles enable access to destination bucket in Validation Account

#### Configuration Parameters

- `SourceBucketName`: Name of the customer's source bucket
- `DestinationBucketName`: Target bucket in Validation Account
- `DestinationBucketKeyArn`: KMS key for destination bucket encryption
- `DeleteSourceObjects`: Whether to delete files after successful copy
- `ObjectExpirationInDays`: Lifecycle policy for automatic cleanup

## Validation Account

### Purpose

The Validation Account is the core of the security and validation pipeline. It performs comprehensive security scanning, file type validation, and orchestrates the transfer process to the Diode Account.

### Architecture Components

#### Core Infrastructure Stacks

##### Main Stack (`aftac_main_stack.yaml`)

Master template that orchestrates all other stacks:

- **Logging Stack**: Centralized logging infrastructure
- **Ingest Stack**: File ingestion and initial processing
- **Pipeline Stack**: Core validation and transfer pipeline
- **SFTP Stack**: Secure file transfer protocol server (low-side only)

##### Ingestion Bucket (`aftac_ingestion_bucket.yaml`)

Secure S3 bucket for receiving files from Customer Account:

- **KMS Encryption**: Customer-managed key with strict access policies
- **Bucket Tags**: Metadata for routing and processing decisions
  - `MappingId`: Unique identifier for transfer routing
  - `DestinationBucket`: Direct bucket destination (alternative to MappingId)
  - `DestinationMappingKey`: Key for destination mapping lookup
  - `DfdlBound`: Flag indicating if files should go through DFDL pipeline
  - `DataOwner`, `DataSteward`, `GovPOC`, `KeyOwner`: Data governance tags
- **Lifecycle Policies**: Automatic cleanup and archival
- **Event Notifications**: Triggers Lambda functions on file upload

##### Pipeline Stack (`aftac_pipeline_stack.yaml`)

Core processing pipeline with multiple components:

- **SQS Queues**: Message queuing for asynchronous processing
- **Lambda Functions**: Serverless processing functions
- **EC2 Auto Scaling**: Scalable virus scanning infrastructure
- **DynamoDB**: Transfer status tracking
- **SNS Topics**: Notifications for various events

#### Processing Components

##### EC2 File Processing (`ec2-files/`)

Scalable EC2 instances that perform intensive file processing:

**Main Components:**

- `sqs_poller.py`: Main service daemon that polls SQS for file processing messages
- `validation.py`: File type and content validation logic including ZIP file inspection
- `clamscan.py`: ClamAV antivirus scanning integration and result processing
- `utils.py`: Shared utility functions for AWS service interactions and file operations
- `config.py`: Configuration management and SSM parameter definitions
- `sqs_poller.service`: Systemd service definition for the SQS poller daemon
- `amazon-cloudwatch-agent.json`: CloudWatch agent configuration for metrics and log collection

**Processing Flow:**

1. **File Validation**: Checks file types against approved lists
2. **ZIP File Handling**: Recursive validation of compressed archives
3. **Antivirus Scanning**: ClamAV scanning for malware detection
4. **Routing Logic**: Determines destination based on scan results and bucket tags

**Destination Routing:**

- **Clean Files**: Routed to Data Transfer bucket or DFDL pipeline based on tags
- **Infected Files**: Quarantined in dedicated bucket
- **Invalid Files**: Stored in invalid files bucket with detailed error tags

##### Lambda Functions (`lambda/`)

**Object Tagger (`object_tagger.py`)**

- Triggered by S3 events on ingestion bucket
- Sends file metadata to SQS queue for processing
- Lightweight function for event routing

**Presigner (`presigner.py`)**

- Generates pre-signed URLs for secure file uploads
- Enforces KMS encryption requirements
- Used by API Gateway for programmatic uploads

**Transfer Result (`transfer_result.py`)**

- Processes transfer completion notifications from Diode Account
- Updates DynamoDB with transfer status
- Handles failed transfers and notifications
- Manages cleanup of successfully transferred files

**Destination Parser (`dest-parser/`)**

- Parses destination mapping keys from file tags
- Retrieves destination bucket mappings from SSM parameters
- Copies files to multiple destination buckets based on mapping

#### Security Features

##### Multi-Layer Validation

1. **File Type Validation**: Whitelist-based file type checking
2. **MIME Type Verification**: Content-based file type validation
3. **Antivirus Scanning**: Real-time malware detection
4. **ZIP File Inspection**: Recursive scanning of compressed files

##### Access Control

- **IAM Roles**: Least-privilege access patterns
- **KMS Encryption**: Customer-managed keys for all data
- **VPC Isolation**: Network-level security controls
- **Cross-Account Policies**: Secure inter-account communication

##### Monitoring and Alerting

- **CloudWatch Metrics**: Comprehensive monitoring of all components
- **SNS Notifications**: Real-time alerts for security events
- **DynamoDB Logging**: Audit trail of all transfer activities
- **Queue Monitoring**: Automated alerting on queue depth thresholds

#### Configuration Management

##### SSM Parameters

Centralized configuration through Systems Manager:

- Bucket names and ARNs
- Queue URLs and ARNs
- File type configurations
- Notification topic ARNs

##### Tagging Strategy

Comprehensive tagging for governance and routing:

- **Data Governance**: Owner, steward, and POC information
- **Processing Flags**: DFDL binding, destination routing
- **Security Metadata**: Scan results, validation status
- **Audit Information**: Creation time, source IP, principal ID

## Diode Account

### Purpose

The Diode Account handles the actual cross-domain data transfer using AWS Diode service. It processes transfer requests from the Validation Account and manages the secure movement of data across security boundaries.

### Components

#### Infrastructure (`diode_account_stack.yaml`)

- **Data Transfer Lambda**: Orchestrates Diode transfer operations
- **SQS Queues**: Message handling for transfer requests and status updates
- **EventBridge Rules**: Captures Diode service events
- **IAM Roles**: Permissions for Diode service interaction

#### Lambda Function (`lambda/data_transfer.py`)

Comprehensive transfer orchestration:

**Core Functions:**

- **Transfer Creation**: Initiates Diode transfers with proper metadata
- **Status Monitoring**: Tracks transfer progress through EventBridge
- **Error Handling**: Robust retry logic and error reporting
- **Result Notification**: Sends completion status back to Validation Account

**Key Features:**

- **Mapping ID Extraction**: Retrieves routing information from S3 object tags
- **Diode Integration**: Native AWS Diode service integration
- **Simulator Support**: Optional Diode simulator for testing
- **Retry Logic**: Intelligent retry for transient failures

#### Diode Simulator (`diode-simulator/`)

Testing infrastructure for development and validation:

- **Python Application**: Simulates Diode service behavior
- **Lambda Package**: Deployable simulator function
- **SWAMS Integration**: Specialized simulator for SWAMS workflows

#### Event Processing

- **S3 Events**: Triggered by file uploads to transfer bucket
- **Diode Events**: Processes transfer status changes
- **SQS Integration**: Reliable message processing with dead letter queues

## Data Flow

### Complete Processing Pipeline

1. **Customer Upload**

   - File uploaded to Customer Account source bucket
   - Lambda function copies file to Validation Account ingestion bucket

2. **Initial Processing**

   - S3 event triggers object tagger Lambda
   - File metadata sent to AV scan queue

3. **Security Validation**

   - EC2 instances poll SQS queue
   - File type validation performed
   - Antivirus scanning with ClamAV

4. **Routing Decision**

   - Based on scan results and bucket tags:
     - Clean files → Data Transfer bucket or DFDL pipeline
     - Infected files → Quarantine bucket
     - Invalid files → Invalid files bucket

5. **Transfer Initiation**

   - Clean files trigger transfer queue message
   - Diode Account Lambda processes transfer request
   - Diode service initiates cross-domain transfer

6. **Transfer Completion**
   - Diode events captured by EventBridge
   - Status updates sent back to Validation Account
   - DynamoDB updated with transfer results
   - Cleanup and notifications performed

### Error Handling and Recovery

#### Retry Mechanisms

- **SQS Visibility Timeout**: Automatic retry for failed processing
- **Dead Letter Queues**: Capture permanently failed messages
- **Lambda Retry Logic**: Built-in retry for transient failures

#### Monitoring and Alerting

- **Queue Depth Monitoring**: Automated alerts for processing backlogs
- **Transfer Failure Notifications**: SNS alerts for failed transfers
- **Health Check Dashboards**: Real-time system status monitoring

## Security Considerations

### Encryption

- **Data at Rest**: KMS encryption for all S3 buckets
- **Data in Transit**: TLS encryption for all communications
- **Key Management**: Customer-managed KMS keys with strict policies

### Access Control

- **Cross-Account Roles**: Minimal permissions for inter-account access
- **Service-Linked Roles**: AWS service integration with least privilege
- **Resource-Based Policies**: Fine-grained access control on resources

### Network Security

- **VPC Isolation**: Private subnets for processing infrastructure
- **Security Groups**: Restrictive network access rules
- **Prefix Lists**: Managed access to AWS services

### Compliance

- **Audit Logging**: Comprehensive logging of all activities
- **Data Governance**: Metadata tracking for compliance requirements
- **Retention Policies**: Automated data lifecycle management

## Deployment and Configuration

### Prerequisites

- Three AWS accounts with appropriate permissions
- VPC and networking infrastructure in Validation Account
- KMS keys for encryption
- SNS topics for notifications

### Deployment Order

1. **Validation Account**: Deploy main stack with all dependencies
2. **Customer Account**: Deploy source bucket template with destination parameters
3. **Diode Account**: Deploy diode account stack with validation account parameters

### Configuration Parameters

Each account requires specific configuration parameters for cross-account integration, networking, and security settings. Refer to individual CloudFormation templates for detailed parameter descriptions.

### Monitoring Setup

- Configure CloudWatch dashboards for system monitoring
- Set up SNS subscriptions for critical alerts
- Establish log aggregation for centralized monitoring

## Troubleshooting

### Common Issues

- **Permission Errors**: Verify cross-account IAM roles and policies
- **Transfer Failures**: Check Diode service quotas and network connectivity
- **Processing Delays**: Monitor SQS queue depths and EC2 scaling

### Debugging Tools

- **CloudWatch Logs**: Detailed logging from all components
- **DynamoDB Tables**: Transfer status and audit information
- **SQS Dead Letter Queues**: Failed message analysis

This architecture provides a robust, secure, and scalable solution for cross-domain data transfer with comprehensive validation and monitoring capabilities.
