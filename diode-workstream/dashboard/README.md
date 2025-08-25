# DIODE Dashboard Monitoring Suite

## Quick Start

**Choose your monitoring focus:**
- **DIODE Transfer Monitoring** → [diode-dashboard/README.md](./diode-dashboard/README.md)
- **Pipeline Infrastructure Monitoring** → [pipeline-dashboard/README.md](./pipeline-dashboard/README.md)

## Table of Contents
1. [Overview](#overview)
2. [Dashboard Selection Guide](#dashboard-selection-guide)
3. [Operational Procedures](#operational-procedures)
4. [Project Architecture](#project-architecture)
5. [Stack Overviews](#stack-overviews)
6. [Detailed Documentation](#detailed-documentation)
7. [CDK Overview](#cdk-overview)

## Overview

The DIODE Dashboard Monitoring Suite is a comprehensive AWS CDK-based solution that provides monitoring and visualization capabilities for the DIODE (Data Input/Output Diode Environment) system. This suite consists of two primary monitoring stacks deployed through a unified CDK application:

1. **DIODE Dashboard Stack**: Monitors DIODE transfer activities across mission areas
2. **Pipeline Dashboard Stack**: Monitors the validation pipeline infrastructure components

The application leverages AWS CDK (Cloud Development Kit) to provide infrastructure-as-code capabilities, enabling consistent, repeatable, and version-controlled deployments of monitoring infrastructure.

## Dashboard Selection Guide

### Decision Matrix

| **Criteria** | **DIODE Dashboard** | **Pipeline Dashboard** |
|--------------|-------------------|----------------------|
| **Primary Focus** | Mission area transfer monitoring | Infrastructure health monitoring |
| **Target Users** | Mission operators, data analysts | DevOps, infrastructure teams |
| **Metrics Source** | Custom CloudWatch metrics | AWS service metrics (SQS, Lambda, EC2) |
| **Time Granularity** | Real-time to 30-day views | 6-month historical with daily aggregation |
| **Dashboard Count** | Multiple (per mission area) | Single comprehensive dashboard |
| **Use When** | Monitoring data transfers by mission | Monitoring pipeline infrastructure health |
| **Key Widgets** | Transfer counts, sizes, success rates | Queue metrics, Lambda performance, network |
| **Configuration** | Mission area mapping IDs | Queue names, Lambda functions, ASG names |
| **Deployment Account** | Mission area accounts | Infrastructure/monitoring account |

## Operational Procedures

### Incident Response

For operational incidents, alerts, and escalation procedures, refer to your organizational Incident Response Procedures and contact the appropriate on-call teams.

### Dashboard Health Monitoring

Both dashboard applications include built-in health monitoring. If dashboards are not displaying current data or showing errors, follow standard troubleshooting procedures documented in each application's README.

## Project Architecture

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        DIODE Dashboard Monitoring Suite                     │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────────┐                    ┌─────────────────┐                │
│  │   CDK App       │                    │   CDK App       │                │
│  │   (app.py)      │                    │   (app.py)      │                │
│  └─────────────────┘                    └─────────────────┘                │
│           │                                       │                        │
│           ▼                                       ▼                        │
│  ┌─────────────────┐                    ┌─────────────────┐                │
│  │ DashboardStack  │                    │PipelineStack    │                │
│  │ (Mission Areas) │                    │(Infrastructure) │                │
│  └─────────────────┘                    └─────────────────┘                │
│           │                                       │                        │
│           ▼                                       ▼                        │
│  ┌─────────────────┐                    ┌─────────────────┐                │
│  │  CloudWatch     │                    │  CloudWatch     │                │
│  │  Dashboards     │                    │  Dashboard      │                │
│  │  (Multiple)     │                    │  (Single)       │                │
│  └─────────────────┘                    └─────────────────┘                │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Directory Structure

```
dashboard/
├── diode-dashboard/                    # Standalone DIODE dashboard app
│   ├── diode_dashboard/
│   │   ├── __init__.py
│   │   └── diode_dashboard_stack.py    # DIODE transfer monitoring
│   ├── tests/
│   │   └── unit/
│   ├── app.py                          # CDK application entry point
│   ├── cdk.json                        # CDK configuration
│   ├── requirements.txt                # Python dependencies
│   └── README.md                       # DIODE dashboard documentation
├── pipeline-dashboard/                 # Standalone pipeline dashboard app
│   ├── pipeline_dashboard/
│   │   ├── __init__.py
│   │   └── pipeline_dashboard_stack.py # Pipeline infrastructure monitoring
│   ├── tests/
│   │   └── unit/
│   ├── app.py                          # CDK application entry point
│   ├── cdk.json                        # CDK configuration
│   ├── requirements.txt                # Python dependencies
│   └── README.md                       # Pipeline dashboard documentation
└── README.md                          # This documentation
```

## AWS CDK Deep Dive

### What is AWS CDK?

AWS CDK (Cloud Development Kit) is an open-source software development framework for defining cloud infrastructure using familiar programming languages. CDK applications are composed of constructs, which are cloud components that encapsulate everything AWS CloudFormation needs to create the component.

### CDK Core Concepts

#### 1. Constructs
Constructs are the basic building blocks of CDK applications. They represent cloud resources and can be composed together to create higher-level abstractions.

**Construct Levels:**
- **L1 Constructs (CFN Resources)**: Direct representations of CloudFormation resources
- **L2 Constructs (AWS Constructs)**: Higher-level abstractions with sensible defaults
- **L3 Constructs (Patterns)**: Opinionated patterns combining multiple resources

#### 2. Stacks
Stacks are the unit of deployment in CDK. Each stack corresponds to a CloudFormation stack and contains a collection of constructs.

#### 3. Apps
Apps are the root of the construct tree and contain one or more stacks.



Both applications use AWS CDK for infrastructure-as-code deployment. Key CDK concepts:

- **Bootstrap**: One-time setup creating S3 bucket and IAM roles for CDK operations
- **Synthesis**: Converts Python CDK code into CloudFormation templates
- **Deployment**: Creates/updates CloudFormation stacks with monitoring resources

**Common CDK Commands:**
```bash
cdk bootstrap    # First-time environment setup
cdk synth       # Generate CloudFormation templates
cdk deploy      # Deploy infrastructure
cdk diff        # Show changes before deployment
cdk destroy     # Remove all resources
```

**For detailed CDK information, deployment procedures, and troubleshooting**, see the individual project READMEs linked above.jectedTransferCount

**Dashboard Types Created**:
- Transfer activity graphs (long-term, medium-term, real-time)
- Transfer size analysis
- In-transit monitoring
- Success/failure analysis
- Single value summary widgets

### Pipeline Dashboard Stack

**Purpose**: Monitors DIODE validation pipeline infrastructure components

**Key Features**:
- Single comprehensive dashboard (ValidationPipelineDashboard)
- SQS queue monitoring (messages, size, DLQ)
- Auto Scaling Group network monitoring
- Dynamic Lambda function monitoring
- 6-month historical view with daily aggregation

**Monitored Components**:
- **SQS Queue**: Message flow and processing rates
- **Dead Letter Queue**: Failed message tracking
- **Auto Scaling Group**: Network performance metrics
- **Lambda Functions**: Invocations, concurrency, errors

**Dashboard Widgets**:
- Queue messaging widget
- Queue message size widget
- Dead Letter Queue widget
- Auto Scaling Group network widget
- Individual Lambda function widgets (dynamically generated)

## CDK Application Structure

### DIODE Dashboard Application (diode-dashboard/app.py)

```python
#!/usr/bin/env python3
import os
import aws_cdk as cdk

from diode_dashboard.diode_dashboard_stack import DiodeDashboardStack

app = cdk.App()
DiodeDashboardStack(app, "DiodeDashboardStack",
    synthesizer = cdk.DefaultStackSynthesizer(
        qualifier='hnb659fds',
        cloud_formation_execution_role='arn:${AWS::Partition}:iam::${AWS::Region}:role/cdk-hnb659fds-cfn-exec-role-{AWS::AccountId}-${AWS::Region}',
        deploy_role_arn='arn:${AWS::Partition}:iam::${AWS::Region}:role/cdk-hnb659fds-deploy-role-{AWS::AccountId}-${AWS::Region}',
        file_asset_publishing_role_arn='arn:${AWS::Partition}:iam::${AWS::Region}:role/cdk-hnb659fds-file-pub-role-{AWS::AccountId}-${AWS::Region}',
        image_asset_publishing_role_arn='arn:${AWS::Partition}:iam::${AWS::Region}:role/cdk-hnb659fds-image-pub-role-{AWS::AccountId}-${AWS::Region}',
        lookup_role_arn='arn:${AWS::Partition}:iam::${AWS::Region}:role/cdk-hnb659fds-lookup-role-{AWS::AccountId}-${AWS::Region}'
    ),
    env=cdk.Environment(account=os.getenv('CDK_DEFAULT_ACCOUNT'), region=os.getenv('CDK_DEFAULT_REGION')),
)
app.synth()
```

### Pipeline Dashboard Application (pipeline-dashboard/app.py)

```python
#!/usr/bin/env python3
import os
import aws_cdk as cdk

from pipeline_dashboard.pipeline_dashboard_stack import PipelineDashboardStack

app = cdk.App()
PipelineDashboardStack(app, "PipelineDashboardStack",
    synthesizer = cdk.DefaultStackSynthesizer(
        qualifier='hnb659fds',
        cloud_formation_execution_role='arn:${AWS::Partition}:iam::${AWS::Region}:role/cdk-hnb659fds-cfn-exec-role-{AWS::AccountId}-${AWS::Region}',
        deploy_role_arn='arn:${AWS::Partition}:iam::${AWS::Region}:role/cdk-hnb659fds-deploy-role-{AWS::AccountId}-${AWS::Region}',
        file_asset_publishing_role_arn='arn:${AWS::Partition}:iam::${AWS::Region}:role/cdk-hnb659fds-file-pub-role-{AWS::AccountId}-${AWS::Region}',
        image_asset_publishing_role_arn='arn:${AWS::Partition}:iam::${AWS::Region}:role/cdk-hnb659fds-image-pub-role-{AWS::AccountId}-${AWS::Region}',
        lookup_role_arn='arn:${AWS::Partition}:iam::${AWS::Region}:role/cdk-hnb659fds-lookup-role-{AWS::AccountId}-${AWS::Region}'
    ),
    env=cdk.Environment(account=os.getenv('CDK_DEFAULT_ACCOUNT'), region=os.getenv('CDK_DEFAULT_REGION')),
)
app.synth()
```

### Stack Implementation Pattern

Both stacks follow a consistent implementation pattern:

1. **Context Parameter Retrieval**: Load configuration from `cdk.json`
2. **Resource Creation**: Create CloudWatch dashboards and metrics
3. **Widget Configuration**: Configure graph and single-value widgets
4. **Dynamic Generation**: Create widgets based on configuration

### CDK Construct Usage

The application primarily uses L2 constructs from the `aws-cloudwatch` module:

- `cloudwatch.Dashboard`: Creates CloudWatch dashboards
- `cloudwatch.Metric`: Defines CloudWatch metrics
- `cloudwatch.GraphWidget`: Creates time-series graph widgets
- `cloudwatch.SingleValueWidget`: Creates summary value widgets

## CDK Deployment Lifecycle

### Phase 1: Environment Preparation

```bash
# Set environment variables
export CDK_DEFAULT_ACCOUNT=123456789012
export CDK_DEFAULT_REGION=us-east-1

# Bootstrap environment (one-time)
cdk bootstrap
```

### Phase 2: Code Development and Testing

```bash
# Install dependencies
pip install -r requirements.txt

# Run unit tests
pytest tests/

# Validate code syntax
python -m py_compile app.py
```

### Phase 3: Synthesis

```bash
# Synthesize CloudFormation templates
cdk synth

# Synthesize specific stack
cdk synth DashboardStack

# Synthesize with strict mode
cdk synth --strict
```

**Synthesis Output Structure**:
```
cdk.out/
├── DashboardStack.template.json        # CloudFormation template
├── DashboardStack.assets.json          # Asset manifest
├── PipelineDashboardStack.template.json
├── PipelineDashboardStack.assets.json
├── manifest.json                       # Deployment manifest
├── tree.json                          # Construct tree
└── cdk.out                            # CDK metadata
```

### Phase 4: Deployment

```bash
# Deploy all stacks
cdk deploy --all

# Deploy specific stack
cdk deploy DashboardStack

# Deploy with approval
cdk deploy --require-approval broadening

# Deploy with parameters
cdk deploy --parameters key=value
```

### Phase 5: Monitoring and Maintenance

```bash
# Check deployment differences
cdk diff

# List deployed stacks
cdk list

# Destroy stacks (caution!)
cdk destroy --all
```

## CDK Configuration Management

### Context Configuration

CDK uses context values for configuration management. Context can be set in multiple ways:

#### 1. cdk.json File
```json
{
  "context": {
    "mapping_ids": {
      "MissionArea1": {
        "System1": "mapping-id-1"
      }
    },
    "av_scan_queue_name": "my-queue",
    "@aws-cdk/core:enableStackNameDuplicates": true
  }
}
```

#### 2. Command Line
```bash
cdk deploy --context key=value
```

#### 3. Environment Variables
```bash
export CDK_CONTEXT_key=value
```

#### 4. Programmatic Context
```python
app = cdk.App()
app.node.set_context("key", "value")
```

### Feature Flags

CDK feature flags control CDK behavior and enable new features:

#### Security Feature Flags
- `@aws-cdk/core:checkSecretUsage`: Prevents secret exposure
- `@aws-cdk/aws-iam:minimizePolicies`: Optimizes IAM policies
- `@aws-cdk/aws-ec2:restrictDefaultSecurityGroup`: Enhances security

#### Performance Feature Flags
- `@aws-cdk/aws-lambda-nodejs:useLatestRuntimeVersion`: Latest runtimes
- `@aws-cdk/aws-ec2:ebsDefaultGp3Volume`: GP3 volumes by default

#### Compatibility Feature Flags
- `@aws-cdk/core:target-partitions`: Multi-partition support
- `@aws-cdk/aws-ecs:arnFormatIncludesClusterName`: Modern ARN formats

### Environment Configuration

```python
# Explicit environment
env = cdk.Environment(account="123456789012", region="us-east-1")

# Environment from variables
env = cdk.Environment(
    account=os.getenv('CDK_DEFAULT_ACCOUNT'),
    region=os.getenv('CDK_DEFAULT_REGION')
)

# Environment-agnostic (not recommended for production)
env = None
```

## CDK Best Practices

### 1. Stack Organization

**Single Responsibility**: Each stack should have a single, well-defined purpose
```python
# Good: Separate stacks for different concerns
DashboardStack(app, "DashboardStack")
PipelineStack(app, "PipelineStack")

# Avoid: Monolithic stacks with mixed concerns
```

**Stack Naming**: Use descriptive, consistent naming conventions
```python
# Good: Descriptive names
DashboardStack(app, "DiodeDashboardStack")

# Avoid: Generic names
Stack(app, "MyStack")
```

### 2. Construct Usage

**Prefer L2 Constructs**: Use higher-level constructs when available
```python
# Good: L2 construct with sensible defaults
dashboard = cloudwatch.Dashboard(self, "Dashboard",
    dashboard_name="MyDashboard"
)

# Avoid: L1 construct requiring all properties
dashboard = cloudwatch.CfnDashboard(self, "Dashboard",
    dashboard_body=json.dumps({...})
)
```

### 3. Configuration Management

**Externalize Configuration**: Use context for environment-specific values
```python
# Good: Configuration from context
queue_name = self.node.try_get_context("queue_name")

# Avoid: Hard-coded values
queue_name = "my-hardcoded-queue"
```

### 4. Resource Naming

**Logical IDs**: Use descriptive logical IDs
```python
# Good: Descriptive logical ID
cloudwatch.Dashboard(self, "DiodeTransferDashboard")

# Avoid: Generic logical ID
cloudwatch.Dashboard(self, "Dashboard1")
```

### 5. Error Handling

**Validation**: Validate context parameters
```python
queue_name = self.node.try_get_context("queue_name")
if not queue_name:
    raise ValueError("queue_name context parameter is required")
```

### 6. Testing

**Unit Tests**: Test stack creation and resource properties
```python
def test_dashboard_created():
    app = cdk.App()
    stack = DashboardStack(app, "test")
    template = Template.from_stack(stack)
    
    template.has_resource_properties("AWS::CloudWatch::Dashboard", {
        "DashboardName": "MyDashboard"
    })
```

## Prerequisites

### System Requirements

1. **Python**: Version 3.8 or higher
2. **Node.js**: Version 14 or higher (for CDK CLI)
3. **AWS CLI**: Version 2.0 or higher
4. **CDK CLI**: Latest version

### AWS Requirements

1. **AWS Account**: Active account with appropriate permissions
2. **IAM Permissions**: CloudWatch, CloudFormation, IAM permissions
3. **AWS Credentials**: Configured via AWS CLI or environment variables

### Permission Requirements

```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "cloudformation:*",
                "cloudwatch:*",
                "ssm:PutParameter",
                "ssm:GetParameter",
                "iam:PassRole",
                "s3:GetObject",
                "s3:PutObject"
            ],
            "Resource": "*"
        }
    ]
}
```

## Installation and Setup

### Step 1: Install CDK CLI

```bash
# Install Node.js (if not already installed)
# Download from https://nodejs.org/

# Install CDK CLI globally
npm install -g aws-cdk

# Verify installation
cdk --version
```

### Step 2: Setup Python Environment

#### For DIODE Dashboard:
```bash
# Navigate to DIODE dashboard directory
cd diode-dashboard

# Create virtual environment
python -m venv .venv

# Activate virtual environment
# Windows:
.venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

#### For Pipeline Dashboard:
```bash
# Navigate to pipeline dashboard directory
cd pipeline-dashboard

# Create virtual environment
python -m venv .venv

# Activate virtual environment
# Windows:
.venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### Step 3: Configure AWS

```bash
# Configure AWS CLI
aws configure

# Or set environment variables
export AWS_ACCESS_KEY_ID=your-access-key
export AWS_SECRET_ACCESS_KEY=your-secret-key
export AWS_DEFAULT_REGION=your-region

# Set CDK environment variables
export CDK_DEFAULT_ACCOUNT=123456789012
export CDK_DEFAULT_REGION=us-east-1
```

## Deployment Instructions

### Step 1: Bootstrap CDK Environment

```bash
# Bootstrap current account/region
cdk bootstrap

# Bootstrap specific account/region
cdk bootstrap aws://123456789012/us-east-1

# Verify bootstrap
aws cloudformation describe-stacks --stack-name CDKToolkit
```

### Step 2: Configure Applications

#### Configure DIODE Dashboard (diode-dashboard/cdk.json):

```json
{
  "context": {
    "mapping_ids": {
      "YourMissionArea": {
        "YourSystem": "your-mapping-id"
      }
    }
  }
}
```

#### Configure Pipeline Dashboard (pipeline-dashboard/cdk.json):

```json
{
  "context": {
    "av_scan_queue_name": "your-queue-name",
    "av_scan_dlq_name": "your-dlq-name",
    "asg_name": "your-asg-name",
    "monitored_lambda_functions": ["your-function-1", "your-function-2"]
  }
}
```

### Step 3: Synthesize and Validate

#### For DIODE Dashboard:
```bash
cd diode-dashboard

# Synthesize CloudFormation templates
cdk synth

# Validate templates
aws cloudformation validate-template --template-body file://cdk.out/DiodeDashboardStack.template.json

# Check for differences (if updating)
cdk diff
```

#### For Pipeline Dashboard:
```bash
cd pipeline-dashboard

# Synthesize CloudFormation templates
cdk synth

# Validate templates
aws cloudformation validate-template --template-body file://cdk.out/PipelineDashboardStack.template.json

# Check for differences (if updating)
cdk diff
```

### Step 4: Deploy Stacks

#### Deploy DIODE Dashboard:
```bash
cd diode-dashboard

# Deploy DIODE dashboard stack
cdk deploy

# Deploy with approval prompts
cdk deploy --require-approval broadening
```

#### Deploy Pipeline Dashboard:
```bash
cd pipeline-dashboard

# Deploy pipeline dashboard stack
cdk deploy

# Deploy with approval prompts
cdk deploy --require-approval broadening
```

### Step 5: Verify Deployment

```bash
# List CloudWatch dashboards
aws cloudwatch list-dashboards

# Check DIODE dashboard stack status
aws cloudformation describe-stacks --stack-name DiodeDashboardStack

# Check pipeline dashboard stack status
aws cloudformation describe-stacks --stack-name PipelineDashboardStack

# View dashboards in AWS Console
# Navigate to CloudWatch > Dashboards
```

## CDK Commands Reference

### Core Commands

```bash
# Initialize new CDK project
cdk init app --language python

# List all stacks in app
cdk list

# Synthesize CloudFormation templates
cdk synth [STACK]

# Deploy stacks
cdk deploy [STACK] [OPTIONS]

# Compare deployed stack with current state
cdk diff [STACK]

# Destroy stacks
cdk destroy [STACK]
```

### Utility Commands

```bash
# Show CDK version
cdk --version

# Get help for command
cdk [COMMAND] --help

# Run CDK doctor (environment check)
cdk doctor

# Open CDK documentation
cdk docs

# Watch for changes and redeploy
cdk watch [STACK]
```

### Context Commands

```bash
# List context values
cdk context --list

# Clear context cache
cdk context --clear

# Reset specific context
cdk context --reset KEY
```

### Bootstrap Commands

```bash
# Bootstrap environment
cdk bootstrap [ENVIRONMENT]

# Show bootstrap template
cdk bootstrap --show-template

# Bootstrap with custom qualifier
cdk bootstrap --qualifier QUALIFIER

# Force bootstrap update
cdk bootstrap --force
```

### Advanced Commands

```bash
# Deploy with parameters
cdk deploy --parameters key1=value1 --parameters key2=value2

# Deploy with specific profile
cdk deploy --profile my-profile

# Deploy with role assumption
cdk deploy --role-arn arn:aws:iam::ACCOUNT:role/ROLE

# Deploy with approval settings
cdk deploy --require-approval never|any-change|broadening

# Deploy with notifications
cdk deploy --notification-arns arn:aws:sns:REGION:ACCOUNT:TOPIC
```

## Troubleshooting CDK Issues

### Common CDK Issues

#### 1. Bootstrap Issues

**Problem**: CDK not bootstrapped
```
Error: Need to perform AWS CDK bootstrap
```

**Solution**:
```bash
cdk bootstrap aws://ACCOUNT/REGION
```

#### 2. Permission Issues

**Problem**: Insufficient permissions
```
Error: User is not authorized to perform: cloudformation:CreateStack
```

**Solution**:
```bash
# Check current identity
aws sts get-caller-identity

# Verify permissions
aws iam simulate-principal-policy \
  --policy-source-arn $(aws sts get-caller-identity --query Arn --output text) \
  --action-names cloudformation:CreateStack \
  --resource-arns "*"
```

#### 3. Context Issues

**Problem**: Context values not loaded
```
Error: Context value 'mapping_ids' not found
```

**Solution**:
```bash
# Check context loading
cdk context --list

# Clear context cache
cdk context --clear

# Validate cdk.json syntax
python -m json.tool cdk.json
```

#### 4. Synthesis Issues

**Problem**: Synthesis fails
```
Error: Cannot read property 'node' of undefined
```

**Solution**:
```bash
# Check Python syntax
python -m py_compile app.py

# Run with debug
CDK_DEBUG=true cdk synth

# Check dependencies
pip check
```

### CDK Debugging Techniques

#### 1. Enable Debug Logging

```bash
# Enable CDK debug logging
export CDK_DEBUG=true
cdk deploy

# Enable verbose logging
cdk deploy --verbose

# Enable CloudFormation debug
export AWS_CDK_DEBUG=true
```

#### 2. Inspect Generated Templates

```bash
# Synthesize and inspect
cdk synth > template.json
cat template.json | jq .

# Compare templates
cdk diff --template template.json
```

#### 3. CloudFormation Events

```bash
# Monitor CloudFormation events
aws cloudformation describe-stack-events --stack-name STACK-NAME

# Get stack status
aws cloudformation describe-stacks --stack-name STACK-NAME
```

#### 4. Asset Debugging

```bash
# List assets
ls -la cdk.out/

# Check asset manifest
cat cdk.out/manifest.json | jq .

# Verify S3 assets
aws s3 ls s3://cdk-hnb659fds-assets-ACCOUNT-REGION/
```

## Advanced CDK Features

### Custom Synthesizers

For enterprise deployments, you can use custom synthesizers:

```python
synthesizer = cdk.DefaultStackSynthesizer(
    qualifier='myapp',
    cloud_formation_execution_role='arn:aws:iam::ACCOUNT:role/MyRole',
    deploy_role_arn='arn:aws:iam::ACCOUNT:role/MyDeployRole'
)

stack = MyStack(app, "MyStack", synthesizer=synthesizer)
```

### Aspects

Aspects allow you to apply operations to all constructs in a scope:

```python
class TaggingAspect:
    def visit(self, node):
        if hasattr(node, 'tags'):
            node.tags.set_tag('Project', 'DIODE')
            node.tags.set_tag('Environment', 'Production')

app = cdk.App()
stack = MyStack(app, "MyStack")
cdk.Aspects.of(stack).add(TaggingAspect())
```

### Custom Resources

For resources not supported by CloudFormation:

```python
custom_resource = cdk.CustomResource(
    self, "MyCustomResource",
    service_token=lambda_function.function_arn,
    properties={
        "Property1": "Value1"
    }
)
```

### Cross-Stack References

Share resources between stacks:

```python
# Producer stack
class ProducerStack(cdk.Stack):
    def __init__(self, scope, id, **kwargs):
        super().__init__(scope, id, **kwargs)
        
        self.shared_resource = s3.Bucket(self, "SharedBucket")

# Consumer stack
class ConsumerStack(cdk.Stack):
    def __init__(self, scope, id, producer_stack, **kwargs):
        super().__init__(scope, id, **kwargs)
        
        # Use resource from producer stack
        bucket = producer_stack.shared_resource
```

## Maintenance and Updates

### Regular Maintenance Tasks

#### 1. CDK Updates

```bash
# Check CDK version
cdk --version

# Update CDK CLI
npm update -g aws-cdk

# Update CDK libraries
pip install --upgrade aws-cdk-lib
```

#### 2. Dependency Updates

```bash
# Check outdated packages
pip list --outdated

# Update all packages
pip install --upgrade -r requirements.txt

# Update specific package
pip install --upgrade aws-cdk-lib
```

#### 3. Configuration Updates

```bash
# Update context in cdk.json
vim cdk.json

# Test configuration changes
cdk diff

# Deploy updates
cdk deploy
```

### Update Procedures

#### 1. CDK Version Updates

```bash
# Check current version
cdk --version

# Update CLI
npm update -g aws-cdk

# Update libraries
pip install --upgrade aws-cdk-lib constructs

# Test synthesis
cdk synth

# Deploy updates
cdk deploy
```

#### 2. Stack Updates

```bash
# Check for changes
cdk diff

# Deploy with approval
cdk deploy --require-approval broadening

# Monitor deployment
aws cloudformation describe-stack-events --stack-name STACK-NAME
```

#### 3. Rollback Procedures

```bash
# Cancel in-progress update
aws cloudformation cancel-update-stack --stack-name STACK-NAME

# Rollback to previous version
git checkout previous-commit
cdk deploy

# Or use CloudFormation rollback
aws cloudformation continue-update-rollback --stack-name STACK-NAME
```

---

## Conclusion

This DIODE Dashboard Monitoring Suite provides a comprehensive, CDK-based solution for monitoring DIODE transfer activities and pipeline infrastructure. By leveraging AWS CDK's infrastructure-as-code capabilities, the application ensures consistent, repeatable, and maintainable deployments while providing rich monitoring capabilities through CloudWatch dashboards.

The detailed CDK implementation enables teams to understand, modify, and extend the monitoring solution to meet evolving requirements while maintaining best practices for cloud infrastructure management.

For additional support or questions, please refer to the AWS CDK documentation or contact the development team.