# CDK Bootstrap Project

This project helps you bootstrap AWS CDK resources in your AWS account.

## Overview

The AWS CDK Bootstrap process sets up the necessary resources in your AWS account to deploy CDK applications. This includes:

- An S3 bucket for storing deployment artifacts
- IAM roles for CDK deployment
- ECR repositories for container images (if needed)

## Prerequisites

- Bash Shell
- AWS CLI installed and configured
- Python 3 or later
- AWS CDK CLI installed (`npm install -g aws-cdk`)
- AWS account credentials configured
- Make

## Configuration
The configuration files are stored in `/env/<environment name>/coniguration.yaml`.
The environment name is set by exporting the variable **ENVIRONMENT**.
The default environment is `dev`

| Parameter                             | Description                                 | Example                                          | Required |
| ------------------------------------- | ------------------------------------------- | ------------------------------------------------ | -------- |
| environment.name                      | Name of the environment being bootstrapped  | standard-dev                                     | Yes      |
| environment.region                    | AWS region where resources will be deployed | us-west-1                                        | Yes      |
| environment.account                   | AWS account ID for deployment               | "908027385618"                                   | Yes      |
| environment.execute                   | Flag to control execution of bootstrap      | false                                            | No       |
| environment.iam.prefix                | Prefix for IAM resource names               | AFC2S                                            | No       |
| environment.iam.permissionBoundaryArn | ARN of IAM permission boundary policy       | arn:aws:iam::908027385618:policy/ProjAdminPolicy | No       |


Sample Configuration

```yaml
environment:
  name: standard-dev
  region: us-west-1
  account: "908027385618"
  execute: false
  iam:
    prefix: AFC2S
    permissionBoundaryArn: arn:aws:iam::908027385618:policy/ProjAdminPolicy
```

## Installation

1. Run the following to initialize the python project
    ```bash
    make init
    ```
2. Update the configuration 
3. Export the target `ENVIRONMENT` variable 
    ```bash
    export ENVIRONMENT=dev
    ```
4. Export the API Access Key to the target AWS account into the shell session
5. Run the `index.py` script with python
    ```bash
    python index.py
    ```
