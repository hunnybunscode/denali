# AFTAC One-to-Many File Distribution Workflow

## Overview

The AFTAC One-to-Many workflow automatically distributes files from a source bucket to multiple destination buckets across different AWS accounts. The system uses EventBridge to trigger a Lambda function when objects are created in the source bucket, which then copies the file to multiple destination buckets based on a mapping configuration stored in Parameter Store.

## Architecture Flow

1. **File Upload**: File is uploaded to the source bucket (ingestion bucket)
2. **Bucket Tag Configuration**: The ingestion bucket is pre-configured with a `DestinationMappingKey` tag
3. **Object Processing Pipeline**: Files go through the validation pipeline where bucket tags are copied to objects
4. **EventBridge Trigger**: S3 object creation event triggers EventBridge rule for the one-to-many function
5. **Lambda Execution**: One-to-many Lambda function is invoked
6. **Tag Retrieval**: Lambda reads `DestinationMappingKey` from the object's tags (inherited from bucket)
7. **Mapping Lookup**: Lambda retrieves destination bucket list from Parameter Store using the mapping key
8. **File Distribution**: Lambda copies the file to all destination buckets in the mapping

## CloudFormation Parameters

### Required Parameters

```yaml
Parameters:
  SourceBucket: "my-ingestion-bucket"
  LambdaCodeBucket: "my-lambda-code-bucket"
  LambdaCodeKey: "one-to-many.zip"
```

### Parameter Descriptions

- **SourceBucket**: The S3 bucket that receives uploaded files and triggers the distribution
- **LambdaCodeBucket**: S3 bucket containing the Lambda deployment package
- **LambdaCodeKey**: S3 key for the Lambda zip file (defaults to "one-to-many.zip")

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

## Cross-Account Bucket Policies

Since destination buckets are in different accounts, they must have bucket policies that allow the Lambda function's role to write objects.

### Required Destination Bucket Policy

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "AllowOneToManyLambdaAccess",
      "Effect": "Allow",
      "Principal": {
        "AWS": "arn:{AWS::Partition}:iam::SOURCE-ACCOUNT-ID:role/OneToManyLambdaRole"
      },
      "Action": [
        "s3:PutObject",
        "s3:PutObjectAcl",
        "s3:PutObjectTagging"
      ],
      "Resource": "arn:{AWS::Partition}:s3:::DESTINATION-BUCKET-NAME/*"
    },
    {
      "Sid": "AllowOneToManyLambdaListBucket",
      "Effect": "Allow",
      "Principal": {
        "AWS": "arn:{AWS::Partition}:iam::SOURCE-ACCOUNT-ID:role/OneToManyLambdaRole"
      },
      "Action": "s3:ListBucket",
      "Resource": "arn:{AWS::Partition}:s3:::DESTINATION-BUCKET-NAME"
    }
  ]
}
```

### Policy Variables to Replace

- **SOURCE-ACCOUNT-ID**: AWS account ID where the Lambda function is deployed
- **DESTINATION-BUCKET-NAME**: Name of the destination bucket
- **{AWS::Partition}**: Replace with appropriate partition (aws, aws-us-gov, aws-cn)

### Example for Multiple Destination Buckets

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "AllowOneToManyLambdaAccess",
      "Effect": "Allow",
      "Principal": {
        "AWS": "arn:{AWS::Partition}:iam::123456789012:role/OneToManyLambdaRole"
      },
      "Action": [
        "s3:PutObject",
        "s3:PutObjectAcl", 
        "s3:PutObjectTagging"
      ],
      "Resource": [
        "arn:{AWS::Partition}:s3:::intel-bucket-east/*",
        "arn:{AWS::Partition}:s3:::intel-bucket-west/*",
        "arn:{AWS::Partition}:s3:::intel-backup-bucket/*"
      ]
    },
    {
      "Sid": "AllowOneToManyLambdaListBucket",
      "Effect": "Allow",
      "Principal": {
        "AWS": "arn:{AWS::Partition}:iam::123456789012:role/OneToManyLambdaRole"
      },
      "Action": "s3:ListBucket",
      "Resource": [
        "arn:{AWS::Partition}:s3:::intel-bucket-east",
        "arn:{AWS::Partition}:s3:::intel-bucket-west", 
        "arn:{AWS::Partition}:s3:::intel-backup-bucket"
      ]
    }
  ]
}
```

## Lambda Function Permissions

The Lambda function requires the following permissions:

### Parameter Store Access
```json
{
  "Effect": "Allow",
  "Action": [
    "ssm:GetParameter",
    "ssm:GetParameters"
  ],
  "Resource": "arn:{AWS::Partition}:ssm:*:*:parameter/pipeline/destination/*"
}
```

### S3 Access (already included in CloudFormation)
- Read access to source bucket
- Write access to all destination buckets (via cross-account bucket policies)

## Deployment Steps

1. **Deploy CloudFormation Stack**: Deploy the one-to-many stack with required parameters
2. **Create Parameter Store Mappings**: Add destination bucket mappings to Parameter Store
3. **Configure Destination Bucket Policies**: Apply bucket policies to all destination buckets
4. **Test File Upload**: Upload a tagged file to the source bucket to verify distribution

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