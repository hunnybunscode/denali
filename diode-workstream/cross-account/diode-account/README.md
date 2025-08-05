# Diode Account - Cross-Domain Data Transfer Infrastructure

This directory contains the CloudFormation template and Lambda code for deploying the Diode Account infrastructure of the cross-account diode workstream. The Diode Account handles the actual cross-domain data transfer using AWS Diode service, processing transfer requests from the Validation Account and managing secure movement of data across security boundaries.

## Overview

The Diode Account serves as the final stage in the secure data transfer pipeline, responsible for:
- Receiving transfer requests from the Validation Account
- Orchestrating AWS Diode service operations
- Monitoring transfer status and handling failures
- Providing transfer completion notifications back to the Validation Account

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Diode Account                            │
│                                                             │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐     │
│  │ Data Transfer│    │   Transfer  │    │ EventBridge │     │
│  │    SQS      │───▶│   Lambda    │───▶│    Rules    │     │
│  │   Queue     │    │  Function   │    │             │     │
│  └─────────────┘    └─────────────┘    └─────────────┘     │
│         ▲                   │                   │          │
│         │                   ▼                   ▼          │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐     │
│  │ Validation  │    │ AWS Diode   │    │ Transfer    │     │
│  │  Account    │    │  Service    │    │ Status SQS  │     │
│  │  Messages   │    │             │    │   Queue     │     │
│  └─────────────┘    └─────────────┘    └─────────────┘     │
│                             │                   │          │
│                             ▼                   ▼          │
│                    ┌─────────────┐    ┌─────────────┐     │
│                    │Cross-Domain │    │ Result SQS  │     │
│                    │ Destination │    │   Queue     │     │
│                    └─────────────┘    └─────────────┘     │
└─────────────────────────────────────────────────────────────┘
                             │
                             ▼
                    ┌─────────────────┐
                    │ Validation Acct │
                    │ Result Queue    │
                    └─────────────────┘
```

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

## Configuration Parameters

### Required Parameters

| Parameter | Description | Example |
|-----------|-------------|---------|
| `IamPrefix` | Required prefix for IAM resources | `AFC2S` |
| `PermissionsBoundaryPolicyArn` | ARN of permissions boundary policy | `arn:aws:iam::123456789012:policy/MyBoundary` |
| `ResourceSuffix` | Suffix for AWS resource names | `prod-east-1` |
| `DataTransferBucketName` | Name of S3 bucket in Validation Account | `validation-data-transfer-abc123` |
| `DataTransferSqsQueueArn` | ARN of transfer queue from Validation Account | `arn:aws:sqs:us-east-1:123456789012:transfer-queue` |
| `TranferResultSqsQueueArn` | ARN of result queue in Validation Account | `arn:aws:sqs:us-east-1:123456789012:result-queue` |
| `PipelineKmsKeyArn` | ARN of KMS key for pipeline encryption | `arn:aws:kms:us-east-1:123456789012:key/12345678-1234-1234-1234-123456789012` |

### Lambda Code Parameters

| Parameter | Description | Default |
|-----------|-------------|---------|
| `DataTransferLambdaStorageBucket` | S3 bucket containing Lambda code | Required |
| `DataTransferLambdaCodeKey` | S3 key for Lambda deployment package | `data_transfer.zip` |
| `DataTransferLambdaCodeKeyVersion` | Object version of Lambda code | Required |

### Optional Parameters

| Parameter | Description | Default | Options |
|-----------|-------------|---------|---------|
| `UseDiodeSimulator` | Enable Diode simulator for testing | `False` | `True`, `False` |
| `DiodeSimulatorEndpoint` | Simulator endpoint URL | Empty | `http://simulator.example.com` |

## Prerequisites

Before deploying this template, ensure you have:

1. **Validation Account Deployment**: The Validation Account infrastructure must be deployed first
2. **Cross-Account Permissions**: Validation Account must grant permissions to this Diode Account
3. **Lambda Code Package**: The `data_transfer.zip` file must be uploaded to an S3 bucket
4. **AWS Diode Service Access**: Ensure the account has access to AWS Diode service
5. **Network Connectivity**: VPC configuration if Lambda needs VPC access (currently commented out)

