# File Validation and Virus Scanning

## Overview

EC2 instances process files uploaded to S3 buckets, validate their content types, perform antivirus scanning, and route them to appropriate destinations based on scan results.

## Architecture Components

### Core Processing Files

- **`sqs_poller.py`** - Main service daemon that polls SQS for file processing messages
- **`validation.py`** - File type and content validation logic including ZIP file inspection
- **`clamscan.py`** - ClamAV antivirus scanning integration and result processing
- **`utils.py`** - Shared utility functions for AWS service interactions and file operations
- **`config.py`** - Configuration management and SSM parameter definitions

### System Configuration

- **`sqs_poller.service`** - Systemd service definition for the SQS poller daemon
- **`amazon-cloudwatch-agent.json`** - CloudWatch agent configuration for metrics and log collection

## Processing Workflow

### 1. Message Reception

- SQS poller continuously monitors the AV scan queue for new file notifications
- Handles message visibility timeouts and retry logic for failed processing
- Refreshes SSM parameters periodically for dynamic configuration updates

### 2. File Validation (`validation.py`)

- **Content Type Validation**: Uses `puremagic` library to detect actual file types vs. extensions
- **Approved File Types**: Validates against configurable allow-lists stored in SSM parameters
- **MIME Type Validation**: Ensures MIME types match expected values for file types
- **ZIP File Inspection**: Recursively validates contents of ZIP archives (configurable depth limit)
- **Special Handling**: Supports exempt file types and DFDL-bound files

### 3. Antivirus Scanning (`clamscan.py`)

- **ClamAV Integration**: Uses `clamdscan` with file descriptor passing for performance
- **Result Processing**: Handles three scan outcomes:
  - `0` - Clean files → Route to data transfer or destination buckets
  - `1` - Infected files → Quarantine bucket
  - `2+` - Scan errors → Invalid files bucket
- **Notification System**: Sends SNS alerts for quarantined or rejected files

### 4. File Routing

Based on validation and scan results, files are routed to:

- **Data Transfer Bucket** - Clean, validated files for cross-domain transfer
- **Destination Bucket** - Files with specific routing tags
- **DFDL Input Bucket** - Files marked for DFDL processing
- **Quarantine Bucket** - Virus-infected files
- **Invalid Files Bucket** - Files failing validation or scan errors

## Key Features

### Security Controls

- **File Type Enforcement**: Strict validation of file types against allow-lists
- **Antivirus Scanning**: Real-time malware detection using ClamAV
- **Content Inspection**: Deep analysis of archive files
- **Audit Logging**: Comprehensive tagging and CloudWatch logging

### Operational Features

- **Retry Logic**: Automatic retry with exponential backoff for transient failures
- **Health Monitoring**: Instance health checks and auto-scaling integration
- **Dynamic Configuration**: SSM parameter-based configuration updates
- **Error Handling**: Graceful handling of missing files, network issues, and service failures

### Performance Optimizations

- **Caching**: LRU caching for frequently accessed configuration data
- **Batch Processing**: Efficient SSM parameter retrieval in batches
- **Resource Management**: Temporary file cleanup and memory management

## Configuration Parameters

### SSM Parameters (per resource suffix)

- `/pipeline/DataTransferIngestBucketName-{suffix}` - Clean files destination
- `/pipeline/QuarantineBucketName-{suffix}` - Infected files destination
- `/pipeline/InvalidFilesBucketName-{suffix}` - Invalid files destination
- `/pipeline/DfdlInputBucketName-{suffix}` - DFDL processing destination
- `/pipeline/AvScanQueueUrl-{suffix}` - SQS queue for file notifications
- `/pipeline/DfdlApprovedFileTypes-{suffix}` - DFDL-specific file types
- `/pipeline/ExemptFileTypes-{suffix}` - Files exempt from validation
- `/{bucket}/ApprovedFileTypes-{suffix}` - Per-bucket approved file types
- `/{bucket}/MimeMapping-{suffix}` - Per-bucket MIME type mappings

### Environment Variables

- `region` - AWS region for service clients
- `resource_suffix` - Deployment-specific resource suffix

## Monitoring and Logging

### CloudWatch Integration

- **Metrics**: CPU, memory, disk usage, and custom application metrics
- **Logs**: Structured logging with rotation (7-day retention)
- **Alarms**: Instance health and processing failure notifications

### Audit Trail

- **File Tags**: Comprehensive tagging with validation results, scan status, and metadata
- **SNS Notifications**: Real-time alerts for security events
- **Processing History**: Complete audit trail of file processing decisions

## Error Handling and Recovery

### Failure Scenarios

- **Missing Files**: Graceful handling of deleted or moved objects
- **Service Unavailability**: Retry logic with exponential backoff
- **Disk Space**: Automatic instance health marking for storage issues
- **ClamAV Failures**: Service restart and health monitoring

### Recovery Mechanisms

- **Message Reprocessing**: SQS visibility timeout management for retries
- **Instance Replacement**: Auto Scaling Group health checks and replacement
- **Configuration Refresh**: Periodic SSM parameter updates
- **Service Restart**: Systemd automatic restart on failures
