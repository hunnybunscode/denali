# Denali AI-ML Workstream
This repo contains the CDK application that defines the infrastructure for the AI-ML workstream of this project. This project implements an automated security vulnerability remediation system for software development, leveraging AWS Step Functions and Lambda functions to create a streamlined workflow. The system analyzes code using Fortify scans to detect security vulnerabilities, then utilizes AI, specifically a Large Language Model (LLM) through Amazon Bedrock, to automatically generate fixes for identified issues. It interacts with a version control system (Gitea) to manage code changes, including creating branches, committing fixes, and opening pull requests, while tracking the remediation process through issue management in the repository. Data about findings and fixes are stored and managed using DynamoDB. 

## Project Structure:
- stacks/: This directory contains all the Python CDK stacks defining the infrastructure
- app.py: The top-level script contain all the build logic for deploying the infrastructure defined in "stacks"
- config/: Contains configuration files and utilities
    - deployment_config.yaml: Main configuration file you need to modify
    - config.py: Configuration loading and processing
- stacks/: Contains the main stack definitions
    - stacks/step_functions_stack/: Contains Step Function definitions
    - stacks/step_functions_stack/lambdas/: Contains Lambda function code

## Deployment

### Create config file

To deploy, you need to pass in a configuration file. An example is provided at config/deployment_config.yaml. You need to update this file with your specific settings:
```
namespace: "your-name"  # Replace with your identifier
version: "v1"
region: "us-gov-west-1"  # Your AWS region
networking:
  vpc_id: "vpc-xxxxxx"               # Replace with your VPC ID
  subnets:
    - subnet_id: "subnet-xxxxxx"     # Replace with your subnet IDs
      availability_zone: "us-gov-west-1a"
    - subnet_id: "subnet-yyyyyy"
      availability_zone: "us-gov-west-1b"
  security_group_id: "sg-xxxxxx"     # Replace with your security group ID
```

### Deploy

The deployment expects a config file, defined above, to be provided via the context at deployment time as follows:
```
cdk synth --context config_file=path/to/config.yaml
cdk deploy --context config_file=path/to/config.yaml
```

### Security Considerations
- Resources are isolated through the namespace system
- Lambda functions are deployed in VPC for network isolation
- Security groups should be configured with minimum required access
- Ensure not to commit personal AWS resource IDs to version control

### dynamodb_table_scan lambda
- Path: ai-ml-workstream/stacks/step_functions_stack/lambdas/dynamodb_table_scan
- Uses a minSeverity payload value to filter the findings returned by severity.
  - A missing minSeverity value returns findings of any severity.
  - Setting the minSeverity value will turn on filtering so that the lambda only returns findings with that severity or higher. 
  - Example: a "4" minSeverity would only return findings with 4 and above severity (highs and criticals)