### Required Information from Validation Account

Obtain these values from the Validation Account CloudFormation stack outputs:
- Data Transfer Bucket Name
- Data Transfer SQS Queue ARN  
- Transfer Result SQS Queue ARN
- Pipeline KMS Key ARN

## Deployment Steps

### Option 1: AWS Console Deployment

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

### Option 2: AWS CLI Deployment

#### Step 1: Prepare Parameter File
Create `diode-parameters.json`:

```json
[
  {
    "ParameterKey": "IamPrefix",
    "ParameterValue": "AFC2S"
  },
  {
    "ParameterKey": "PermissionsBoundaryPolicyArn",
    "ParameterValue": "arn:aws:iam::123456789012:policy/MyPermissionsBoundary"
  },
  {
    "ParameterKey": "ResourceSuffix", 
    "ParameterValue": "prod-east-1"
  },
  {
    "ParameterKey": "DataTransferBucketName",
    "ParameterValue": "validation-data-transfer-abc123"
  },
  {
    "ParameterKey": "DataTransferSqsQueueArn",
    "ParameterValue": "arn:aws:sqs:us-east-1:123456789012:transfer-queue-abc123"
  },
  {
    "ParameterKey": "TranferResultSqsQueueArn",
    "ParameterValue": "arn:aws:sqs:us-east-1:123456789012:result-queue-abc123"
  },
  {
    "ParameterKey": "PipelineKmsKeyArn",
    "ParameterValue": "arn:aws:kms:us-east-1:123456789012:key/12345678-1234-1234-1234-123456789012"
  },
  {
    "ParameterKey": "DataTransferLambdaStorageBucket",
    "ParameterValue": "my-lambda-code-bucket"
  },
  {
    "ParameterKey": "DataTransferLambdaCodeKey",
    "ParameterValue": "data_transfer.zip"
  },
  {
    "ParameterKey": "DataTransferLambdaCodeKeyVersion",
    "ParameterValue": "v1.0.0"
  },
  {
    "ParameterKey": "UseDiodeSimulator",
    "ParameterValue": "False"
  },
  {
    "ParameterKey": "DiodeSimulatorEndpoint",
    "ParameterValue": ""
  }
]
```

#### Step 2: Deploy Stack
```bash
# Set variables
STACK_NAME="diode-account-stack"
TEMPLATE_FILE="diode_account_stack.yaml"
PARAMETERS_FILE="diode-parameters.json"
REGION="us-east-1"

# Deploy the stack
aws cloudformation create-stack \
  --stack-name $STACK_NAME \
  --template-body file://$TEMPLATE_FILE \
  --parameters file://$PARAMETERS_FILE \
  --capabilities CAPABILITY_NAMED_IAM \
  --region $REGION \
  --tags Key=Environment,Value=Production Key=Project,Value=DiodeWorkstream Key=Account,Value=Diode
```

#### Step 3: Monitor Deployment
```bash
# Check stack status
aws cloudformation describe-stacks \
  --stack-name $STACK_NAME \
  --region $REGION \
  --query 'Stacks[0].StackStatus'

# Watch stack events
aws cloudformation describe-stack-events \
  --stack-name $STACK_NAME \
  --region $REGION \
  --query 'StackEvents[*].[Timestamp,ResourceStatus,ResourceType,LogicalResourceId]' \
  --output table
```

#### Step 4: Verify Deployment
```bash
# Get stack outputs (none defined in this template)
aws cloudformation describe-stacks \
  --stack-name $STACK_NAME \
  --region $REGION \
  --query 'Stacks[0].Outputs'

# Verify Lambda function
aws lambda get-function \
  --function-name data-transfer-function-prod-east-1 \
  --region $REGION
```

## Post-Deployment Configuration

### 1. Verify Lambda Function
```bash
# Check function configuration
aws lambda get-function-configuration \
  --function-name data-transfer-function-your-suffix

# Test function permissions
aws lambda get-policy \
  --function-name data-transfer-function-your-suffix
```

