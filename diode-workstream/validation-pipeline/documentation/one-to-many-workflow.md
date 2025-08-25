# AFTAC One-to-Many File Distribution Workflow

## Overview

The AFTAC One-to-Many workflow automatically distributes files from a source bucket to multiple destination buckets across different AWS accounts. The system uses S3 event notifications to trigger a Lambda function when objects are created in the source bucket, which then copies the file to multiple destination buckets based on a mapping configuration stored in Parameter Store.

## Architecture Flow

1. **File Upload**: File is uploaded to the source bucket (ingestion bucket)
2. **S3 Event Notification**: S3 bucket sends event notification directly to Lambda function
3. **Lambda Execution**: One-to-many Lambda function is invoked with S3 event data
4. **Tag Retrieval**: Lambda reads `DestinationMappingKey` from the object's tags
5. **Mapping Lookup**: Lambda retrieves destination bucket list from Parameter Store using the mapping key
6. **File Distribution**: Lambda downloads file locally and uploads to all destination buckets
7. **Success Handling**: If all transfers succeed, source file is deleted
8. **Failure Handling**: If any transfers fail, SNS notification is sent to configured email

## S3 Event Notification Setup

The CloudFormation stack includes a custom resource that automatically configures S3 event notifications on the source bucket. This custom resource:

- **Preserves Existing Notifications**: Reads current bucket notification configuration and preserves any existing SNS/SQS notifications
- **Adds Lambda Trigger**: Configures the source bucket to send `s3:ObjectCreated:*` events to the one-to-many Lambda function
- **Handles Cleanup**: Removes the Lambda notification configuration when the stack is deleted
- **Prevents Conflicts**: Uses a unique identifier (`OneToManyLambdaTrigger`) to avoid conflicts with other Lambda triggers

### What This Means for Deployment

- The source bucket will automatically be configured to trigger the Lambda function
- No manual S3 notification configuration is required
- Existing bucket notifications (SNS/SQS) will continue to work
- Stack deletion will clean up the notification configuration

## CloudFormation Parameters

### Required Parameters

- SourceBucket: "my-ingestion-bucket"
- LambdaCodeBucket: "my-lambda-code-bucket"
- LambdaCodeKey: "one-to-many.zip"
- NotificationEmail: "admin@example.com"
- RolePrefix: "AFC2S\_"
- PermissionsBoundaryARN: "arn:aws:iam::123456789012:policy/MyPermissionsBoundary"

### Parameter Descriptions

- **SourceBucket**: The S3 bucket that receives uploaded files and triggers the distribution
- **LambdaCodeBucket**: S3 bucket containing the Lambda deployment package
- **LambdaCodeKey**: S3 key for the Lambda zip file (defaults to "one-to-many.zip")
- **NotificationEmail**: Email address to receive failure notifications via SNS
- **RolePrefix**: Prefix for IAM role names (defaults to "AFC2S\_")
- **PermissionsBoundaryARN**: Optional permissions boundary ARN for IAM roles

## Parameter Store Configuration

The Lambda function reads destination bucket mappings from AWS Systems Manager Parameter Store. Each mapping key corresponds to a list of destination buckets.

### Parameter Store Structure

**Parameter Name Format**: `/pipeline/destination/{mapping-key}`

**Parameter Type**: String (comma-separated values)

### Example Parameter Store Values

```bash
# Parameter Name: /pipeline/destination/intel-distribution
# Parameter Value:
intel-bucket-east,intel-bucket-west,intel-backup-bucket

# Parameter Name: /pipeline/destination/ops-distribution
# Parameter Value:
ops-primary-bucket,ops-secondary-bucket

# Parameter Name: /pipeline/destination/archive-distribution
# Parameter Value:
archive-bucket-1,archive-bucket-2,archive-bucket-3,long-term-storage
```

### Creating Parameter Store Values

```bash
# AWS CLI example
aws ssm put-parameter \
  --name "/pipeline/destination/intel-distribution" \
  --value "intel-bucket-east,intel-bucket-west,intel-backup-bucket" \
  --type "String" \
  --description "Intel distribution bucket mapping"
```

## Bucket and Object Tagging System

The system uses a two-tier tagging approach where bucket tags are inherited by objects during the processing pipeline.

### Ingestion Bucket Configuration

The ingestion bucket must be configured with the following tag:

