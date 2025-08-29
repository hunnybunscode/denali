# Diode Account - Cross-Domain Data Transfer Infrastructure

This directory contains the CloudFormation template and Lambda code for deploying the Diode Account infrastructure of the cross-account diode workstream. The Diode Account handles the actual cross-domain data transfer using AWS Diode service, processing transfer requests from the Validation Account and managing secure movement of data across security boundaries.

## Overview

The Diode Account serves as the final stage in the secure data transfer pipeline, responsible for:

- Receiving transfer requests from the Validation Account
- Orchestrating AWS Diode service operations
- Monitoring transfer status and handling failures
- Providing transfer completion notifications back to the Validation Account

## Components Deployed

### 1. Data Transfer Lambda Function

- **Runtime**: Python 3.11
- **Purpose**: Orchestrates Diode transfer operations and status monitoring
- **Timeout**: 30 seconds
- **Memory**: Default (128 MB)
- **Event Sources**:
  - Data Transfer SQS Queue (from Validation Account)
  - Transfer Status SQS Queue (internal)

**Key Capabilities**:

- Creates Diode transfers with mapping ID and metadata
- Extracts routing information from S3 object tags
- Handles both real Diode service and simulator
- Implements intelligent retry logic for transient failures
- Processes transfer status events from EventBridge

### 2. SQS Queues

#### Data Transfer Queue (External)

- **Source**: Validation Account pipeline
- **Purpose**: Receives transfer requests for files ready to transfer
- **Message Format**: S3 event notifications with file metadata
- **Batch Size**: 1 message per Lambda invocation
- **Visibility Timeout**: Managed by Lambda retry logic

#### Transfer Status Queue (Internal)

- **Source**: EventBridge rules capturing Diode events
- **Purpose**: Processes transfer completion/failure notifications
- **Message Retention**: 4 days (default)
- **Dead Letter Queue**: Configured with 5 retry attempts

#### Transfer Status Dead Letter Queue

- **Purpose**: Captures permanently failed status messages
- **Retention**: 14 days
- **Encryption**: AWS managed KMS (alias/aws/sqs)

### 3. EventBridge Rule

- **Purpose**: Captures AWS Diode service events
- **Event Pattern**: Filters for transfer status changes (SUCCEEDED, FAILED, REJECTED)
- **Target**: Transfer Status SQS Queue
- **State**: Enabled by default

**Monitored Events**:

- Transfer completion (SUCCEEDED)
- Transfer failures (FAILED, REJECTED)
- Specific to the configured data transfer bucket

### 4. IAM Role (DataTransferLambdaRole)

- **Purpose**: Provides Lambda function with necessary permissions
- **Permissions Boundary**: Applied as specified in parameters
- **Key Permissions**:
  - S3 read access to data transfer bucket
  - Diode service operations (CreateTransfer, DescribeTransfer)
  - SQS send/receive/delete operations
  - KMS decrypt/encrypt operations
  - CloudWatch Logs access

### 5. CloudWatch Log Group

- **Purpose**: Stores Lambda function execution logs
- **Retention**: 90 days
- **Log Group Name**: `/aws/lambda/data-transfer-function-{ResourceSuffix}`

### 6. Diode Simulator (Optional)

- **Purpose**: Testing and development environment
- **Components**:
  - Python application package
  - Lambda deployment package
  - SWAMS-specific simulator variant
- **Usage**: Controlled by `UseDiodeSimulator` parameter

## Prerequisites

Before deploying this template, ensure you have:

1. **Validation Account Deployment**: The Validation Account infrastructure must be deployed first
2. **Cross-Account Permissions**: Validation Account must grant permissions to this Diode Account
3. **Lambda Code Package**: The `data_transfer.zip` file must be uploaded to an S3 bucket
4. **AWS Diode Service Access**: Ensure the account has access to AWS Diode service

### Required Information from Validation Account

Obtain these values from the Validation Account CloudFormation stack outputs:

- Data Transfer Bucket Name
- Data Transfer SQS Queue ARN
- Transfer Result SQS Queue ARN
- Pipeline KMS Key ARN

## Deployment Steps

### AWS Console Deployment

#### Step 1: Prepare Lambda Code

1. Ensure `data_transfer.zip` is uploaded to an S3 bucket accessible by this account
2. Note the bucket name, key, and object version