### 2. Verify SQS Queues
```bash
# List queues
aws sqs list-queues --queue-name-prefix transfer

# Check queue attributes
aws sqs get-queue-attributes \
  --queue-url https://sqs.region.amazonaws.com/account/queue-name \
  --attribute-names All
```

### 3. Test EventBridge Rule
```bash
# Describe the rule
aws events describe-rule --name DiodeEventBridgeEventsRule

# List targets
aws events list-targets-by-rule --rule DiodeEventBridgeEventsRule
```

### 4. Monitor Initial Operations
```bash
# Check Lambda logs
aws logs describe-log-groups \
  --log-group-name-prefix "/aws/lambda/data-transfer-function"

# View recent log events
aws logs filter-log-events \
  --log-group-name "/aws/lambda/data-transfer-function-your-suffix" \
  --start-time $(date -d '1 hour ago' +%s)000
```

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

| Variable | Description | Source |
|----------|-------------|--------|
| `TRANSFER_BUCKET_OWNER` | Account ID owning the transfer bucket | Derived from queue ARN |
| `TRANSFER_RESULT_QUEUE_URL` | URL for sending results back | Constructed from ARN |
| `DATA_TRANSFER_QUEUE_URL` | URL for receiving transfer requests | Constructed from ARN |
| `TRANSFER_STATUS_QUEUE_URL` | Internal status queue URL | Reference to created queue |
| `USE_DIODE_SIMULATOR` | Whether to use simulator | Parameter value |
| `DIODE_SIMULATOR_ENDPOINT` | Simulator endpoint URL | Parameter value |

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

## Security Considerations

### 1. IAM Permissions
- **Least Privilege**: Lambda role has minimal required permissions
- **Cross-Account Access**: Secure access to Validation Account resources
- **Permissions Boundary**: Applied to all IAM resources
- **Service-Linked Roles**: Uses AWS service principals where possible

### 2. Encryption
- **Data in Transit**: All communications use TLS encryption
- **SQS Messages**: Encrypted using pipeline KMS key
- **Lambda Environment**: Environment variables encrypted at rest
- **CloudWatch Logs**: Log data encrypted

### 3. Network Security
- **VPC Configuration**: Currently disabled but can be enabled
- **Security Groups**: Would restrict network access if VPC enabled
- **Private Subnets**: Lambda can be deployed in private subnets

### 4. Monitoring and Auditing
- **CloudWatch Logs**: All function executions logged
- **CloudTrail**: API calls audited
- **EventBridge**: Transfer events captured and processed
- **Dead Letter Queues**: Failed messages preserved for analysis

## Troubleshooting

### Common Issues

#### 1. Lambda Function Fails to Start
**Symptoms**: Function errors immediately on invocation
**Causes**:
- Missing or incorrect IAM permissions
- Invalid environment variables
- Lambda code package issues

**Solutions**:
```bash
# Check function configuration
aws lambda get-function-configuration --function-name your-function-name

# Verify IAM role permissions
aws iam get-role-policy --role-name your-role-name --policy-name your-policy-name

# Check environment variables
aws lambda get-function-configuration \
  --function-name your-function-name \
  --query 'Environment'
```

#### 2. Cross-Account Access Denied
**Symptoms**: S3 or SQS access denied errors
**Causes**:
- Incorrect ARNs in parameters
- Missing cross-account permissions in Validation Account
- KMS key access issues

**Solutions**:
```bash
# Test S3 access
aws s3 ls s3://validation-bucket-name --profile diode-account

# Test SQS access
aws sqs get-queue-attributes \
  --queue-url validation-queue-url \
  --attribute-names QueueArn
```

#### 3. Diode Service Errors
**Symptoms**: CreateTransfer or DescribeTransfer failures
**Causes**:
- Invalid mapping IDs
- Diode service quotas exceeded
- Network connectivity issues

**Solutions**:
```bash
# Check Diode service quotas
aws service-quotas list-service-quotas --service-code diode

# Verify mapping ID format
aws s3api get-object-tagging \
  --bucket your-bucket \
  --key your-key
```

