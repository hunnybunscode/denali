# Customer Account - Source Bucket Infrastructure

This directory contains the CloudFormation template for deploying the customer-side infrastructure of the cross-account diode workstream. The Customer Account serves as the secure entry point for data into the validation and transfer pipeline.

## Overview

The Customer Account infrastructure creates a secure S3 bucket where customers can upload files that need to be transferred across security domains. When files are uploaded, they are automatically copied to the Validation Account for security scanning and processing.

## Architecture

```
┌─────────────────────────────────────┐
│           Customer Account          │
│                                     │
│  ┌─────────────┐    ┌─────────────┐ │
│  │   Source    │    │   Lambda    │ │
│  │   Bucket    │───▶│  Function   │ │
│  │ (KMS Encrypted) │ │ (Copy Files)│ │
│  └─────────────┘    └─────────────┘ │
│         │                    │      │
│         │                    │      │
│  ┌─────────────┐    ┌─────────────┐ │
│  │ Lifecycle   │    │ IAM Role    │ │
│  │ Policies    │    │ (Cross-Acct)│ │
│  └─────────────┘    └─────────────┘ │
└─────────────────────────────────────┘
                │
                ▼
┌─────────────────────────────────────┐
│         Validation Account          │
│                                     │
│         ┌─────────────┐             │
│         │ Ingestion   │             │
│         │   Bucket    │             │
│         └─────────────┘             │
└─────────────────────────────────────┘
```

## Components Deployed

### 1. Source S3 Bucket
- **Purpose**: Secure storage for customer file uploads
- **Encryption**: KMS encryption with customer-managed key
- **Access Control**: Public access blocked, restricted to authorized users
- **Event Notifications**: Triggers Lambda function on object creation
- **Lifecycle Management**: Automatic cleanup based on configured retention

### 2. Lambda Function (CopyObjectFunction)
- **Runtime**: Python 3.11
- **Purpose**: Automatically copies uploaded files to Validation Account
- **Timeout**: 15 minutes (900 seconds)
- **Memory**: 256 MB
- **Features**:
  - Cross-account S3 copy operations
  - Optional source file deletion after successful copy
  - Comprehensive error handling and logging
  - URL decoding for file names with special characters

### 3. KMS Encryption Key
- **Type**: Customer-managed KMS key
- **Purpose**: Encrypts S3 bucket and Lambda function
- **Key Rotation**: Enabled automatically
- **Access**: Restricted to account root and CloudWatch Logs service

### 4. IAM Execution Role
- **Purpose**: Provides Lambda function with necessary permissions
- **Permissions**:
  - Read access to source bucket
  - Write access to destination bucket (cross-account)
  - KMS decrypt permissions for source bucket key
  - KMS encrypt permissions for destination bucket key
  - CloudWatch Logs permissions

### 5. CloudWatch Log Group
- **Purpose**: Stores Lambda function execution logs
- **Retention**: 90 days
- **Encryption**: KMS encrypted with customer-managed key

## Configuration Parameters

### Required Parameters

| Parameter | Description | Example |
|-----------|-------------|---------|
| `SourceBucketName` | Name for the customer's source S3 bucket | `my-company-source-bucket` |
| `DestinationBucketName` | Name of the ingestion bucket in Validation Account | `validation-ingestion-bucket-abc123` |
| `DestinationBucketKeyArn` | ARN of the KMS key for the destination bucket | `arn:aws:kms:us-east-1:123456789012:key/12345678-1234-1234-1234-123456789012` |

### Optional Parameters

| Parameter | Description | Default | Options |
|-----------|-------------|---------|---------|
| `ObjectExpirationInDays` | Days to keep objects in source bucket | 30 | Any positive integer |
| `DeleteSourceObjects` | Delete source files after successful copy | false | true, false |

## Prerequisites

Before deploying this template, ensure you have:

1. **AWS Account Access**: Administrative permissions in the Customer Account
2. **Validation Account Information**:
   - Destination bucket name from the Validation Account deployment
   - KMS key ARN for the destination bucket encryption