#### Step 2: Access CloudFormation Console

1. Log into the AWS Management Console for your Diode Account
2. Navigate to **CloudFormation** service
3. Select the appropriate region for deployment

#### Step 3: Create Stack

1. Click **Create stack** → **With new resources (standard)**
2. Under **Template source**, select **Upload a template file**
3. Click **Choose file** and select `diode_account_stack.yaml`
4. Click **Next**

#### Step 4: Configure Stack Parameters

1. **Stack name**: Enter descriptive name (e.g., `diode-account-stack`)
2. **General Parameters**:
   - **IAM Prefix**: `AFC2S`
   - **Permissions Boundary Policy ARN**: Enter your organization's boundary policy
   - **Resource Suffix**: Enter unique suffix (e.g., `prod-east-1`)
3. **Resources from Validation Account**:
   - **Data Transfer Bucket Name**: From Validation Account outputs
   - **Data Transfer SQS Queue ARN**: From Validation Account outputs
   - **Transfer Result SQS Queue ARN**: From Validation Account outputs
   - **Pipeline KMS Key ARN**: From Validation Account outputs
4. **Data Transfer Lambda Code**:
   - **Lambda Storage Bucket**: S3 bucket containing your Lambda code
   - **Lambda Code Key**: `data_transfer.zip`
   - **Lambda Code Key Version**: Object version from S3
5. **Diode Simulator** (Optional):
   - **Use Diode Simulator**: `False` for production, `True` for testing
   - **Diode Simulator Endpoint**: Leave blank unless using simulator
6. Click **Next**

#### Step 5: Configure Stack Options

1. **Tags** (Recommended):
   - Key: `Environment`, Value: `Production`
   - Key: `Project`, Value: `DiodeWorkstream`
   - Key: `Account`, Value: `Diode`
2. **Permissions**: Leave default
3. **Advanced options**: Leave defaults
4. Click **Next**

#### Step 6: Review and Deploy

1. Review all parameters carefully
2. **Capabilities**: Check **I acknowledge that AWS CloudFormation might create IAM resources with custom names**
3. Click **Create stack**

#### Step 7: Monitor Deployment

1. Watch the **Events** tab for progress
2. Deployment typically takes 5-10 minutes
3. Status will show **CREATE_COMPLETE** when finished

## Lambda Function Details

### Core Functionality

The `data_transfer.py` Lambda function handles two types of events:

#### 1. Transfer Creation (from Validation Account)

- **Trigger**: SQS messages from Validation Account transfer queue
- **Process**:
  - Extracts S3 bucket and key from message
  - Retrieves MappingId from S3 object tags
  - Creates Diode transfer request
  - Handles retry logic for transient failures
  - Sends results to Validation Account result queue

#### 2. Transfer Status Updates (from EventBridge)

- **Trigger**: EventBridge events from AWS Diode service
- **Process**:
  - Processes transfer completion/failure events
  - Updates transfer status
  - Sends final results to Validation Account
  - Handles error details for failed transfers

### Environment Variables

The Lambda function uses these environment variables:

| Variable                    | Description                           | Source                     |
| --------------------------- | ------------------------------------- | -------------------------- |
| `TRANSFER_BUCKET_OWNER`     | Account ID owning the transfer bucket | Derived from queue ARN     |
| `TRANSFER_RESULT_QUEUE_URL` | URL for sending results back          | Constructed from ARN       |
| `DATA_TRANSFER_QUEUE_URL`   | URL for receiving transfer requests   | Constructed from ARN       |
| `TRANSFER_STATUS_QUEUE_URL` | Internal status queue URL             | Reference to created queue |
| `USE_DIODE_SIMULATOR`       | Whether to use simulator              | Parameter value            |
| `DIODE_SIMULATOR_ENDPOINT`  | Simulator endpoint URL                | Parameter value            |

### Error Handling

The function implements comprehensive error handling:

#### Retryable Errors

- Network timeouts and connection errors
- Service throttling and rate limiting
- Transient AWS service errors
- Resource limit exceptions

#### Non-Retryable Errors

- Invalid mapping ID or missing tags
- Permanent authorization failures
- Malformed requests

#### Retry Logic

- Uses SQS visibility timeout for automatic retry
- Exponential backoff based on receive count
- Maximum of 5 retry attempts
- Dead letter queue for permanent failures