#### 4. EventBridge Events Not Processing
**Symptoms**: Transfer status updates not received
**Causes**:
- EventBridge rule misconfiguration
- SQS queue permissions
- Event pattern matching issues

**Solutions**:
```bash
# Check EventBridge rule
aws events describe-rule --name DiodeEventBridgeEventsRule

# Test event pattern
aws events test-event-pattern \
  --event-pattern file://event-pattern.json \
  --event file://test-event.json
```

### Debugging Commands

```bash
# View Lambda function logs
aws logs filter-log-events \
  --log-group-name "/aws/lambda/data-transfer-function-suffix" \
  --start-time $(date -d '1 hour ago' +%s)000

# Check SQS queue metrics
aws cloudwatch get-metric-statistics \
  --namespace AWS/SQS \
  --metric-name ApproximateNumberOfMessages \
  --dimensions Name=QueueName,Value=your-queue-name \
  --start-time $(date -d '1 hour ago' --iso-8601) \
  --end-time $(date --iso-8601) \
  --period 300 \
  --statistics Average

# Monitor EventBridge rule metrics
aws cloudwatch get-metric-statistics \
  --namespace AWS/Events \
  --metric-name MatchedEvents \
  --dimensions Name=RuleName,Value=DiodeEventBridgeEventsRule \
  --start-time $(date -d '1 hour ago' --iso-8601) \
  --end-time $(date --iso-8601) \
  --period 300 \
  --statistics Sum
```

## Integration Testing

### 1. End-to-End Test
```bash
# Upload test file to Customer Account
aws s3 cp test-file.txt s3://customer-source-bucket/

# Monitor processing through pipeline
# Check Validation Account logs
# Check Diode Account logs
# Verify transfer completion
```

### 2. Simulator Testing
For development and testing, enable the Diode simulator:

1. Set `UseDiodeSimulator` to `True`
2. Deploy simulator infrastructure
3. Configure simulator endpoint
4. Test transfer operations without actual cross-domain transfer

## Performance Optimization

### 1. Lambda Configuration
- **Memory**: Default 128MB is sufficient for most operations
- **Timeout**: 30 seconds handles typical transfer operations
- **Concurrency**: No reserved concurrency set (uses account default)

### 2. SQS Configuration
- **Batch Size**: Set to 1 for immediate processing
- **Visibility Timeout**: Managed dynamically by Lambda
- **Message Retention**: 4 days provides adequate retry window

### 3. Monitoring Metrics
Key metrics to monitor:
- Lambda duration and error rate
- SQS queue depth and age of oldest message
- Diode service API call success rate
- EventBridge rule match rate

## Cleanup

### Console Method
1. Go to CloudFormation console
2. Select the Diode Account stack
3. Click **Delete**
4. Confirm deletion

### CLI Method
```bash
# Delete the stack
aws cloudformation delete-stack \
  --stack-name $STACK_NAME \
  --region $REGION

# Monitor deletion
aws cloudformation describe-stack-events \
  --stack-name $STACK_NAME \
  --region $REGION
```

**Note**: Ensure no active transfers are in progress before deleting the stack.

## Integration with Other Accounts

### Validation Account Integration
- **Inbound**: Receives transfer requests via SQS
- **Outbound**: Sends transfer results via SQS
- **Shared Resources**: Uses Validation Account's KMS key and S3 bucket

### Cross-Domain Integration
- **AWS Diode Service**: Handles actual data transfer
- **Destination Systems**: Receives transferred data
- **Monitoring**: Transfer status reported back through the pipeline

## Support and Maintenance

### Regular Maintenance
1. **Monitor Lambda Metrics**: Check execution duration and error rates
2. **Review SQS Queues**: Monitor message processing and dead letter queues
3. **Update Lambda Code**: Deploy new versions as needed
4. **Review IAM Permissions**: Audit cross-account access quarterly

### Scaling Considerations
- Lambda automatically scales based on SQS queue depth
- SQS queues handle high message volumes
- EventBridge rules process events in near real-time
- Consider reserved concurrency for predictable workloads

For additional support, refer to the main cross-account README or contact the infrastructure team.