3. **Network Connectivity**: Ensure the Customer Account can reach AWS S3 service endpoints
4. **IAM Permissions**: Ability to create IAM roles, KMS keys, S3 buckets, and Lambda functions

## Deployment Steps

### Option 1: AWS Console Deployment

#### Step 1: Access CloudFormation Console
1. Log into the AWS Management Console for your Customer Account
2. Navigate to **CloudFormation** service
3. Select the appropriate region for deployment

#### Step 2: Create Stack
1. Click **Create stack** → **With new resources (standard)**
2. Under **Template source**, select **Upload a template file**
3. Click **Choose file** and select `customer-source-bucket-template.yaml`
4. Click **Next**

#### Step 3: Configure Stack Parameters
1. **Stack name**: Enter a descriptive name (e.g., `customer-source-bucket-stack`)
2. **Source Bucket Configuration**:
   - **Source Bucket Name**: Enter unique bucket name (e.g., `my-company-diode-source-2024`)
   - **Object Expiration**: Set retention period (default: 30 days)
   - **Delete Source Objects**: Choose whether to delete files after copy (default: false)
3. **Destination Bucket Configuration**:
   - **Destination Bucket Name**: Enter the ingestion bucket name from Validation Account
   - **Destination Bucket Key ARN**: Enter the KMS key ARN from Validation Account
4. Click **Next**

#### Step 4: Configure Stack Options
1. **Tags** (Optional): Add tags for resource management
   - Key: `Environment`, Value: `Production`
   - Key: `Project`, Value: `DiodeWorkstream`
2. **Permissions**: Leave default (use current role)
3. **Advanced options**: Leave defaults unless specific requirements
4. Click **Next**

#### Step 5: Review and Deploy
1. Review all parameters and configuration
2. **Capabilities**: Check **I acknowledge that AWS CloudFormation might create IAM resources**
3. Click **Create stack**

#### Step 6: Monitor Deployment
1. Watch the **Events** tab for deployment progress
2. Deployment typically takes 3-5 minutes
3. Status will change to **CREATE_COMPLETE** when finished

### Option 2: AWS CLI Deployment

#### Step 1: Prepare Parameter File
Create a file named `parameters.json`:

```json
[
  {
    "ParameterKey": "SourceBucketName",
    "ParameterValue": "my-company-diode-source-2024"
  },
  {
    "ParameterKey": "DestinationBucketName", 
    "ParameterValue": "validation-ingestion-bucket-abc123"
  },
  {
    "ParameterKey": "DestinationBucketKeyArn",
    "ParameterValue": "arn:aws:kms:us-east-1:123456789012:key/12345678-1234-1234-1234-123456789012"
  },
  {
    "ParameterKey": "ObjectExpirationInDays",
    "ParameterValue": "30"
  },
  {
    "ParameterKey": "DeleteSourceObjects",
    "ParameterValue": "false"
  }
]
```

#### Step 2: Deploy Stack
```bash
# Set variables
STACK_NAME="customer-source-bucket-stack"
TEMPLATE_FILE="customer-source-bucket-template.yaml"
PARAMETERS_FILE="parameters.json"
REGION="us-east-1"

# Deploy the stack
aws cloudformation create-stack \
  --stack-name $STACK_NAME \
  --template-body file://$TEMPLATE_FILE \
  --parameters file://$PARAMETERS_FILE \
  --capabilities CAPABILITY_IAM \
  --region $REGION \
  --tags Key=Environment,Value=Production Key=Project,Value=DiodeWorkstream
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

#### Step 4: Get Stack Outputs
```bash
# Retrieve important outputs
aws cloudformation describe-stacks \
  --stack-name $STACK_NAME \
  --region $REGION \
  --query 'Stacks[0].Outputs'
```

## Post-Deployment Configuration

### 1. Verify Deployment
After successful deployment, verify the following:

```bash
# Check if source bucket was created
aws s3 ls | grep your-source-bucket-name

# Verify Lambda function exists
aws lambda list-functions --query 'Functions[?contains(FunctionName, `CopyObject`)]'

# Test bucket encryption
aws s3api get-bucket-encryption --bucket your-source-bucket-name
```

### 2. Test File Upload
Test the pipeline with a small file:

```bash
# Create a test file
echo "Test file for diode pipeline" > test-file.txt

