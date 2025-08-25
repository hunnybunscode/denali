# DIODE Pipeline Dashboard Application

## Table of Contents
1. [Overview](#overview)
2. [Architecture](#architecture)
3. [Project Structure](#project-structure)
4. [CDK Deployment Process](#cdk-deployment-process)
5. [Configuration](#configuration)
6. [Dashboard Features](#dashboard-features)
7. [Metrics Monitored](#metrics-monitored)
8. [Creating Custom Metrics](#creating-custom-metrics)
9. [Implementation Details](#implementation-details)
10. [Prerequisites](#prerequisites)
11. [Installation and Setup](#installation-and-setup)
12. [Deployment Instructions](#deployment-instructions)
13. [Advanced Features](#advanced-features)
14. [Testing](#testing)
15. [Troubleshooting](#troubleshooting)
16. [Security Considerations](#security-considerations)
17. [Performance Considerations](#performance-considerations)
18. [Maintenance and Updates](#maintenance-and-updates)

## Overview

The DIODE Pipeline Dashboard Application is a comprehensive AWS CDK-based monitoring solution designed to provide visibility into the DIODE validation pipeline infrastructure. This application creates a centralized CloudWatch dashboard that monitors critical pipeline components including SQS queues, Lambda functions, Auto Scaling Groups, and Dead Letter Queues (DLQs).

The application focuses on monitoring the operational health and performance of the DIODE validation pipeline, enabling operators to quickly identify bottlenecks, failures, and capacity issues within the data processing workflow.

## Architecture

### High-Level Architecture

The DIODE Pipeline Dashboard Application follows a serverless monitoring architecture pattern using AWS CloudWatch for metrics visualization. The application is deployed using AWS CDK, providing infrastructure-as-code capabilities for consistent and repeatable deployments.

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   CDK App       │───▶│  CloudFormation  │───▶│  AWS Resources  │
│   (Python)      │    │     Stack        │    │                 │
└─────────────────┘    └──────────────────┘    └─────────────────┘
                                                         │
                                                         ▼
┌─────────────────────────────────────────────────────────────────┐
│                    AWS Resources Created                        │
├─────────────────────────────────────────────────────────────────┤
│ • CloudWatch Dashboard (ValidationPipelineDashboard)           │
│ • CloudWatch Metrics (SQS, Lambda, EC2, DLQ)                  │
│ • Graph Widgets (Queue Metrics, Network Metrics, Lambda)      │
└─────────────────────────────────────────────────────────────────┘
```

### Component Architecture

The pipeline dashboard monitors four key infrastructure components:

1. **SQS Queue Monitoring**: Antivirus scanning queue metrics
2. **Dead Letter Queue Monitoring**: Failed message tracking
3. **Auto Scaling Group Monitoring**: EC2 network performance
4. **Lambda Function Monitoring**: Serverless function performance

### Pipeline Flow Architecture

```
┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│   Data      │───▶│  AV Scan    │───▶│  Lambda     │───▶│  Processing │
│   Ingestion │    │   Queue     │    │ Functions   │    │  Pipeline   │
└─────────────┘    └─────────────┘    └─────────────┘    └─────────────┘
                           │                   │
                           ▼                   ▼
                   ┌─────────────┐    ┌─────────────┐
                   │  Dead Letter│    │  Auto Scale │
                   │    Queue    │    │    Group    │
                   └─────────────┘    └─────────────┘
```

## Project Structure

```
pipeline-dashboard/
├── pipeline_dashboard/
│   ├── __init__.py                        # Package initialization
│   └── pipeline_dashboard_stack.py        # Main stack implementation
├── tests/
│   ├── unit/
│   │   ├── __init__.py
│   │   └── test_pipeline_dashboard_stack.py  # Unit tests
│   └── __init__.py
├── .gitignore                             # Git ignore rules
├── app.py                                 # CDK application entry point
├── cdk.json                               # CDK configuration and context
├── README.md                              # This documentation
├── requirements.txt                       # Python dependencies
├── requirements-dev.txt                   # Development dependencies
└── source.bat                             # Windows activation script
```

### File Descriptions

- **`app.py`**: The main entry point for the CDK application. Instantiates the PipelineDashboardStack with custom synthesizer configuration for cross-account deployments.
- **`pipeline_dashboard_stack.py`**: Contains the core logic for creating the validation pipeline CloudWatch dashboard with SQS, Lambda, and EC2 metrics.
- **`cdk.json`**: Configuration file containing CDK settings, feature flags, and pipeline component configurations.
- **`requirements.txt`**: Specifies the Python dependencies required for the application (aws-cdk-lib==2.202.0, constructs>=10.0.0).
- **`tests/`**: Contains unit tests for the stack implementation.

## CDK Deployment Process

### Understanding AWS CDK

AWS CDK (Cloud Development Kit) is a software development framework for defining cloud infrastructure using familiar programming languages. The CDK deployment process involves several key stages:

#### 1. Bootstrap Phase

Before deploying any CDK application, the target AWS environment must be bootstrapped. This process:

- Creates an S3 bucket for storing CDK assets (templates, code bundles)
- Creates IAM roles for CDK operations (deployment, file publishing, lookup)
- Sets up necessary permissions for deployment
- Creates CloudFormation execution roles

```bash
cdk bootstrap aws://ACCOUNT-NUMBER/REGION
```

The bootstrap process creates the following resources:
- **CDK Toolkit Stack**: Contains S3 bucket and IAM roles
- **S3 Bucket**: Stores CloudFormation templates and assets
- **IAM Roles**: Enable CDK to perform deployments on your behalf

#### 2. Synthesis Phase

During synthesis, the CDK:

- Executes the Python code in `app.py`
- Instantiates the PipelineDashboardStack class
- Converts CDK constructs (Dashboard, Metrics, Widgets) into CloudFormation templates
- Generates asset manifests for any bundled code or files
- Outputs everything to the `cdk.out/` directory

```bash
cdk synth
```

The synthesis process creates:
- **CloudFormation Template**: JSON template defining all AWS resources
- **Asset Manifest**: Inventory of files and dependencies
- **Tree Metadata**: Hierarchical view of all constructs

#### 3. Deployment Phase

During deployment, the CDK:

- Uploads assets to the bootstrap S3 bucket
- Creates or updates the PipelineDashboardStack CloudFormation stack
- Monitors the deployment progress through CloudFormation events
- Reports any errors or rollbacks
- Provides stack outputs and resource information

```bash
cdk deploy
```

### Custom Synthesizer Configuration

This application uses a custom `DefaultStackSynthesizer` configuration in `app.py` to support enterprise and cross-account deployments:

```python
synthesizer = cdk.DefaultStackSynthesizer(
    qualifier='hnb659fds',
    cloud_formation_execution_role='arn:${AWS::Partition}:iam::${AWS::Region}:role/cdk-hnb659fds-cfn-exec-role-{AWS::AccountId}-${AWS::Region}',
    deploy_role_arn='arn:${AWS::Partition}:iam::${AWS::Region}:role/cdk-hnb659fds-deploy-role-{AWS::AccountId}-${AWS::Region}',
    file_asset_publishing_role_arn='arn:${AWS::Partition}:iam::${AWS::Region}:role/cdk-hnb659fds-file-pub-role-{AWS::AccountId}-${AWS::Region}',
    image_asset_publishing_role_arn='arn:${AWS::Partition}:iam::${AWS::Region}:role/cdk-hnb659fds-image-pub-role-{AWS::AccountId}-${AWS::Region}',
    lookup_role_arn='arn:${AWS::Partition}:iam::${AWS::Region}:role/cdk-hnb659fds-lookup-role-{AWS::AccountId}-${AWS::Region}'
)
```

This configuration enables:
- **Cross-Account Deployment**: Deploy to different AWS accounts
- **Custom Qualifier**: Avoid conflicts with other CDK applications
- **Role Separation**: Use specific IAM roles for different operations
- **Enterprise Compliance**: Meet organizational security requirements

## Configuration

### Context Parameters

The application uses CDK context parameters defined in `cdk.json` to configure the pipeline dashboard. The configuration includes four key components:

```json
{
  "context": {
    "av_scan_queue_name": "your-av-scan-queue-name",
    "av_scan_dlq_name": "your-av-scan-dlq-name",
    "asg_name": "your-autoscaling-group-name",
    "monitored_lambda_functions": [
      "bucket-object-tagger-dev",
      "bucket-object-tagger-test",
      "dev-aftac-dfdl-DfdlParser",
      "presigned-url-generator-test"
    ]
  }
}
```

#### Configuration Parameters Explained

- **av_scan_queue_name**: Name of the SQS queue used for antivirus scanning operations
- **av_scan_dlq_name**: Name of the Dead Letter Queue for failed antivirus scan messages
- **asg_name**: Name of the Auto Scaling Group running the validation pipeline EC2 instances
- **monitored_lambda_functions**: Array of Lambda function names to monitor in the pipeline

#### Configuration Best Practices

1. **Resource Naming**: Use consistent naming conventions across environments
2. **Environment Separation**: Use different configurations for dev, test, and production
3. **Function Monitoring**: Include all critical Lambda functions in the monitoring list
4. **Queue Validation**: Ensure queue names correspond to actual SQS resources

### CDK Feature Flags

The `cdk.json` file includes comprehensive CDK feature flags that control CDK behavior and enable modern AWS features:

#### Security Features
- `@aws-cdk/core:checkSecretUsage`: Prevents accidental secret exposure
- `@aws-cdk/aws-iam:minimizePolicies`: Optimizes IAM policy sizes
- `@aws-cdk/aws-ec2:restrictDefaultSecurityGroup`: Enhances security group defaults

#### Performance Features
- `@aws-cdk/aws-lambda-nodejs:useLatestRuntimeVersion`: Uses latest Lambda runtimes
- `@aws-cdk/aws-ec2:ebsDefaultGp3Volume`: Uses GP3 volumes for better performance

#### Compatibility Features
- `@aws-cdk/core:target-partitions`: Supports AWS, AWS China, and AWS GovCloud
- `@aws-cdk/aws-ecs:arnFormatIncludesClusterName`: Modern ECS ARN formats

## Dashboard Features

### Validation Pipeline Dashboard

The application creates a single comprehensive dashboard named "ValidationPipelineDashboard" that includes multiple monitoring widgets:

#### 1. Queue Messaging Widget

**Purpose**: Monitor SQS queue activity and message flow
- **Metrics**: NumberOfMessagesReceived, NumberOfMessagesSent
- **Time Range**: 6 months (180 days)
- **Period**: 1-day aggregation
- **Width**: 12 units (half dashboard width)
- **Statistic**: Sum

**Use Cases**:
- Monitor queue throughput and processing rates
- Identify message processing bottlenecks
- Track queue activity patterns over time
- Detect unusual spikes or drops in message volume

#### 2. Queue Sent Message Size Widget

**Purpose**: Monitor the size of messages being processed
- **Metrics**: SentMessageSize
- **Time Range**: 6 months (180 days)
- **Period**: 1-day aggregation
- **Width**: 12 units
- **Statistic**: Sum

**Use Cases**:
- Monitor data volume flowing through the pipeline
- Identify large message patterns that might impact performance
- Capacity planning for queue processing
- Detect anomalous message sizes

#### 3. Dead Letter Queue (DLQ) Widget

**Purpose**: Monitor failed message processing
- **Metrics**: ApproximateNumberOfMessagesVisible
- **Time Range**: 6 months (180 days)
- **Period**: 1-day aggregation
- **Width**: 12 units
- **Statistic**: Sum

**Use Cases**:
- Monitor system reliability and error rates
- Identify recurring processing failures
- Track DLQ message accumulation
- Alert on system health degradation

#### 4. Auto Scaling Group Network Widget

**Purpose**: Monitor EC2 instance network performance
- **Metrics**: NetworkIn, NetworkOut
- **Time Range**: 6 months (180 days)
- **Period**: 1-day aggregation
- **Width**: 12 units
- **Statistic**: Sum

**Use Cases**:
- Monitor network bandwidth utilization
- Identify network bottlenecks
- Track data transfer patterns
- Capacity planning for network resources

#### 5. Lambda Function Widgets (Dynamic)

**Purpose**: Monitor individual Lambda function performance
- **Metrics**: Invocations, ConcurrentExecutions, Errors
- **Time Range**: 6 months (180 days)
- **Period**: 1-day aggregation
- **Width**: 24 units (full dashboard width)
- **Statistic**: Sum
- **Region**: Dynamically set to current AWS region

**Generated for each function in monitored_lambda_functions**:
- bucket-object-tagger-dev
- bucket-object-tagger-test
- dev-aftac-dfdl-DfdlParser
- presigned-url-generator-test

**Use Cases**:
- Monitor function execution frequency
- Track concurrent execution limits
- Identify function errors and failures
- Performance optimization and capacity planning

## Metrics Monitored

### SQS Queue Metrics (AWS/SQS Namespace)

#### 1. NumberOfMessagesReceived
- **Type**: Count metric
- **Statistic**: Sum
- **Description**: Number of messages received by the queue
- **Use Case**: Monitor queue input rate and system load
- **Dimension**: QueueName

#### 2. NumberOfMessagesSent
- **Type**: Count metric
- **Statistic**: Sum
- **Description**: Number of messages sent from the queue
- **Use Case**: Monitor queue processing rate and throughput
- **Dimension**: QueueName

#### 3. SentMessageSize
- **Type**: Size metric (bytes)
- **Statistic**: Sum
- **Description**: Size of messages sent from the queue
- **Use Case**: Monitor data volume and message payload sizes
- **Dimension**: QueueName

#### 4. ApproximateNumberOfMessagesVisible (DLQ)
- **Type**: Count metric
- **Statistic**: Sum
- **Description**: Number of messages visible in the Dead Letter Queue
- **Use Case**: Monitor failed message processing and system reliability
- **Dimension**: QueueName

### EC2 Auto Scaling Group Metrics (AWS/EC2 Namespace)

#### 1. NetworkIn
- **Type**: Network metric (bytes)
- **Statistic**: Sum
- **Description**: Network bytes received by EC2 instances
- **Use Case**: Monitor inbound network traffic and bandwidth utilization
- **Dimension**: AutoScalingGroupName

#### 2. NetworkOut
- **Type**: Network metric (bytes)
- **Statistic**: Sum
- **Description**: Network bytes sent by EC2 instances
- **Use Case**: Monitor outbound network traffic and data transfer
- **Dimension**: AutoScalingGroupName

### Lambda Function Metrics (AWS/Lambda Namespace)

#### 1. Invocations
- **Type**: Count metric
- **Statistic**: Sum
- **Description**: Number of times the function was invoked
- **Use Case**: Monitor function usage and execution frequency
- **Dimension**: FunctionName

#### 2. ConcurrentExecutions
- **Type**: Count metric
- **Statistic**: Sum
- **Description**: Number of concurrent executions
- **Use Case**: Monitor function concurrency and scaling behavior
- **Dimension**: FunctionName

#### 3. Errors
- **Type**: Count metric
- **Statistic**: Sum
- **Description**: Number of function execution errors
- **Use Case**: Monitor function reliability and error rates
- **Dimension**: FunctionName

### Metric Aggregation Strategy

The application uses consistent aggregation strategies across all metrics:

- **Time Period**: 1-day aggregation for all widgets
- **Time Range**: 6-month historical view (-P6M)
- **Statistic**: Sum for all count and size metrics
- **Update Frequency**: Real-time updates as metrics are published

## Creating Custom Metrics

### Overview

Custom metrics allow you to track application-specific data that isn't available through standard AWS service metrics. This section demonstrates how to create and publish custom metrics from Lambda functions and display them on dashboards.

### Example: Mission Area File Tracking

This example shows how to track file processing metrics by mission area in the data-transfer-result Lambda function:

#### 1. Publishing Custom Metrics in Lambda

```python
import boto3
import json
from datetime import datetime

# Initialize CloudWatch client
cloudwatch = boto3.client('cloudwatch')

def lambda_handler(event, context):
    # Extract mission area from file metadata or path
    mission_area = extract_mission_area(event)
    file_size = get_file_size(event)
    
    # Publish file count metric
    cloudwatch.put_metric_data(
        Namespace='DIODE/Pipeline',
        MetricData=[
            {
                'MetricName': 'FilesProcessed',
                'Dimensions': [
                    {
                        'Name': 'MissionArea',
                        'Value': mission_area
                    }
                ],
                'Value': 1,
                'Unit': 'Count',
                'Timestamp': datetime.utcnow()
            }
        ]
    )
    
    # Publish file size metric
    cloudwatch.put_metric_data(
        Namespace='DIODE/Pipeline',
        MetricData=[
            {
                'MetricName': 'TotalFileSize',
                'Dimensions': [
                    {
                        'Name': 'MissionArea',
                        'Value': mission_area
                    }
                ],
                'Value': file_size,
                'Unit': 'Bytes',
                'Timestamp': datetime.utcnow()
            }
        ]
    )
    
    # Continue with existing Lambda logic
    return process_file(event)

def extract_mission_area(event):
    """Extract mission area from S3 object key or metadata"""
    # Example: extract from S3 key path like 'mission-area-1/data/file.txt'
    s3_key = event['Records'][0]['s3']['object']['key']
    return s3_key.split('/')[0] if '/' in s3_key else 'unknown'

def get_file_size(event):
    """Get file size from S3 event"""
    return event['Records'][0]['s3']['object']['size']
```

#### 2. Batch Metric Publishing (Recommended)

```python
def publish_metrics_batch(mission_area, file_count, total_size):
    """Publish multiple metrics in a single API call"""
    cloudwatch.put_metric_data(
        Namespace='DIODE/Pipeline',
        MetricData=[
            {
                'MetricName': 'FilesProcessed',
                'Dimensions': [{'Name': 'MissionArea', 'Value': mission_area}],
                'Value': file_count,
                'Unit': 'Count'
            },
            {
                'MetricName': 'TotalFileSize',
                'Dimensions': [{'Name': 'MissionArea', 'Value': mission_area}],
                'Value': total_size,
                'Unit': 'Bytes'
            },
            {
                'MetricName': 'AverageFileSize',
                'Dimensions': [{'Name': 'MissionArea', 'Value': mission_area}],
                'Value': total_size / file_count if file_count > 0 else 0,
                'Unit': 'Bytes'
            }
        ]
    )
```

#### 3. Adding Custom Metrics to Dashboard

```python
# In pipeline_dashboard_stack.py

def create_mission_area_widgets(self, dashboard):
    """Create widgets for mission area custom metrics"""
    
    # Get list of mission areas from context or configuration
    mission_areas = self.node.try_get_context("mission_areas") or [
        "mission-area-1", "mission-area-2", "mission-area-3"
    ]
    
    for mission_area in mission_areas:
        # Files processed metric
        files_processed = cloudwatch.Metric(
            namespace="DIODE/Pipeline",
            metric_name="FilesProcessed",
            dimensions_map={"MissionArea": mission_area},
            statistic="Sum"
        )
        
        # Total file size metric
        total_file_size = cloudwatch.Metric(
            namespace="DIODE/Pipeline",
            metric_name="TotalFileSize",
            dimensions_map={"MissionArea": mission_area},
            statistic="Sum"
        )
        
        # Average file size metric
        avg_file_size = cloudwatch.Metric(
            namespace="DIODE/Pipeline",
            metric_name="AverageFileSize",
            dimensions_map={"MissionArea": mission_area},
            statistic="Average"
        )
        
        # Create widget for this mission area
        dashboard.add_widgets(
            cloudwatch.GraphWidget(
                title=f"{mission_area} File Processing Metrics",
                left=[files_processed],
                right=[total_file_size, avg_file_size],
                width=24,
                period=Duration.hours(1),
                start="-P7D"  # 7 days of data
            )
        )
```

#### 4. Configuration Update

Add mission areas to your `cdk.json` configuration:

```json
{
  "context": {
    "av_scan_queue_name": "your-av-scan-queue-name",
    "av_scan_dlq_name": "your-av-scan-dlq-name",
    "asg_name": "your-autoscaling-group-name",
    "monitored_lambda_functions": [
      "bucket-object-tagger-dev",
      "data-transfer-result"
    ],
    "mission_areas": [
      "mission-area-1",
      "mission-area-2",
      "mission-area-3"
    ]
  }
}
```

#### 5. Lambda IAM Permissions

Ensure your Lambda execution role has CloudWatch permissions:

```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "cloudwatch:PutMetricData"
            ],
            "Resource": "*"
        }
    ]
}
```

### Custom Metric Best Practices

#### 1. Namespace Organization
- Use hierarchical namespaces: `DIODE/Pipeline`, `DIODE/Validation`
- Avoid AWS service namespaces (AWS/*)
- Keep namespace names consistent across applications

#### 2. Dimension Strategy
- Use meaningful dimension names (MissionArea, Environment, Component)
- Limit dimensions to essential categorization (max 10 per metric)
- Consider cardinality impact on costs

#### 3. Metric Naming
- Use descriptive names: `FilesProcessed`, `ProcessingDuration`
- Follow consistent naming conventions
- Include units in names when helpful: `FileSizeBytes`

#### 4. Performance Optimization
- Batch multiple metrics in single `put_metric_data` calls
- Use appropriate metric resolution (standard vs high-resolution)
- Consider async metric publishing for high-throughput functions

#### 5. Cost Management
- Monitor custom metric usage and costs
- Use metric filters for log-based metrics when appropriate
- Consider metric retention policies

### Advanced Custom Metrics

#### Metric Math for Calculated Values

```python
# Create calculated metrics using metric math
processing_rate = cloudwatch.MathExpression(
    expression="files / PERIOD(files)",
    using_metrics={
        "files": cloudwatch.Metric(
            namespace="DIODE/Pipeline",
            metric_name="FilesProcessed",
            dimensions_map={"MissionArea": mission_area},
            statistic="Sum"
        )
    },
    label="Files per Second"
)
```

#### Composite Alarms

```python
# Create alarms based on custom metrics
files_alarm = cloudwatch.Alarm(
    self, f"FilesProcessedAlarm-{mission_area}",
    metric=files_processed,
    threshold=100,
    evaluation_periods=2,
    alarm_description=f"Low file processing rate for {mission_area}"
)
```

### Testing Custom Metrics

#### 1. Local Testing

```python
# Test metric publishing locally
import boto3
from moto import mock_cloudwatch

@mock_cloudwatch
def test_metric_publishing():
    cloudwatch = boto3.client('cloudwatch', region_name='us-east-1')
    
    # Test your metric publishing function
    publish_metrics_batch('test-mission', 5, 1024000)
    
    # Verify metrics were published
    metrics = cloudwatch.list_metrics(Namespace='DIODE/Pipeline')
    assert len(metrics['Metrics']) > 0
```

#### 2. Integration Testing

```bash
# Verify metrics in AWS
aws cloudwatch list-metrics --namespace DIODE/Pipeline

# Get metric statistics
aws cloudwatch get-metric-statistics \
  --namespace DIODE/Pipeline \
  --metric-name FilesProcessed \
  --dimensions Name=MissionArea,Value=mission-area-1 \
  --start-time $(date -d '1 hour ago' -u +%Y-%m-%dT%H:%M:%SZ) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%SZ) \
  --period 300 \
  --statistics Sum
```

## Implementation Details

### Dashboard Creation Process

The `PipelineDashboardStack` implements a structured approach to dashboard creation:

#### Step 1: Context Parameter Retrieval
```python
av_scan_queue = self.node.try_get_context("av_scan_queue_name")
av_scan_dlq = self.node.try_get_context("av_scan_dlq_name")
monitored_lambda_functions = self.node.try_get_context("monitored_lambda_functions")
asg_name = self.node.try_get_context("asg_name")
```
Retrieves configuration parameters from CDK context.

#### Step 2: Dashboard Initialization
```python
dashboard = cloudwatch.Dashboard(self, f"Pipeline-Dashboard", 
    dashboard_name=f"ValidationPipelineDashboard",
    period_override=cloudwatch.PeriodOverride.INHERIT)
```
Creates the main dashboard with period inheritance from individual widgets.

#### Step 3: Static Metric Creation
Creates metrics for SQS queues and Auto Scaling Groups:
```python
av_scan_queue_rcvd_msgs = cloudwatch.Metric(
    namespace="AWS/SQS",
    dimensions_map={"QueueName": av_scan_queue},  
    metric_name="NumberOfMessagesReceived",
    statistic="Sum",
)
```

#### Step 4: Static Widget Addition
Adds pre-configured widgets for infrastructure components:
```python
dashboard.add_widgets(
    cloudwatch.GraphWidget(
        title=f"Queue Messaging Widget",
        left=[av_scan_queue_rcvd_msgs, av_scan_queue_sent_msgs],  
        width=12,
        period=Duration.days(1),
        start='-P6M'
    )
)
```

#### Step 5: Dynamic Lambda Widget Generation
Iterates through monitored Lambda functions to create individual widgets:
```python
for function in monitored_lambda_functions:
    invocations = cloudwatch.Metric(
        namespace="AWS/Lambda",
        dimensions_map={"FunctionName": function},
        metric_name="Invocations",
        statistic="Sum",
    )
    
    dashboard.add_widgets(
        cloudwatch.GraphWidget(
            title=f"{function} Widget",
            left=[invocations, concurrent_executions, errors],
            width=24,
            period=Duration.days(1),
            start='-P6M',
            region=Aws.REGION
        )
    )
```

### Widget Configuration Details

#### Graph Widget Parameters
- **title**: Descriptive title identifying the monitored component
- **left**: Array of metrics displayed on the left Y-axis
- **width**: Widget width (12 = half dashboard, 24 = full width)
- **period**: Data aggregation interval (Duration.days(1))
- **start**: Relative start time using ISO 8601 duration format (-P6M)
- **region**: AWS region for metric queries (dynamically set)

#### Metric Configuration Parameters
- **namespace**: AWS service namespace (AWS/SQS, AWS/Lambda, AWS/EC2)
- **dimensions_map**: Key-value pairs for metric dimensions
- **metric_name**: Specific metric name from the AWS service
- **statistic**: Aggregation method (Sum for all metrics)

### Error Handling and Validation

The application includes several validation mechanisms:

1. **Context Validation**: Ensures required context parameters are provided
2. **Resource Validation**: Validates that referenced resources exist
3. **Metric Validation**: Ensures metrics are properly configured
4. **Widget Validation**: Validates widget configurations before deployment

## Prerequisites

### System Requirements

1. **Operating System**: Windows, macOS, or Linux
2. **Python**: Version 3.8 or higher
3. **Node.js**: Version 14 or higher (for CDK CLI)
4. **AWS CLI**: Version 2.0 or higher
5. **Git**: For version control and source management

### AWS Requirements

1. **AWS Account**: Active AWS account with appropriate permissions
2. **IAM Permissions**: Permissions to create CloudWatch dashboards and access metrics
3. **CDK Bootstrap**: Target environment must be CDK bootstrapped
4. **Pipeline Infrastructure**: Active DIODE pipeline components (SQS, Lambda, ASG)

### Infrastructure Prerequisites

The following AWS resources must exist before deploying the dashboard:

1. **SQS Queue**: Antivirus scanning queue
2. **Dead Letter Queue**: Failed message queue
3. **Auto Scaling Group**: EC2 instances for pipeline processing
4. **Lambda Functions**: All functions specified in the configuration

### Permission Requirements

The deployment requires the following AWS permissions:

```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "cloudwatch:PutDashboard",
                "cloudwatch:GetDashboard",
                "cloudwatch:DeleteDashboards",
                "cloudwatch:ListDashboards",
                "cloudwatch:GetMetricStatistics",
                "cloudwatch:ListMetrics"
            ],
            "Resource": "*"
        },
        {
            "Effect": "Allow",
            "Action": [
                "sqs:GetQueueAttributes",
                "sqs:ListQueues"
            ],
            "Resource": "*"
        },
        {
            "Effect": "Allow",
            "Action": [
                "lambda:ListFunctions",
                "lambda:GetFunction"
            ],
            "Resource": "*"
        },
        {
            "Effect": "Allow",
            "Action": [
                "autoscaling:DescribeAutoScalingGroups"
            ],
            "Resource": "*"
        },
        {
            "Effect": "Allow",
            "Action": [
                "cloudformation:*"
            ],
            "Resource": "*"
        }
    ]
}
```

## Installation and Setup

### Step 1: Environment Setup

#### Install Node.js and CDK CLI
```bash
# Install Node.js (if not already installed)
# Download from https://nodejs.org/

# Install AWS CDK CLI globally
npm install -g aws-cdk

# Verify installation
cdk --version
```

#### Install Python Dependencies
```bash
# Ensure Python 3.8+ is installed
python --version

# Verify pip is available
pip --version
```

### Step 2: Project Setup

#### Navigate to Project Directory
```bash
# Navigate to the pipeline-dashboard directory
cd pipeline-dashboard
```

#### Create Virtual Environment

**On Windows:**
```cmd
python -m venv .venv
.venv\Scripts\activate
```

**On macOS/Linux:**
```bash
python -m venv .venv
source .venv/bin/activate
```

#### Install Dependencies
```bash
# Install production dependencies
pip install -r requirements.txt

# Install development dependencies (optional)
pip install -r requirements-dev.txt
```

### Step 3: AWS Configuration

#### Configure AWS CLI
```bash
# Configure AWS credentials
aws configure

# Or use environment variables
export AWS_ACCESS_KEY_ID=your-access-key
export AWS_SECRET_ACCESS_KEY=your-secret-key
export AWS_DEFAULT_REGION=your-region
```

#### Set CDK Environment Variables

**On Windows:**
```cmd
set CDK_DEFAULT_ACCOUNT=123456789012
set CDK_DEFAULT_REGION=us-east-1
```

**On macOS/Linux:**
```bash
export CDK_DEFAULT_ACCOUNT=123456789012
export CDK_DEFAULT_REGION=us-east-1
```

## Deployment Instructions

### Step 1: Configuration

#### Update cdk.json
Edit the `cdk.json` file to include your specific pipeline component names:

```json
{
  "context": {
    "av_scan_queue_name": "your-actual-av-scan-queue",
    "av_scan_dlq_name": "your-actual-av-scan-dlq",
    "asg_name": "your-actual-autoscaling-group",
    "monitored_lambda_functions": [
      "your-lambda-function-1",
      "your-lambda-function-2",
      "your-lambda-function-3"
    ]
  }
}
```

#### Validate Configuration
```bash
# Verify SQS queues exist
aws sqs list-queues --queue-name-prefix your-av-scan-queue

# Verify Lambda functions exist
aws lambda list-functions --query 'Functions[?contains(FunctionName, `your-function-name`)]'

# Verify Auto Scaling Group exists
aws autoscaling describe-auto-scaling-groups --auto-scaling-group-names your-asg-name
```

### Step 2: Bootstrap (First Time Only)

```bash
# Bootstrap the CDK environment
cdk bootstrap

# For cross-account deployment
cdk bootstrap aws://TARGET-ACCOUNT/TARGET-REGION

# Verify bootstrap
aws cloudformation describe-stacks --stack-name CDKToolkit
```

### Step 3: Synthesis and Validation

```bash
# Synthesize CloudFormation templates
cdk synth

# Review the generated templates
ls cdk.out/
cat cdk.out/PipelineDashboardStack.template.json

# Validate CloudFormation template
aws cloudformation validate-template --template-body file://cdk.out/PipelineDashboardStack.template.json
```

### Step 4: Deployment

```bash
# Deploy the stack
cdk deploy

# Deploy with approval prompts disabled (use with caution)
cdk deploy --require-approval never

# Deploy to specific profile
cdk deploy --profile your-aws-profile

# Deploy with specific parameters
cdk deploy --parameters ParameterName=ParameterValue
```

### Step 5: Verification

#### Verify Dashboard Creation
```bash
# List CloudWatch dashboards
aws cloudwatch list-dashboards

# Get dashboard definition
aws cloudwatch get-dashboard --dashboard-name ValidationPipelineDashboard
```

#### Verify Metrics Access
```bash
# Test SQS metrics
aws cloudwatch get-metric-statistics \
  --namespace AWS/SQS \
  --metric-name NumberOfMessagesReceived \
  --dimensions Name=QueueName,Value=your-queue-name \
  --start-time 2024-01-01T00:00:00Z \
  --end-time 2024-01-02T00:00:00Z \
  --period 3600 \
  --statistics Sum

# Test Lambda metrics
aws cloudwatch get-metric-statistics \
  --namespace AWS/Lambda \
  --metric-name Invocations \
  --dimensions Name=FunctionName,Value=your-function-name \
  --start-time 2024-01-01T00:00:00Z \
  --end-time 2024-01-02T00:00:00Z \
  --period 3600 \
  --statistics Sum
```

#### Access Dashboard
1. Open AWS CloudWatch Console
2. Navigate to Dashboards
3. Select "ValidationPipelineDashboard"
4. Verify all widgets display data correctly

### Step 6: Updates and Maintenance

```bash
# Check for differences before deployment
cdk diff

# Deploy updates
cdk deploy

# View deployment logs
aws cloudformation describe-stack-events --stack-name PipelineDashboardStack

# Destroy stack (use with extreme caution)
cdk destroy
```

## Advanced Features

### Dynamic Lambda Function Monitoring

The application automatically creates monitoring widgets for each Lambda function specified in the configuration:

#### Dynamic Widget Generation
```python
for function in monitored_lambda_functions:
    # Create metrics for each function
    invocations = cloudwatch.Metric(...)
    concurrent_executions = cloudwatch.Metric(...)
    errors = cloudwatch.Metric(...)
    
    # Create widget for each function
    dashboard.add_widgets(
        cloudwatch.GraphWidget(
            title=f"{function} Widget",
            left=[invocations, concurrent_executions, errors],
            width=24,
            period=Duration.days(1),
            start='-P6M',
            region=Aws.REGION
        )
    )
```

#### Benefits
- **Scalability**: Easily add or remove Lambda functions from monitoring
- **Consistency**: Uniform monitoring across all functions
- **Maintenance**: Single configuration point for all Lambda monitoring
- **Flexibility**: Different functions can be monitored in different environments

### Cross-Region Support

The application includes explicit region support for Lambda metrics:

```python
region=Aws.REGION
```

This ensures:
- **Multi-Region Deployments**: Support for different AWS regions
- **Region Consistency**: Metrics are queried from the correct region
- **Dynamic Region Detection**: Automatically uses the deployment region

### Custom Synthesizer Integration

The application uses enterprise-grade synthesizer configuration:

#### Features
- **Cross-Account Support**: Deploy dashboards to monitoring accounts
- **Custom Qualifier**: Avoid conflicts with other CDK applications
- **Role Separation**: Use specific IAM roles for different operations
- **Asset Management**: Custom asset publishing configuration

#### Security Benefits
- **Principle of Least Privilege**: Specific roles for specific operations
- **Audit Trail**: Clear separation of deployment responsibilities
- **Compliance**: Meet enterprise security requirements
- **Isolation**: Separate deployment environments

## Testing

### Unit Testing

The application includes unit tests in the `tests/unit/` directory:

#### Running Tests
```bash
# Activate virtual environment
source .venv/bin/activate  # macOS/Linux
.venv\Scripts\activate     # Windows

# Run all tests
pytest tests/

# Run with verbose output
pytest -v tests/

# Run with coverage
pytest --cov=pipeline_dashboard tests/

# Run specific test file
pytest tests/unit/test_pipeline_dashboard_stack.py
```

#### Test Structure
```python
import aws_cdk as core
import aws_cdk.assertions as assertions
from pipeline_dashboard.pipeline_dashboard_stack import PipelineDashboardStack

def test_dashboard_creation():
    app = core.App()
    stack = PipelineDashboardStack(app, "test-stack")
    template = assertions.Template.from_stack(stack)
    
    # Test CloudWatch dashboard creation
    template.has_resource_properties("AWS::CloudWatch::Dashboard", {
        "DashboardName": "ValidationPipelineDashboard"
    })

def test_metric_configuration():
    app = core.App()
    stack = PipelineDashboardStack(app, "test-stack")
    template = assertions.Template.from_stack(stack)
    
    # Verify dashboard contains expected widgets
    template.has_resource_properties("AWS::CloudWatch::Dashboard", {
        "DashboardBody": assertions.Match.string_like_regexp(".*Queue Messaging Widget.*")
    })
```

### Integration Testing

#### Manual Testing Steps
1. Deploy to test environment
2. Verify dashboard creation in CloudWatch console
3. Check that all widgets display data
4. Validate metric queries return data
5. Test dashboard responsiveness and performance

#### Automated Testing
```bash
# Synthesize and validate templates
cdk synth --strict

# Run CDK validation
cdk doctor

# Validate CloudFormation templates
aws cloudformation validate-template --template-body file://cdk.out/PipelineDashboardStack.template.json

# Test metric availability
aws cloudwatch list-metrics --namespace AWS/SQS
aws cloudwatch list-metrics --namespace AWS/Lambda
aws cloudwatch list-metrics --namespace AWS/EC2
```

### Load Testing

#### Dashboard Performance Testing
```bash
# Test dashboard loading performance
time aws cloudwatch get-dashboard --dashboard-name ValidationPipelineDashboard

# Test metric query performance
time aws cloudwatch get-metric-statistics \
  --namespace AWS/SQS \
  --metric-name NumberOfMessagesReceived \
  --dimensions Name=QueueName,Value=your-queue \
  --start-time $(date -d '1 day ago' -u +%Y-%m-%dT%H:%M:%SZ) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%SZ) \
  --period 3600 \
  --statistics Sum
```

## Troubleshooting

### Common Issues and Solutions

#### 1. Missing Metrics Data

**Symptoms**: Dashboard widgets show "No data available"

**Causes**:
- Incorrect resource names in configuration
- Resources don't exist in the target account/region
- Insufficient permissions to access metrics
- Resources not generating metrics

**Solutions**:
```bash
# Verify SQS queue exists and has activity
aws sqs get-queue-attributes --queue-url $(aws sqs get-queue-url --queue-name your-queue-name --query 'QueueUrl' --output text) --attribute-names All

# Verify Lambda function exists and has invocations
aws lambda get-function --function-name your-function-name
aws logs describe-log-groups --log-group-name-prefix /aws/lambda/your-function-name

# Verify Auto Scaling Group exists
aws autoscaling describe-auto-scaling-groups --auto-scaling-group-names your-asg-name

# Check CloudWatch metrics availability
aws cloudwatch list-metrics --namespace AWS/SQS --metric-name NumberOfMessagesReceived
aws cloudwatch list-metrics --namespace AWS/Lambda --metric-name Invocations
aws cloudwatch list-metrics --namespace AWS/EC2 --metric-name NetworkIn
```

#### 2. Deployment Failures

**Symptoms**: CDK deploy fails with permission or resource errors

**Causes**:
- Insufficient IAM permissions
- CDK not bootstrapped
- Resource naming conflicts
- CloudFormation limits exceeded

**Solutions**:
```bash
# Check CDK bootstrap status
aws cloudformation describe-stacks --stack-name CDKToolkit

# Verify IAM permissions
aws sts get-caller-identity
aws iam simulate-principal-policy \
  --policy-source-arn $(aws sts get-caller-identity --query Arn --output text) \
  --action-names cloudwatch:PutDashboard \
  --resource-arns "*"

# Check CloudFormation limits
aws cloudformation describe-account-attributes

# Verify resource names don't conflict
aws cloudwatch list-dashboards --query 'DashboardEntries[?DashboardName==`ValidationPipelineDashboard`]'
```

#### 3. Context Parameter Issues

**Symptoms**: Configuration not loaded or resources not found

**Causes**:
- Malformed JSON in cdk.json
- Missing or incorrect context parameters
- Typos in resource names

**Solutions**:
```bash
# Validate JSON syntax
python -m json.tool cdk.json

# Check context loading
cdk context --list

# Clear context cache if needed
cdk context --clear

# Verify resource names match actual resources
aws sqs list-queues
aws lambda list-functions --query 'Functions[].FunctionName'
aws autoscaling describe-auto-scaling-groups --query 'AutoScalingGroups[].AutoScalingGroupName'
```

#### 4. Dashboard Performance Issues

**Symptoms**: Dashboard loads slowly or times out

**Causes**:
- Too many metrics in single widgets
- Long time ranges with high-resolution data
- Network connectivity issues
- CloudWatch API throttling

**Solutions**:
```bash
# Check CloudWatch API limits
aws logs describe-export-tasks --query 'exportTasks[?status==`RUNNING`]' --output table

# Optimize time ranges in configuration
# Reduce period resolution for long-term views
# Consider splitting widgets with many metrics

# Test individual metric queries
aws cloudwatch get-metric-statistics \
  --namespace AWS/SQS \
  --metric-name NumberOfMessagesReceived \
  --dimensions Name=QueueName,Value=your-queue \
  --start-time $(date -d '1 hour ago' -u +%Y-%m-%dT%H:%M:%SZ) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%SZ) \
  --period 300 \
  --statistics Sum
```

### Debugging Techniques

#### 1. Enable Debug Logging
```bash
# Enable CDK debug logging
export CDK_DEBUG=true
cdk deploy

# Enable AWS CLI debug logging
export AWS_CLI_DEBUG=true
aws cloudwatch list-dashboards
```

#### 2. CloudFormation Events Monitoring
```bash
# Monitor CloudFormation events during deployment
aws cloudformation describe-stack-events --stack-name PipelineDashboardStack --query 'StackEvents[0:10].[Timestamp,ResourceStatus,ResourceType,LogicalResourceId]' --output table

# Get detailed stack information
aws cloudformation describe-stacks --stack-name PipelineDashboardStack
```

#### 3. Resource Inspection
```bash
# Inspect created dashboard
aws cloudwatch get-dashboard --dashboard-name ValidationPipelineDashboard --query 'DashboardBody' --output text | python -m json.tool

# List all CloudWatch dashboards
aws cloudwatch list-dashboards --query 'DashboardEntries[].DashboardName'

# Check metric data availability
aws cloudwatch get-metric-statistics \
  --namespace AWS/SQS \
  --metric-name NumberOfMessagesReceived \
  --dimensions Name=QueueName,Value=your-queue-name \
  --start-time $(date -d '1 day ago' -u +%Y-%m-%dT%H:%M:%SZ) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%SZ) \
  --period 3600 \
  --statistics Sum
```

## Security Considerations

### Access Control

#### Dashboard Access
- Configure IAM policies to restrict dashboard access to authorized personnel
- Use AWS Organizations for centralized access control across accounts
- Implement resource-based policies for fine-grained access control
- Consider using AWS SSO for centralized authentication

#### Metric Data Security
- Dashboards display aggregated metrics only, not raw data
- CloudWatch metrics are encrypted at rest by default
- Metric data is transmitted over HTTPS
- No sensitive data is exposed through dashboard widgets

#### Deployment Security
- Use least-privilege IAM roles for CDK deployment
- Enable CloudTrail for deployment auditing and compliance
- Implement approval workflows for production deployments
- Use separate AWS accounts for different environments

### Best Practices

1. **Principle of Least Privilege**: Grant minimum required permissions for dashboard access
2. **Regular Access Reviews**: Periodically review who has access to monitoring dashboards
3. **Encryption**: Ensure all data is encrypted in transit and at rest
4. **Monitoring**: Monitor dashboard access and usage patterns
5. **Compliance**: Ensure compliance with organizational security policies

### Security Configuration Example

```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Principal": {
                "AWS": "arn:aws:iam::ACCOUNT:role/PipelineDashboardViewers"
            },
            "Action": [
                "cloudwatch:GetDashboard",
                "cloudwatch:ListDashboards"
            ],
            "Resource": "*",
            "Condition": {
                "StringEquals": {
                    "cloudwatch:dashboard-name": "ValidationPipelineDashboard"
                }
            }
        }
    ]
}
```

## Performance Considerations

### Dashboard Performance

#### Widget Optimization
- Limit the number of metrics per widget (current: 3 metrics per Lambda widget)
- Use appropriate time ranges for different monitoring needs
- Optimize metric queries for faster loading
- Consider widget placement and sizing for better user experience

#### Metric Aggregation
- Use appropriate statistics (Sum) for count-based metrics
- Choose optimal time periods (1-day aggregation) for historical analysis
- Consider metric math for complex calculations
- Use efficient dimension filtering

### Scalability Considerations

#### Dashboard Limits
- AWS CloudWatch: 500 dashboards per account
- Dashboard size: 100KB maximum per dashboard
- Widgets per dashboard: No hard limit, but performance degrades with many widgets
- Metric queries: Rate limits apply to CloudWatch API calls

#### Metric Limits
- CloudWatch metrics: 10 million metrics per account
- API rate limits: 400 requests per second for GetMetricStatistics
- Data retention: 15 months for detailed metrics
- Custom metrics: Additional costs apply

### Performance Optimization

#### Efficient Widget Configuration
```python
# Optimize metric queries with appropriate periods
cloudwatch.GraphWidget(
    title="Optimized Queue Widget",
    left=[queue_metric],
    width=12,
    period=Duration.days(1),  # Appropriate for 6-month view
    start="-P6M"  # Reasonable time range
)
```

#### Metric Query Optimization
```python
# Use efficient metric configurations
cloudwatch.Metric(
    namespace="AWS/SQS",
    metric_name="NumberOfMessagesReceived",
    statistic="Sum",  # Appropriate statistic
    dimensions_map={"QueueName": queue_name}  # Specific dimensions
)
```

## Maintenance and Updates

### Regular Maintenance Tasks

#### 1. Configuration Updates
- Review and update Lambda function lists quarterly
- Add new pipeline components as they are deployed
- Remove obsolete or decommissioned resources
- Update queue names if they change

#### 2. Dependency Updates
```bash
# Check for CDK updates
npm outdated -g aws-cdk

# Update CDK CLI
npm update -g aws-cdk

# Update Python dependencies
pip list --outdated
pip install --upgrade aws-cdk-lib constructs

# Update development dependencies
pip install --upgrade pytest
```

#### 3. Performance Monitoring
- Monitor dashboard loading times and user experience
- Review CloudWatch API usage and costs
- Optimize slow-loading widgets
- Consider dashboard consolidation if needed

#### 4. Cost Optimization
- Review CloudWatch dashboard costs
- Optimize metric retention periods
- Consider metric sampling for high-volume metrics
- Monitor CloudWatch API usage charges

### Update Procedures

#### 1. Configuration Changes
```bash
# Update cdk.json with new resource names
vim cdk.json

# Test configuration changes
cdk diff

# Deploy configuration updates
cdk deploy

# Verify changes in CloudWatch console
aws cloudwatch get-dashboard --dashboard-name ValidationPipelineDashboard
```

#### 2. Code Updates
```bash
# Update stack implementation
vim pipeline_dashboard/pipeline_dashboard_stack.py

# Run tests to verify changes
pytest tests/

# Check for breaking changes
cdk diff

# Deploy code updates
cdk deploy
```

#### 3. Rollback Procedures
```bash
# Rollback CloudFormation stack to previous version
aws cloudformation cancel-update-stack --stack-name PipelineDashboardStack

# Or deploy previous configuration from version control
git checkout previous-commit
cdk deploy

# Verify rollback success
aws cloudwatch list-dashboards
```

### Monitoring and Alerting

#### Dashboard Health Monitoring
```python
# Add CloudWatch alarms for dashboard health
dashboard_alarm = cloudwatch.Alarm(
    self,
    "DashboardHealthAlarm",
    metric=cloudwatch.Metric(
        namespace="AWS/CloudFormation",
        metric_name="StackUpdateComplete",
        dimensions_map={"StackName": "PipelineDashboardStack"}
    ),
    threshold=1,
    evaluation_periods=1,
    alarm_description="Pipeline Dashboard deployment health"
)
```

#### Automated Testing Pipeline
```bash
# Set up automated testing pipeline
# Example using GitHub Actions or AWS CodePipeline

# Validate configuration
python -m json.tool cdk.json

# Test CDK synthesis
cdk synth --strict

# Validate CloudFormation templates
aws cloudformation validate-template --template-body file://cdk.out/PipelineDashboardStack.template.json

# Deploy to test environment
cdk deploy --context environment=test

# Run integration tests
pytest tests/integration/
```

---

## Conclusion

The DIODE Pipeline Dashboard Application provides a comprehensive monitoring solution for the DIODE validation pipeline infrastructure. By leveraging AWS CDK and CloudWatch, it offers a robust, scalable, and maintainable approach to pipeline monitoring while providing rich visualization capabilities for operational oversight.

The application's focus on SQS queues, Lambda functions, Auto Scaling Groups, and Dead Letter Queues ensures complete visibility into the pipeline's health and performance, enabling proactive monitoring and rapid issue resolution.

For additional support or questions, please refer to the AWS CDK documentation or contact the development team.