- **Tag Key**: `DestinationMappingKey`
- **Tag Value**: Space-separated mapping keys that exist in Parameter Store

### Example Ingestion Bucket Tags

```json
{
  "DestinationMappingKey": "intel-distribution ops-distribution"
}
```

### How Bucket Tags Are Set

Bucket tags are automatically configured during the ingestion bucket deployment via the `aftac_ingestion_bucket.yaml` CloudFormation template. The `IngestBucketDestinationMappingKey` parameter in the ingestion bucket stack sets the `DestinationMappingKey` tag on the bucket.

### Object Tag Inheritance

During the validation pipeline processing, the `DestinationMappingKey` tag from the bucket is automatically copied to each uploaded object. The one-to-many Lambda function then reads this tag from the object to determine distribution destinations.

## Cross-Account Permissions

### Destination Bucket Policies

Since destination buckets are in different accounts, they must have bucket policies that allow the Lambda function's role to write objects.

#### Required Destination Bucket Policy

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "AllowOneToManyLambdaAccess",
      "Effect": "Allow",
      "Principal": {
        "AWS": "arn:aws:iam::SOURCE-ACCOUNT-ID:role/AFC2S_OneToManyLambdaRole"
      },
      "Action": ["s3:PutObject", "s3:PutObjectAcl", "s3:PutObjectTagging"],
      "Resource": "arn:aws:s3:::DESTINATION-BUCKET-NAME/*"
    }
  ]
}
```

### KMS Key Policies (for encrypted buckets)

If destination buckets use KMS encryption, the KMS key policy must allow the Lambda role access.

#### Required KMS Key Policy Statement

```json
{
  "Sid": "AllowOneToManyLambdaKMSAccess",
  "Effect": "Allow",
  "Principal": {
    "AWS": "arn:aws:iam::SOURCE-ACCOUNT-ID:role/AFC2S_OneToManyLambdaRole"
  },
  "Action": [
    "kms:Encrypt",
    "kms:Decrypt",
    "kms:ReEncrypt*",
    "kms:GenerateDataKey*",
    "kms:DescribeKey"
  ],
  "Resource": "*"
}
```

## File Processing Behavior

### File Size Limitations

The Lambda function is configured with **2 GB of ephemeral storage** in `/tmp`, allowing processing of files up to approximately **2 GB** in size. Files larger than this will fail during the download phase.

#### Adjusting File Size Limits

**Via CloudFormation:**
Modify the `EphemeralStorage` configuration in the Lambda function:

```yaml
EphemeralStorage:
  Size: 4096 # 4 GB in MB (max is 10240 for 10 GB)
```

**Via AWS Console:**

1. Navigate to Lambda → Functions → `one-to-many-processor`
2. Go to Configuration → General configuration
3. Click Edit
4. Adjust "Ephemeral storage" (512 MB - 10,240 MB)
5. Save changes

**Cost Impact:** Each additional GB costs ~$0.0000000309 per GB-second. For most use cases, the cost increase is negligible compared to execution time costs.

### Execution Timeout

The Lambda function is configured with a **5-minute (300 second) timeout**. This should be sufficient for most file transfers, but may need adjustment for:

- Very large files (approaching 2 GB)
- Distribution to many destination buckets
- Slow network conditions

#### Adjusting Timeout

**Via CloudFormation:**
Modify the `Timeout` configuration in the Lambda function:

```yaml
Timeout: 900 # 15 minutes (maximum allowed)
```

**Via AWS Console:**

1. Navigate to Lambda → Functions → `one-to-many-processor`
2. Go to Configuration → General configuration
3. Click Edit
4. Adjust "Timeout" (1 second - 15 minutes)
5. Save changes

**Note:** Maximum Lambda timeout is 15 minutes (900 seconds).

### Success Scenario

1. Lambda downloads file from source bucket to temporary storage
2. Lambda uploads file to all destination buckets
3. Lambda verifies all uploads completed successfully
4. Lambda deletes the original file from source bucket
5. Process completes successfully

### Failure Scenario

1. Lambda attempts to copy file to all destination buckets
2. If any destination fails, Lambda continues with remaining destinations
3. If some destinations succeed but others fail:
   - Original file is NOT deleted from source bucket
   - SNS notification sent to configured email with failure details
4. If ALL destinations fail, Lambda function fails and original file remains

### SNS Failure Notifications

When transfers fail, an email notification is sent containing:

- Source bucket and file name
- Number of successful vs total transfers
- List of failed destination buckets
- Timestamp and error details

### Policy Variables to Replace

- **SOURCE-ACCOUNT-ID**: AWS account ID where the Lambda function is deployed
- **DESTINATION-BUCKET-NAME**: Name of the destination bucket
- **AFC2S_OneToManyLambdaRole**: Role name (includes RolePrefix parameter)

### Example Complete Bucket Policy

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "AllowOneToManyLambdaAccess",
      "Effect": "Allow",
      "Principal": {
        "AWS": "arn:aws:iam::123456789012:role/AFC2S_OneToManyLambdaRole"
      },
      "Action": ["s3:PutObject", "s3:PutObjectAcl", "s3:PutObjectTagging"],
      "Resource": "arn:aws:s3:::intel-bucket-east/*"
    }
  ]
}
```