# Upload to source bucket
aws s3 cp test-file.txt s3://your-source-bucket-name/

# Check Lambda function logs
aws logs describe-log-groups --log-group-name-prefix "/aws/lambda/"
```

### 3. Monitor Lambda Function
```bash
# Get recent Lambda invocations
aws logs filter-log-events \
  --log-group-name "/aws/lambda/your-function-name" \
  --start-time $(date -d '1 hour ago' +%s)000
```

## Security Considerations

### 1. Access Control
- Source bucket blocks all public access
- Lambda function uses least-privilege IAM role
- Cross-account access limited to specific destination bucket

### 2. Encryption
- All data encrypted at rest using customer-managed KMS keys
- Data encrypted in transit using TLS
- Lambda function environment encrypted

### 3. Monitoring
- CloudWatch Logs capture all Lambda execution details
- CloudTrail logs all API calls for audit purposes
- S3 access logging can be enabled for additional monitoring

## Troubleshooting

### Common Issues

#### 1. Permission Denied Errors
**Symptom**: Lambda function fails with access denied
**Solution**: 
- Verify destination bucket name and KMS key ARN are correct
- Ensure Validation Account has granted cross-account permissions
- Check IAM role policies in CloudFormation template

#### 2. Bucket Name Already Exists
**Symptom**: Stack creation fails with bucket name conflict
**Solution**:
- S3 bucket names must be globally unique
- Choose a more specific bucket name
- Include account ID or timestamp in bucket name

#### 3. Lambda Function Timeout
**Symptom**: Large file transfers fail with timeout
**Solution**:
- Current timeout is 15 minutes (maximum for Lambda)
- For larger files, consider using S3 Transfer Acceleration
- Monitor CloudWatch metrics for execution duration

### Debugging Commands

```bash
# Check Lambda function configuration
aws lambda get-function --function-name your-function-name

# View recent Lambda errors
aws logs filter-log-events \
  --log-group-name "/aws/lambda/your-function-name" \
  --filter-pattern "ERROR"

# Check S3 bucket policy
aws s3api get-bucket-policy --bucket your-source-bucket-name

# Verify KMS key permissions
aws kms describe-key --key-id your-kms-key-id
```

## Cleanup

To remove all resources created by this template:

### Console Method
1. Go to CloudFormation console
2. Select your stack
3. Click **Delete**
4. Confirm deletion

### CLI Method
```bash
# Delete the stack
aws cloudformation delete-stack \
  --stack-name $STACK_NAME \
  --region $REGION

# Monitor deletion progress
aws cloudformation describe-stack-events \
  --stack-name $STACK_NAME \
  --region $REGION
```

**Note**: If the S3 bucket contains objects, you must empty it before stack deletion:

```bash
# Empty the bucket first
aws s3 rm s3://your-source-bucket-name --recursive

# Then delete the stack
aws cloudformation delete-stack --stack-name $STACK_NAME
```

## Integration with Validation Account

This Customer Account infrastructure integrates with the Validation Account through:

1. **Cross-Account S3 Access**: Lambda function copies files to Validation Account bucket
2. **KMS Key Sharing**: Uses Validation Account's KMS key for destination encryption
3. **Event-Driven Processing**: File uploads trigger immediate processing in Validation Account

Ensure the Validation Account infrastructure is deployed first and provides the necessary:
- Ingestion bucket name
- KMS key ARN for destination bucket encryption
- Cross-account IAM permissions

## Support and Maintenance

### Regular Maintenance Tasks
1. **Monitor CloudWatch Logs**: Review Lambda execution logs weekly
2. **Check S3 Metrics**: Monitor upload patterns and storage usage
3. **Review IAM Permissions**: Audit cross-account access quarterly
4. **Update Lambda Runtime**: Keep Python runtime version current

### Performance Optimization
- Monitor Lambda duration and memory usage
- Consider S3 Transfer Acceleration for large files
- Implement S3 Intelligent Tiering for cost optimization

For additional support, refer to the main cross-account README or contact the infrastructure team.