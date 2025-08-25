# DIODE Dashboard Application

## Table of Contents
1. [Overview](#overview)
2. [Architecture](#architecture)
3. [Project Structure](#project-structure)
4. [CDK Deployment Process](#cdk-deployment-process)
5. [Configuration](#configuration)
6. [Dashboard Features](#dashboard-features)
7. [Metrics Monitored](#metrics-monitored)
8. [Implementation Details](#implementation-details)
9. [Prerequisites](#prerequisites)
10. [Installation and Setup](#installation-and-setup)
11. [Deployment Instructions](#deployment-instructions)
12. [Adding New Metrics to Dashboards](#adding-new-metrics-to-dashboards)
13. [Advanced Features](#advanced-features)
14. [Testing](#testing)
15. [Troubleshooting](#troubleshooting)
16. [Security Considerations](#security-considerations)
17. [Performance Considerations](#performance-considerations)
18. [Maintenance and Updates](#maintenance-and-updates)

## Overview

The DIODE Dashboard Application is a sophisticated AWS CDK-based solution designed to monitor and visualize DIODE (Data Input/Output Diode Environment) transfer activities across multiple mission areas. This application creates comprehensive CloudWatch dashboards that provide real-time and historical metrics for DIODE transfers, enabling operators to monitor data flow, identify bottlenecks, and ensure the health of the DIODE system.

The application dynamically generates CloudWatch dashboards based on mission area configurations, providing a scalable and maintainable monitoring solution for complex DIODE environments.

## Architecture

### High-Level Architecture

The DIODE Dashboard Application follows a serverless architecture pattern using AWS CloudWatch for metrics visualization and AWS Systems Manager (SSM) Parameter Store for configuration storage. The application is deployed using AWS CDK, which provides infrastructure-as-code capabilities.

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
│ • CloudWatch Dashboards (Mission Area Specific)                │
│ • CloudWatch Metrics (DIODE Transfer Metrics)                  │
│ • SSM Parameter (Dashboard Mapping Storage)                    │
└─────────────────────────────────────────────────────────────────┘
```

### Component Architecture

1. **CDK Application Layer**: Python-based CDK application that defines infrastructure
2. **Configuration Layer**: Context-based configuration in `cdk.json`
3. **Dashboard Generation Layer**: Dynamic dashboard creation based on mission areas
4. **Metrics Layer**: CloudWatch metrics from DIODE system
5. **Storage Layer**: SSM Parameter Store for dashboard mappings

## Project Structure

```
diode-dashboard/
├── diode_dashboard/
│   ├── __init__.py                    # Package initialization
│   └── diode_dashboard_stack.py       # Main stack implementation
├── tests/
│   ├── unit/
│   │   ├── __init__.py
│   │   └── test_diode_dashboard_stack.py  # Unit tests
│   └── __init__.py
├── .gitignore                         # Git ignore rules
├── app.py                             # CDK application entry point
├── cdk.json                           # CDK configuration and context
├── README.md                          # This documentation
├── requirements.txt                   # Python dependencies
├── requirements-dev.txt               # Development dependencies
└── source.bat                         # Windows activation script
```

### File Descriptions

- **`app.py`**: The main entry point for the CDK application. Instantiates the DiodeDashboardStack with custom synthesizer configuration for cross-account deployments.
- **`diode_dashboard_stack.py`**: Contains the core logic for creating CloudWatch dashboards, metrics, and SSM parameters.
- **`cdk.json`**: Configuration file containing CDK settings, feature flags, and mission area mappings.
- **`requirements.txt`**: Specifies the Python dependencies required for the application.
- **`tests/`**: Contains unit tests for the stack implementation.

## CDK Deployment Process

### Understanding AWS CDK

AWS CDK (Cloud Development Kit) is a software development framework for defining cloud infrastructure using familiar programming languages. The CDK deployment process involves several key stages:

#### 1. Bootstrap Phase

Before deploying any CDK application, the target AWS environment must be bootstrapped. This process:

- Creates an S3 bucket for storing CDK assets (templates, code bundles)
- Creates IAM roles for CDK operations
- Sets up necessary permissions for deployment
- Creates CloudFormation execution roles

```bash
cdk bootstrap aws://ACCOUNT-NUMBER/REGION
```

#### 2. Synthesis Phase

During synthesis, the CDK:

- Executes the Python code in `app.py`
- Instantiates the stack classes
- Converts CDK constructs into CloudFormation templates
- Generates asset manifests for any bundled code or files
- Outputs everything to the `cdk.out/` directory

```bash
cdk synth
```

#### 3. Deployment Phase

During deployment, the CDK:

- Uploads assets to the bootstrap S3 bucket
- Creates or updates CloudFormation stacks
- Monitors the deployment progress
- Reports any errors or rollbacks

```bash
cdk deploy
```

### Custom Synthesizer Configuration

This application uses a custom `DefaultStackSynthesizer` configuration in `app.py` to support cross-account deployments:

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

This configuration specifies custom IAM roles for different CDK operations, enabling deployment across different AWS accounts and regions.

## Configuration

### Context Parameters

The application uses CDK context parameters defined in `cdk.json` to configure the dashboards. The primary configuration is the `mapping_ids` parameter:

```json
{
  "context": {
    "mapping_ids": {
      "MissionAreaName1": {
        "FriendlyName1": "mapping-id-1",
        "FriendlyName2": "mapping-id-2"
      },
      "MissionAreaName2": {
        "FriendlyName1": "mapping-id-1",
        "FriendlyName2": "mapping-id-2"
      }
    }
  }
}
```

#### Configuration Parameters Explained

- **MissionAreaName**: The name of the mission area (used in dashboard titles and organization)
- **FriendlyName**: A human-readable name for the mapping (displayed in widget labels and legends)
- **mapping-id**: The actual DIODE mapping ID used to query CloudWatch metrics

#### Configuration Best Practices

1. **Naming Conventions**: Use consistent naming patterns for mission areas and friendly names
2. **Mapping ID Validation**: Ensure mapping IDs correspond to actual DIODE mappings
3. **Scalability**: Consider the 5-mapping-per-dashboard limit when planning configurations
4. **Documentation**: Maintain documentation of mapping ID to system component relationships

### CDK Feature Flags

The `cdk.json` file includes numerous CDK feature flags that control CDK behavior:

- **Security Features**: Enable security best practices
- **Compatibility Features**: Maintain backward compatibility
- **Performance Features**: Optimize resource creation
- **Behavioral Features**: Control CDK construct behavior

## Dashboard Features

### Mission Area Dashboards

Each mission area dashboard is automatically generated and includes comprehensive monitoring widgets:

#### 1. Transfer Activity Graphs

**Long-term Trend Analysis (365 Days)**
- **Period**: 30-day aggregation
- **Metrics**: Transfer Created Count, Succeeded Transfer Count
- **Purpose**: Identify long-term trends and seasonal patterns
- **Width**: 12 units (half dashboard width)

**Medium-term Analysis (14 Days)**
- **Period**: 1-day aggregation
- **Metrics**: Transfer Created Count, Succeeded Transfer Count
- **Purpose**: Monitor recent performance and identify issues
- **Width**: 12 units

**Real-time Monitoring (14 Days)**
- **Period**: 1-minute aggregation
- **Metrics**: Transfer Created Count, Succeeded Transfer Count
- **Purpose**: Real-time monitoring and immediate issue detection
- **Width**: 12 units

#### 2. Transfer Size Analysis

**Annual Size Trends (12 Months)**
- **Period**: 30-day aggregation
- **Metrics**: Succeeded Transfer Size
- **Purpose**: Capacity planning and growth analysis
- **Width**: 12 units

**Recent Size Patterns (14 Days)**
- **Period**: 1-day aggregation
- **Metrics**: Succeeded Transfer Size
- **Purpose**: Monitor data volume patterns
- **Width**: 12 units

#### 3. In-Transit Monitoring

**In-Transit Count Monitoring (14 Days)**
- **Period**: 1-day aggregation
- **Metrics**: In-Transit Transfer Count
- **Purpose**: Monitor queue depth and processing capacity
- **Width**: 12 units

**In-Transit Size Monitoring (14 Days)**
- **Period**: 1-day aggregation
- **Metrics**: In-Transit Transfer Size
- **Purpose**: Monitor data volume in processing pipeline
- **Width**: 12 units

**Real-time In-Transit Monitoring (1 Day)**
- **Period**: 5-minute aggregation
- **Metrics**: In-Transit Transfer Count
- **Purpose**: Immediate visibility into processing bottlenecks
- **Width**: 12 units

#### 4. Success and Failure Analysis

**Real-time Success Monitoring (1 Day)**
- **Period**: 5-minute aggregation
- **Metrics**: Succeeded Transfer Count
- **Purpose**: Monitor processing success rates
- **Width**: 12 units

**Real-time Failure Monitoring (1 Day)**
- **Period**: 5-minute aggregation
- **Metrics**: Rejected Transfer Count
- **Purpose**: Immediate failure detection and alerting
- **Width**: 12 units

#### 5. Single Value Widgets

For each mapping in the mission area:

**Success Summary (12 Months)**
- **Metric**: Succeeded Transfer Count
- **Period**: 365 days
- **Purpose**: High-level success metrics
- **Width**: 6 units

**Creation Summary (12 Months)**
- **Metric**: Transfer Created Count
- **Period**: 365 days
- **Purpose**: High-level activity metrics
- **Width**: 6 units

## Metrics Monitored

### DIODE System Metrics

The application monitors six key metrics from the AWS/Diode namespace:

#### 1. TransferCreatedCount
- **Type**: Count metric
- **Statistic**: Sum
- **Description**: Number of transfer requests initiated
- **Use Case**: Monitor system load and user activity
- **Dimension**: MappingId

#### 2. SucceededTransferCount
- **Type**: Count metric
- **Statistic**: Sum
- **Description**: Number of transfers completed successfully
- **Use Case**: Monitor system effectiveness and success rates
- **Dimension**: MappingId

#### 3. SucceededTransferSize
- **Type**: Size metric (bytes)
- **Statistic**: Sum
- **Description**: Total size of successful transfers
- **Use Case**: Monitor data throughput and capacity utilization
- **Dimension**: MappingId

#### 4. InTransitTransferSize
- **Type**: Size metric (bytes)
- **Statistic**: Average
- **Description**: Size of transfers currently being processed
- **Use Case**: Monitor processing pipeline capacity
- **Dimension**: MappingId

#### 5. InTransitTransferCount
- **Type**: Count metric
- **Statistic**: Average
- **Description**: Number of transfers currently being processed
- **Use Case**: Monitor queue depth and processing bottlenecks
- **Dimension**: MappingId

#### 6. RejectedTransferCount
- **Type**: Count metric
- **Statistic**: Sum
- **Description**: Number of transfers that failed or were rejected
- **Use Case**: Monitor system errors and failure patterns
- **Dimension**: MappingId

### Metric Aggregation Strategy

The application uses different aggregation strategies based on metric type:

- **Count Metrics**: Use "Sum" statistic to aggregate discrete events
- **Size Metrics**: Use "Sum" statistic for throughput, "Average" for current state
- **Time Periods**: Vary from 1 minute (real-time) to 30 days (long-term trends)

## Implementation Details

### Dashboard Creation Algorithm

The `DiodeDashboardStack` implements a sophisticated algorithm for dashboard creation:

#### Step 1: Configuration Processing
```python
mission_mappings = self.node.try_get_context("mapping_ids")
```
Retrieves mission area configurations from CDK context.

#### Step 2: Chunking Algorithm
```python
list_size = 5  # Maximum mappings per dashboard
```
Splits mappings into chunks to prevent dashboard overcrowding.

#### Step 3: Dashboard Naming
```python
dashboard_name = f"{mission_area}-Dashboard"
if len(mapping_chunks) > 1:
    dashboard_name = f"{mission_area}-Dashboard-{chunk_index+1}"
```
Generates unique dashboard names with sequential numbering.

#### Step 4: Metric Creation
For each mapping, creates six CloudWatch metrics with friendly name labels:
```python
transfer_created_count = cloudwatch.Metric(
    namespace="AWS/Diode",
    dimensions_map={"MappingId": mapping_id},
    metric_name="TransferCreatedCount",
    statistic="Sum",
    label=f"{friendly_name} - TransferCreatedCount"
)
```

#### Step 5: Widget Generation
Creates multiple widget types:
- Graph widgets for time-series data
- Single value widgets for summary metrics

#### Step 6: SSM Parameter Storage
```python
ssm.StringParameter(
    self,
    "CompleteDashboardMappings",
    parameter_name="/diode/dashboards/complete-mappings",
    string_value=json.dumps(dashboard_mappings)
)
```
Stores complete mapping structure for reference.

### Widget Configuration Details

#### Graph Widget Configuration
```python
cloudwatch.GraphWidget(
    title=f"{mission_area} Transfer Activity: Preceding 365 Days by month",
    left=all_transfer_created_count + all_succeeded_transfer_count,
    width=12,
    period=Duration.days(30),
    start='-P12M'
)
```

**Parameters Explained**:
- **title**: Descriptive title including mission area and time range
- **left**: Metrics displayed on left Y-axis
- **width**: Widget width (12 = half dashboard, 24 = full width)
- **period**: Data aggregation interval
- **start**: Relative start time using ISO 8601 duration format

#### Single Value Widget Configuration
```python
cloudwatch.SingleValueWidget(
    metrics=[all_succeeded_transfer_count[i]],
    title=f"{friendly_name} Succeeded - Last 12 Months",
    width=6,
    period=Duration.days(365)
)
```

### Error Handling and Validation

The application includes several error handling mechanisms:

1. **Context Validation**: Checks for required context parameters
2. **Metric Validation**: Ensures metrics are properly configured
3. **Dashboard Limits**: Respects AWS CloudWatch dashboard limits
4. **Resource Naming**: Ensures unique resource names

## Prerequisites

### System Requirements

1. **Operating System**: Windows, macOS, or Linux
2. **Python**: Version 3.8 or higher
3. **Node.js**: Version 14 or higher (for CDK CLI)
4. **AWS CLI**: Version 2.0 or higher
5. **Git**: For version control

### AWS Requirements

1. **AWS Account**: Active AWS account with appropriate permissions
2. **IAM Permissions**: Permissions to create CloudWatch dashboards, SSM parameters
3. **CDK Bootstrap**: Target environment must be CDK bootstrapped
4. **DIODE System**: Active DIODE system publishing metrics to CloudWatch

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
                "cloudwatch:ListDashboards"
            ],
            "Resource": "*"
        },
        {
            "Effect": "Allow",
            "Action": [
                "ssm:PutParameter",
                "ssm:GetParameter",
                "ssm:DeleteParameter"
            ],
            "Resource": "arn:aws:ssm:*:*:parameter/diode/dashboards/*"
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

# Install pip if not available
# Instructions vary by operating system
```

### Step 2: Project Setup

#### Clone and Navigate
```bash
# Navigate to the project directory
cd diode-dashboard
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
Edit the `cdk.json` file to include your specific mission areas and mapping IDs:

```json
{
  "context": {
    "mapping_ids": {
      "YourMissionArea1": {
        "System1": "your-mapping-id-1",
        "System2": "your-mapping-id-2"
      },
      "YourMissionArea2": {
        "SystemA": "your-mapping-id-3",
        "SystemB": "your-mapping-id-4"
      }
    }
  }
}
```

### Step 2: Bootstrap (First Time Only)

```bash
# Bootstrap the CDK environment
cdk bootstrap

# For cross-account deployment
cdk bootstrap aws://TARGET-ACCOUNT/TARGET-REGION
```

### Step 3: Synthesis and Validation

```bash
# Synthesize CloudFormation templates
cdk synth

# Review the generated templates in cdk.out/
ls cdk.out/
```

### Step 4: Deployment

```bash
# Deploy the stack
cdk deploy

# Deploy with approval prompts disabled (use with caution)
cdk deploy --require-approval never

# Deploy to specific profile
cdk deploy --profile your-aws-profile
```

### Step 5: Verification

1. **Check CloudFormation Console**: Verify stack deployment status
2. **Check CloudWatch Console**: Verify dashboards are created
3. **Check SSM Console**: Verify parameter is stored
4. **Test Dashboard Access**: Open dashboards and verify metrics display

### Step 6: Updates and Maintenance

```bash
# Check for differences before deployment
cdk diff

# Deploy updates
cdk deploy

# Destroy stack (use with extreme caution)
cdk destroy
```

## Adding New Metrics to Dashboards

### Overview

This section provides a comprehensive guide for adding new metrics to the DIODE dashboards. The process involves discovering available metrics, creating metric objects, configuring widgets, and integrating them into the dashboard layout.

### Step 1: Discover Available Metrics

#### Method 1: Find Metrics via AWS Console

**Navigate to CloudWatch Metrics:**
1. Open AWS Console → CloudWatch → Metrics → All metrics
2. In the "Browse" tab, look for "AWS/Diode" namespace
3. Click on "AWS/Diode" to expand available metrics
4. Click on dimension categories (e.g., "MappingId") to see specific metrics

**Identify Metric Details:**
1. **Namespace**: Will show as "AWS/Diode" in the breadcrumb
2. **Metric Name**: Listed in the "Metric name" column (e.g., "ProcessingLatency")
3. **Dimensions**: Shown in dimension columns (e.g., "MappingId: mapping-123")
4. **Available Statistics**: Click "Graphed metrics" tab to see Sum, Average, Maximum options

**Console Screenshot Reference:**
```
CloudWatch > Metrics > All metrics
├── AWS/Diode
│   ├── MappingId
│   │   ├── ProcessingLatency        [MappingId: mapping-123]
│   │   ├── TransferCreatedCount     [MappingId: mapping-123]
│   │   └── CustomMetricName         [MappingId: mapping-456]
│   └── Other Dimensions...
```

**Verify Metric Data:**
1. Select the checkbox next to your desired metric
2. Click "Graphed metrics" tab to see the metric plotted
3. Note the "Statistic" column (Sum, Average, etc.)
4. Check "Period" to understand data granularity
5. Verify data points exist in the graph

#### Method 2: Find Metrics via AWS CLI

For programmatic discovery or automation:

```bash
# List all metrics in the AWS/Diode namespace
aws cloudwatch list-metrics --namespace AWS/Diode

# List metrics for a specific metric name
aws cloudwatch list-metrics --namespace AWS/Diode --metric-name YourNewMetricName

# List metrics with specific dimensions
aws cloudwatch list-metrics --namespace AWS/Diode --dimensions Name=MappingId,Value=your-mapping-id
```

**Example CLI Output:**
```json
{
    "Metrics": [
        {
            "Namespace": "AWS/Diode",
            "MetricName": "ProcessingLatency",
            "Dimensions": [
                {
                    "Name": "MappingId",
                    "Value": "mapping-123"
                }
            ]
        }
    ]
}
```

#### Identify Required Attributes

From either the Console or CLI, note these key attributes:

**From Console:**
- **Namespace**: Shown in breadcrumb (e.g., `AWS/Diode`)
- **MetricName**: Listed in "Metric name" column (e.g., `ProcessingLatency`)
- **Dimensions**: Shown as column headers and values (e.g., `MappingId: mapping-123`)
- **Statistic**: Available in "Graphed metrics" tab (Sum, Average, Maximum, etc.)

**From CLI Output:**
- **Namespace**: `AWS/Diode` (for DIODE metrics)
- **MetricName**: The exact name of the metric (e.g., `ProcessingLatency`)
- **Dimensions**: Key-value pairs that identify the metric source (e.g., `MappingId: mapping-123`)

**Console Tips:**
- Use the search box to filter metrics by name
- Click "Add to dashboard" to see metric configuration options
- Use "Actions" → "View in Metrics Explorer" for advanced filtering

### Step 2: Create Metric Objects in CDK

#### Basic Metric Creation

In `diode_dashboard_stack.py`, add your new metric creation within the mapping loop:

```python
# Example: Adding ProcessingLatency metric
processing_latency = cloudwatch.Metric(
    namespace="AWS/Diode",                    # CloudWatch namespace
    dimensions_map={"MappingId": mapping_id}, # Dimension mapping
    metric_name="ProcessingLatency",          # Exact metric name from CloudWatch
    statistic="Average",                     # Aggregation method
    label=f"{friendly_name} - ProcessingLatency"  # Display label
)
```

#### Metric Configuration Parameters Explained

- **namespace**: The CloudWatch namespace where the metric exists
- **dimensions_map**: Dictionary mapping dimension names to values
- **metric_name**: Exact metric name as it appears in CloudWatch
- **statistic**: How to aggregate data points (`Sum`, `Average`, `Maximum`, `Minimum`, `SampleCount`)
- **label**: Human-readable label displayed in dashboard legends

#### Choosing the Right Statistic

| Metric Type | Recommended Statistic | Use Case |
|-------------|----------------------|----------|
| Count metrics (events) | `Sum` | Total number of occurrences |
| Size metrics (bytes) | `Sum` | Total data volume |
| Latency metrics (time) | `Average` | Typical response time |
| Utilization metrics (%) | `Average` | Resource usage levels |
| Error rates | `Sum` | Total error count |

### Step 3: Add Metrics to Collections

After creating individual metrics, add them to the appropriate collections for widget creation:

```python
# Find the existing metric collections in the code
all_transfer_created_count.append(transfer_created_count)
all_succeeded_transfer_count.append(succeeded_transfer_count)
# ... existing metrics ...

# Add your new metric to a new collection
all_processing_latency.append(processing_latency)
```

**Complete Example:**
```python
# Initialize collections at the beginning of the loop
all_processing_latency = []

# Inside the mapping loop, after existing metric creation:
for friendly_name, mapping_id in friendly_to_mapping_id.items():
    # ... existing metric creation code ...
    
    # Create new metric
    processing_latency = cloudwatch.Metric(
        namespace="AWS/Diode",
        dimensions_map={"MappingId": mapping_id},
        metric_name="ProcessingLatency",
        statistic="Average",
        label=f"{friendly_name} - ProcessingLatency"
    )
    
    # Add to collection
    all_processing_latency.append(processing_latency)
```

### Step 4: Create Widgets

#### Graph Widget for Time-Series Data

Add a new graph widget to display your metric over time:

```python
# Add after existing widget creation
dashboard.add_widgets(
    cloudwatch.GraphWidget(
        title=f"{mission_area} Processing Latency: Last 14 Days",
        left=all_processing_latency,           # Metrics to display
        width=12,                             # Widget width (12 = half dashboard)
        period=Duration.hours(1),             # Data aggregation period
        start='-P14D'                         # Time range (14 days ago)
    )
)
```

#### Single Value Widget for Summary Data

Add a single value widget for high-level metrics:

```python
# Add individual single value widgets for each mapping
for i, (friendly_name, mapping_id) in enumerate(friendly_to_mapping_id.items()):
    dashboard.add_widgets(
        cloudwatch.SingleValueWidget(
            metrics=[all_processing_latency[i]],
            title=f"{friendly_name} Avg Latency - Last 24 Hours",
            width=6,                          # Smaller width for summary widgets
            period=Duration.days(1)           # Aggregation period
        )
    )
```

#### Widget Configuration Options

**Graph Widget Parameters:**
- **title**: Descriptive title for the widget
- **left**: List of metrics for left Y-axis
- **right**: List of metrics for right Y-axis (optional)
- **width**: Widget width (6, 12, 18, or 24 units)
- **height**: Widget height (default: 6 units)
- **period**: Data aggregation interval
- **start**: Relative start time (ISO 8601 duration format)
- **end**: Relative end time (optional)
- **region**: AWS region (defaults to current region)

**Time Range Examples:**
- `-PT1H`: Last 1 hour
- `-P1D`: Last 1 day  
- `-P7D`: Last 7 days
- `-P1M`: Last 1 month
- `-P1Y`: Last 1 year

### Step 5: Widget Placement Strategy

#### Dashboard Layout Planning

CloudWatch dashboards use a 24-unit width grid system:

```
┌─────────────────────────────────────────────────────────────┐
│  Widget (width=24)                                          │
├──────────────────────────┬──────────────────────────────────┤
│  Widget (width=12)       │  Widget (width=12)               │
├─────────────┬────────────┼─────────────┬────────────────────┤
│Widget (w=6) │Widget (w=6)│Widget (w=6) │Widget (w=6)        │
└─────────────┴────────────┴─────────────┴────────────────────┘
```

#### Recommended Widget Placement

1. **Full-width widgets (24 units)**: Important overview metrics
2. **Half-width widgets (12 units)**: Detailed time-series analysis
3. **Quarter-width widgets (6 units)**: Summary statistics and KPIs

#### Adding Widgets in Logical Groups

```python
# Group 1: Overview widgets (full width)
dashboard.add_widgets(
    cloudwatch.GraphWidget(
        title=f"{mission_area} System Overview",
        left=all_transfer_created_count + all_processing_latency,
        width=24,
        period=Duration.days(1),
        start='-P30D'
    )
)

# Group 2: Detailed analysis (half width)
dashboard.add_widgets(
    cloudwatch.GraphWidget(
        title=f"{mission_area} Transfer Activity",
        left=all_transfer_created_count,
        width=12,
        period=Duration.hours(1),
        start='-P7D'
    ),
    cloudwatch.GraphWidget(
        title=f"{mission_area} Processing Performance",
        left=all_processing_latency,
        width=12,
        period=Duration.hours(1),
        start='-P7D'
    )
)
```

### Step 6: Testing and Validation

#### Validate Metric Availability

Before deploying, verify your metrics exist and have data:

```bash
# Test metric data retrieval
aws cloudwatch get-metric-statistics \
  --namespace AWS/Diode \
  --metric-name ProcessingLatency \
  --dimensions Name=MappingId,Value=your-mapping-id \
  --start-time $(date -d '1 day ago' -u +%Y-%m-%dT%H:%M:%SZ) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%SZ) \
  --period 3600 \
  --statistics Average
```

#### Deploy and Test

```bash
# Synthesize to check for errors
cdk synth

# Deploy changes
cdk deploy

# Verify dashboard creation
aws cloudwatch get-dashboard --dashboard-name YourDashboardName
```

### Step 7: Complete Example Implementation

Here's a complete example of adding a new `ProcessingLatency` metric:

```python
# In diode_dashboard_stack.py, within the mission area loop:

# 1. Initialize metric collection
all_processing_latency = []

# 2. Create metrics for each mapping
for friendly_name, mapping_id in friendly_to_mapping_id.items():
    # ... existing metric creation ...
    
    # Create new ProcessingLatency metric
    processing_latency = cloudwatch.Metric(
        namespace="AWS/Diode",
        dimensions_map={"MappingId": mapping_id},
        metric_name="ProcessingLatency",
        statistic="Average",
        label=f"{friendly_name} - ProcessingLatency"
    )
    
    # Add to collection
    all_processing_latency.append(processing_latency)

# 3. Create widgets after the loop
# Long-term trend widget
dashboard.add_widgets(
    cloudwatch.GraphWidget(
        title=f"{mission_area} Processing Latency: Last 30 Days",
        left=all_processing_latency,
        width=12,
        period=Duration.days(1),
        start='-P30D'
    )
)

# Real-time monitoring widget
dashboard.add_widgets(
    cloudwatch.GraphWidget(
        title=f"{mission_area} Processing Latency: Last 24 Hours",
        left=all_processing_latency,
        width=12,
        period=Duration.minutes(5),
        start='-P1D'
    )
)

# Summary widgets for each mapping
for i, (friendly_name, mapping_id) in enumerate(friendly_to_mapping_id.items()):
    dashboard.add_widgets(
        cloudwatch.SingleValueWidget(
            metrics=[all_processing_latency[i]],
            title=f"{friendly_name} Avg Latency - 24h",
            width=6,
            period=Duration.days(1)
        )
    )
```

### Best Practices for Adding Metrics

#### 1. Metric Naming and Organization
- Use descriptive, consistent naming for metric variables
- Group related metrics together in collections
- Follow existing naming patterns in the codebase

#### 2. Widget Design
- Place most important metrics in prominent positions
- Use appropriate time ranges for different use cases
- Group related widgets visually
- Maintain consistent widget sizing within groups

#### 3. Performance Considerations
- Limit the number of metrics per widget (recommended: 5-10 max)
- Use appropriate aggregation periods for time ranges
- Consider dashboard loading performance with many widgets

#### 4. Documentation
- Document new metrics in code comments
- Update this README with new metric descriptions
- Maintain mapping documentation for operational teams

### Troubleshooting New Metrics

#### Common Issues

**1. Metric Not Found**
```bash
# Verify metric exists
aws cloudwatch list-metrics --namespace AWS/Diode --metric-name YourMetricName
```

**2. No Data Displayed**
```bash
# Check if metric has recent data
aws cloudwatch get-metric-statistics \
  --namespace AWS/Diode \
  --metric-name YourMetricName \
  --dimensions Name=MappingId,Value=your-mapping-id \
  --start-time $(date -d '1 hour ago' -u +%Y-%m-%dT%H:%M:%SZ) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%SZ) \
  --period 300 \
  --statistics Average
```

**3. Wrong Statistic Type**
- Count metrics: Use `Sum`
- Latency metrics: Use `Average`
- Size metrics: Use `Sum` for totals, `Average` for rates

**4. Dimension Mismatch**
- Verify dimension names and values match exactly
- Check for case sensitivity
- Ensure mapping IDs are correct

## Advanced Features

### Dashboard Chunking

The application automatically implements dashboard chunking to prevent overcrowding:

#### Algorithm Details
```python
list_size = 5  # Maximum mappings per dashboard
mapping_chunks = []
current_chunk = {}
count = 0

for friendly_name, mapping_id in friendly_to_mapping_id.items():
    if count >= list_size:
        mapping_chunks.append(current_chunk)
        current_chunk = {}
        count = 0
    
    current_chunk[friendly_name] = mapping_id
    count += 1
```

#### Benefits
- **Performance**: Faster dashboard loading
- **Usability**: Better visual organization
- **Scalability**: Supports unlimited mappings per mission area
- **Maintenance**: Easier to manage individual dashboards

### SSM Parameter Storage

The application stores complete dashboard mappings in SSM Parameter Store:

#### Storage Format
```json
[
  {
    "MissionArea1-Dashboard": {
      "FriendlyName1": "mapping-id-1",
      "FriendlyName2": "mapping-id-2"
    }
  },
  {
    "MissionArea1-Dashboard-2": {
      "FriendlyName3": "mapping-id-3",
      "FriendlyName4": "mapping-id-4"
    }
  }
]
```

#### Use Cases
- **Documentation**: Reference for dashboard contents
- **Automation**: Input for other monitoring tools
- **Auditing**: Track dashboard configurations
- **Integration**: API access to dashboard mappings

### Custom Synthesizer Configuration

The application uses a custom synthesizer for enterprise deployments:

#### Features
- **Cross-Account Support**: Deploy to different AWS accounts
- **Custom Qualifier**: Avoid conflicts with other CDK applications
- **Role Customization**: Use specific IAM roles for deployment
- **Asset Management**: Custom asset publishing configuration

#### Configuration Benefits
- **Security**: Fine-grained permission control
- **Isolation**: Separate deployment environments
- **Compliance**: Meet enterprise security requirements
- **Scalability**: Support multiple deployment targets

## Testing

### Unit Testing

The application includes unit tests in the `tests/unit/` directory:

#### Running Tests
```bash
# Activate virtual environment
source .venv/bin/activate  # macOS/Linux
.venv\Scripts\activate     # Windows

# Run tests
pytest tests/

# Run with coverage
pytest --cov=diode_dashboard tests/

# Run specific test
pytest tests/unit/test_diode_dashboard_stack.py
```

#### Test Structure
```python
import aws_cdk as core
import aws_cdk.assertions as assertions
from diode_dashboard.diode_dashboard_stack import DiodeDashboardStack

def test_dashboard_creation():
    app = core.App()
    stack = DiodeDashboardStack(app, "test-stack")
    template = assertions.Template.from_stack(stack)
    
    # Test CloudWatch dashboard creation
    template.has_resource_properties("AWS::CloudWatch::Dashboard", {
        "DashboardName": assertions.Match.string_like_regexp(".*-Dashboard")
    })
```

### Integration Testing

#### Manual Testing Steps
1. Deploy to test environment
2. Verify dashboard creation in CloudWatch console
3. Check metric data display
4. Validate SSM parameter creation
5. Test dashboard functionality

#### Automated Testing
```bash
# Synthesize and validate templates
cdk synth --strict

# Run CDK validation
cdk doctor

# Validate CloudFormation templates
aws cloudformation validate-template --template-body file://cdk.out/DiodeDashboardStack.template.json
```

## Troubleshooting

### Common Issues and Solutions

#### 1. Missing Metrics Data

**Symptoms**: Dashboards show "No data available"

**Causes**:
- Incorrect mapping IDs in configuration
- DIODE system not publishing metrics
- Wrong AWS region or account

**Solutions**:
```bash
# Verify mapping IDs
aws cloudwatch list-metrics --namespace AWS/Diode

# Check metric dimensions
aws cloudwatch list-metrics --namespace AWS/Diode --metric-name TransferCreatedCount

# Verify region configuration
echo $AWS_DEFAULT_REGION
```

#### 2. Deployment Failures

**Symptoms**: CDK deploy fails with permission errors

**Causes**:
- Insufficient IAM permissions
- CDK not bootstrapped
- Resource limits exceeded

**Solutions**:
```bash
# Check CDK bootstrap status
cdk bootstrap --show-template

# Verify permissions
aws sts get-caller-identity
aws iam get-user

# Check CloudFormation limits
aws cloudformation describe-account-attributes
```

#### 3. Dashboard Limit Exceeded

**Symptoms**: Error creating additional dashboards

**Causes**:
- AWS CloudWatch dashboard limit reached (500 per account)

**Solutions**:
- Delete unused dashboards
- Implement dashboard rotation
- Use multiple AWS accounts
- Contact AWS support for limit increase

#### 4. Context Parameter Issues

**Symptoms**: Configuration not loaded correctly

**Causes**:
- Malformed JSON in cdk.json
- Missing context parameters
- Incorrect parameter names

**Solutions**:
```bash
# Validate JSON syntax
python -m json.tool cdk.json

# Check context loading
cdk context --list

# Clear context cache
cdk context --clear
```

### Emergency Procedures

#### Dashboard Recovery

If dashboards are accidentally deleted or corrupted:

```bash
# Quick recovery - redeploy from last known good configuration
git checkout last-known-good-commit
cdk deploy --require-approval never

# Verify recovery
aws cloudwatch list-dashboards
```

#### Rollback Procedures

```bash
# Cancel in-progress CloudFormation update
aws cloudformation cancel-update-stack --stack-name DiodeDashboardStack

# Force rollback if stack is in UPDATE_ROLLBACK_FAILED state
aws cloudformation continue-update-rollback --stack-name DiodeDashboardStack

# Complete rollback to previous working version
aws cloudformation update-stack \
  --stack-name DiodeDashboardStack \
  --template-body file://previous-working-template.json
```

#### Contact Information

For critical issues requiring immediate attention:
- **Operational Issues**: Refer to organizational Incident Response Procedures
- **Technical Issues**: Contact the development team through established channels
- **AWS Support**: Open support case for AWS service-related issues

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

#### 2. CloudFormation Events
```bash
# Monitor CloudFormation events
aws cloudformation describe-stack-events --stack-name DiodeDashboardStack

# Get stack status
aws cloudformation describe-stacks --stack-name DiodeDashboardStack
```

#### 3. Resource Inspection
```bash
# List created dashboards
aws cloudwatch list-dashboards

# Get dashboard definition
aws cloudwatch get-dashboard --dashboard-name YourDashboardName

# Check SSM parameter
aws ssm get-parameter --name "/diode/dashboards/complete-mappings"
```

#### 5. Widget Display Issues

**Symptoms**: Widgets show "Invalid metric" or "Metric not found"

**Causes**:
- Metric name typos in code
- Incorrect dimension values
- Metrics not published yet
- Wrong namespace specification

**Solutions**:
```bash
# Verify exact metric names
aws cloudwatch list-metrics --namespace AWS/Diode --query 'Metrics[].MetricName' --output table

# Check specific metric with dimensions
aws cloudwatch list-metrics --namespace AWS/Diode --metric-name TransferCreatedCount --query 'Metrics[].Dimensions'

# Test metric data availability
aws cloudwatch get-metric-statistics \
  --namespace AWS/Diode \
  --metric-name TransferCreatedCount \
  --dimensions Name=MappingId,Value=your-mapping-id \
  --start-time $(date -d '24 hours ago' -u +%Y-%m-%dT%H:%M:%SZ) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%SZ) \
  --period 3600 \
  --statistics Sum
```

#### 6. Dashboard Loading Performance Issues

**Symptoms**: Dashboards load slowly or timeout

**Causes**:
- Too many widgets on single dashboard
- Long time ranges with high-resolution data
- Network connectivity issues
- CloudWatch API throttling

**Solutions**:
```bash
# Check dashboard size
aws cloudwatch get-dashboard --dashboard-name YourDashboardName --query 'length(DashboardBody)'

# Monitor CloudWatch API usage
aws logs describe-metric-filters --log-group-name CloudTrail

# Test individual widget performance
aws cloudwatch get-metric-widget-image \
  --metric-widget '{"metrics":[["AWS/Diode","TransferCreatedCount","MappingId","your-mapping-id"]],"period":300,"stat":"Sum","region":"us-east-1","title":"Test Widget"}' \
  --output-format png
```

**Performance Optimization**:
- Reduce number of metrics per widget (max 10 recommended)
- Use appropriate time periods (avoid 1-minute periods for long ranges)
- Split large dashboards into multiple smaller ones
- Consider using metric math for complex calculations

#### 7. SSM Parameter Issues

**Symptoms**: SSM parameter not created or contains incorrect data

**Causes**:
- Insufficient SSM permissions
- Parameter name conflicts
- JSON serialization errors

**Solutions**:
```bash
# Check SSM permissions
aws iam simulate-principal-policy \
  --policy-source-arn $(aws sts get-caller-identity --query Arn --output text) \
  --action-names ssm:PutParameter ssm:GetParameter \
  --resource-arns "arn:aws:ssm:*:*:parameter/diode/dashboards/*"

# List all DIODE-related parameters
aws ssm get-parameters-by-path --path "/diode/dashboards" --recursive

# Validate parameter JSON content
aws ssm get-parameter --name "/diode/dashboards/complete-mappings" --query 'Parameter.Value' --output text | python -m json.tool
```

#### 8. Cross-Account Deployment Issues

**Symptoms**: Deployment fails in target account

**Causes**:
- CDK not bootstrapped in target account
- Cross-account role trust issues
- Different region configurations

**Solutions**:
```bash
# Verify bootstrap in target account
aws cloudformation describe-stacks --stack-name CDKToolkit --region target-region --profile target-account-profile

# Check cross-account role assumptions
aws sts assume-role \
  --role-arn "arn:aws:iam::TARGET-ACCOUNT:role/cdk-hnb659fds-deploy-role-TARGET-ACCOUNT-REGION" \
  --role-session-name "test-session"

# Verify region consistency
echo "Source region: $CDK_DEFAULT_REGION"
echo "Target region: $(aws configure get region --profile target-account-profile)"
```

#### 9. Mission Area Configuration Errors

**Symptoms**: Some mission areas missing from dashboards

**Causes**:
- JSON syntax errors in cdk.json
- Missing or empty mapping configurations
- Case sensitivity issues

**Solutions**:
```bash
# Validate cdk.json structure
python -c "import json; print(json.load(open('cdk.json'))['context']['mapping_ids'])"

# Check for empty configurations
python -c "
import json
with open('cdk.json') as f:
    data = json.load(f)
    for mission, mappings in data['context']['mapping_ids'].items():
        if not mappings:
            print(f'Empty mappings for mission area: {mission}')
        for friendly, mapping_id in mappings.items():
            if not mapping_id:
                print(f'Empty mapping ID for {mission}/{friendly}')
"

# Test context parameter loading
cdk synth --quiet | grep -A 20 "mapping_ids"
```

#### 10. CloudFormation Stack Issues

**Symptoms**: Stack creation or update fails

**Causes**:
- Resource naming conflicts
- CloudFormation template size limits
- Circular dependencies

**Solutions**:
```bash
# Check stack events for detailed error messages
aws cloudformation describe-stack-events --stack-name DiodeDashboardStack --query 'StackEvents[?ResourceStatus==`CREATE_FAILED` || ResourceStatus==`UPDATE_FAILED`]'

# Validate CloudFormation template
aws cloudformation validate-template --template-body file://cdk.out/DiodeDashboardStack.template.json

# Check template size
ls -lh cdk.out/DiodeDashboardStack.template.json

# Identify resource naming conflicts
aws cloudwatch list-dashboards --query 'DashboardEntries[?contains(DashboardName, `YourMissionArea`)]'
```

### Advanced Troubleshooting

#### Metric Data Validation Script

Create a validation script to test all configured metrics:

```python
#!/usr/bin/env python3
import json
import boto3
from datetime import datetime, timedelta

def validate_metrics():
    # Load configuration
    with open('cdk.json') as f:
        config = json.load(f)
    
    cloudwatch = boto3.client('cloudwatch')
    
    # Test each mapping
    for mission_area, mappings in config['context']['mapping_ids'].items():
        print(f"\nValidating {mission_area}:")
        
        for friendly_name, mapping_id in mappings.items():
            print(f"  Testing {friendly_name} ({mapping_id})...")
            
            # Test TransferCreatedCount metric
            try:
                response = cloudwatch.get_metric_statistics(
                    Namespace='AWS/Diode',
                    MetricName='TransferCreatedCount',
                    Dimensions=[{'Name': 'MappingId', 'Value': mapping_id}],
                    StartTime=datetime.utcnow() - timedelta(days=1),
                    EndTime=datetime.utcnow(),
                    Period=3600,
                    Statistics=['Sum']
                )
                
                if response['Datapoints']:
                    print(f"    ✓ Data available ({len(response['Datapoints'])} points)")
                else:
                    print(f"    ⚠ No data points found")
                    
            except Exception as e:
                print(f"    ✗ Error: {e}")

if __name__ == '__main__':
    validate_metrics()
```

#### Dashboard Health Check Script

```bash
#!/bin/bash
# dashboard-health-check.sh

echo "DIODE Dashboard Health Check"
echo "============================"

# Check CloudFormation stack status
echo "1. CloudFormation Stack Status:"
aws cloudformation describe-stacks --stack-name DiodeDashboardStack --query 'Stacks[0].StackStatus' --output text

# List created dashboards
echo -e "\n2. Created Dashboards:"
aws cloudwatch list-dashboards --query 'DashboardEntries[?contains(DashboardName, `Dashboard`)].DashboardName' --output table

# Check SSM parameter
echo -e "\n3. SSM Parameter Status:"
if aws ssm get-parameter --name "/diode/dashboards/complete-mappings" >/dev/null 2>&1; then
    echo "✓ SSM parameter exists"
else
    echo "✗ SSM parameter missing"
fi

# Test metric availability
echo -e "\n4. Sample Metric Test:"
if aws cloudwatch list-metrics --namespace AWS/Diode --metric-name TransferCreatedCount --query 'Metrics[0]' >/dev/null 2>&1; then
    echo "✓ DIODE metrics available"
else
    echo "✗ No DIODE metrics found"
fi

echo -e "\nHealth check complete."
```

#### Log Analysis for Common Errors

```bash
# Search CloudTrail logs for dashboard-related errors
aws logs filter-log-events \
  --log-group-name CloudTrail \
  --filter-pattern "{ $.eventName = PutDashboard && $.errorCode exists }" \
  --start-time $(date -d '1 day ago' +%s)000

# Search for CDK deployment errors
aws logs filter-log-events \
  --log-group-name "/aws/codebuild/cdk-deploy" \
  --filter-pattern "ERROR" \
  --start-time $(date -d '1 day ago' +%s)000
```

## Security Considerations

### Access Control

#### Dashboard Access
- Configure IAM policies to restrict dashboard access
- Use AWS Organizations for centralized access control
- Implement resource-based policies where applicable

#### Metric Data Security
- Dashboards display aggregated metrics only
- No access to underlying raw data
- CloudWatch metrics are encrypted at rest

#### Deployment Security
- Use least-privilege IAM roles for deployment
- Enable CloudTrail for deployment auditing
- Implement approval workflows for production deployments

### Best Practices

1. **Principle of Least Privilege**: Grant minimum required permissions
2. **Regular Access Reviews**: Periodically review dashboard access
3. **Encryption**: Ensure all data is encrypted in transit and at rest
4. **Monitoring**: Monitor dashboard access and usage
5. **Compliance**: Ensure compliance with organizational security policies

## Performance Considerations

### Dashboard Performance

#### Widget Optimization
- Limit widgets per dashboard (current: ~15 widgets)
- Use appropriate time ranges for different use cases
- Optimize metric queries for faster loading

#### Metric Aggregation
- Use appropriate statistics (Sum, Average) based on metric type
- Choose optimal time periods for different views
- Consider metric math for complex calculations

### Scalability Considerations

#### Dashboard Limits
- AWS CloudWatch: 500 dashboards per account
- Dashboard size: 100KB maximum
- Widgets per dashboard: No hard limit, but performance degrades

#### Metric Limits
- CloudWatch metrics: 10 million metrics per account
- API rate limits: 400 requests per second
- Data retention: 15 months for detailed metrics

## Maintenance and Updates

### Regular Maintenance Tasks

#### 1. Configuration Updates
- Review and update mapping IDs quarterly
- Add new mission areas as needed
- Remove obsolete mappings

#### 2. Dependency Updates
```bash
# Check for CDK updates
npm outdated -g aws-cdk

# Update CDK CLI
npm update -g aws-cdk

# Update Python dependencies
pip list --outdated
pip install --upgrade aws-cdk-lib
```

#### 3. Performance Monitoring
- Monitor dashboard loading times
- Review CloudWatch API usage
- Optimize slow-loading widgets

#### 4. Cost Optimization
- Review CloudWatch costs
- Optimize metric retention periods
- Consider dashboard consolidation

### Update Procedures

#### 1. Configuration Changes
```bash
# Update cdk.json with new mappings
vim cdk.json

# Test changes
cdk diff

# Deploy updates
cdk deploy
```

#### 2. Code Updates
```bash
# Update stack implementation
vim diode_dashboard/diode_dashboard_stack.py

# Run tests
pytest tests/

# Deploy changes
cdk deploy
```

#### 3. Rollback Procedures
```bash
# Rollback to previous version
aws cloudformation cancel-update-stack --stack-name DiodeDashboardStack

# Or deploy previous configuration
git checkout previous-commit
cdk deploy
```

---

## Conclusion

The DIODE Dashboard Application provides a comprehensive, scalable, and maintainable solution for monitoring DIODE transfer activities. By leveraging AWS CDK and CloudWatch, it offers a robust infrastructure-as-code approach to dashboard management while providing rich visualization capabilities for operational monitoring.

For additional support or questions, please refer to the AWS CDK documentation or contact the development team.