## Lambda Function Permissions

The Lambda function requires the following permissions (automatically configured by CloudFormation):

### Source Account Permissions

- **S3**: GetObject, GetObjectTagging, DeleteObject on source bucket
- **SSM**: GetParameter on `/pipeline/destination/*` parameters
- **SNS**: Publish to failure notification topic
- **KMS**: GenerateDataKey, Encrypt, Decrypt on all keys (for encrypted buckets)
- **Lambda**: Basic execution role for CloudWatch Logs

### Cross-Account Permissions (configured by destination accounts)

- **S3**: PutObject, PutObjectAcl, PutObjectTagging on destination buckets
- **KMS**: Encrypt, Decrypt, GenerateDataKey on destination bucket KMS keys

## Deployment Steps

1. **Deploy CloudFormation Stack**: Deploy the one-to-many stack with required parameters
2. **Confirm SNS Subscription**: Check email and confirm SNS subscription for failure notifications
3. **Create Parameter Store Mappings**: Add destination bucket mappings to Parameter Store
4. **Configure Cross-Account Permissions**:
   - Apply bucket policies to all destination buckets
   - Update KMS key policies if buckets are encrypted
5. **Test File Upload**: Upload a tagged file to the source bucket to verify distribution
6. **Monitor**: Check CloudWatch Logs and verify files are distributed and source file deleted

## Error Handling

The Lambda function includes comprehensive error handling with retry logic:

### Automatic Retry Logic

- **Retryable Errors**: Network timeouts, throttling, and temporary service issues are automatically retried with exponential backoff
- **Non-Retryable Errors**: Access denied (403), invalid credentials, missing resources, and configuration errors fail immediately without retry
- **Maximum Retries**: Up to 3 retry attempts with increasing delays (1s, 2s, 4s)

### Partial Failure Handling

- **Individual Bucket Failures**: If copying to some destination buckets fails, the function continues processing remaining buckets
- **Success Threshold**: The function only fails if it cannot copy to ANY destination bucket
- **Detailed Logging**: Each failure is logged with specific error codes and bucket names

### Common Error Scenarios

- **Missing DestinationMappingKey tag**: Immediate failure with validation error
- **Parameter Store mapping not found**: Immediate failure with clear error message
- **Access denied to destination bucket**: No retry, logged as permission error
- **Network connectivity issues**: Automatic retry with exponential backoff
- **S3 throttling**: Automatic retry with exponential backoff

## Monitoring

Monitor the workflow using:

### CloudWatch Logs

- **Structured Logging**: All operations logged with appropriate levels (INFO, WARNING, ERROR, DEBUG)
- **Detailed Context**: Each log entry includes bucket names, file keys, and operation details
- **Error Details**: Failed operations include specific error codes and retry attempts
- **Success Tracking**: Successful copies logged with destination bucket confirmation

### CloudWatch Metrics

- **Lambda Invocation Metrics**: Function invocations, duration, and error rates
- **Custom Metrics**: Track partial failures and retry patterns
- **Throttling Metrics**: Monitor for Lambda or service throttling

### Recommended Alarms

- **High Error Rate**: Alert when Lambda error rate exceeds threshold
- **Long Duration**: Alert when function execution time is unusually high
- **Partial Failures**: Monitor logs for patterns of destination bucket failures

### Additional Monitoring

- **EventBridge Metrics**: Rule execution and failure metrics
- **S3 Access Logs**: Destination bucket access patterns and failures
- **Parameter Store Metrics**: Track parameter retrieval failures
