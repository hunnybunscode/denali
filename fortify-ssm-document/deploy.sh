#!/bin/bash

set -e

STACK_NAME="fortify-scan-stack"
REGION="us-gov-west-1"
PARAMETERS_FILE="parameters.json"
TEMPLATE_FILE="fortify-scan-template.yaml"

echo "Deploying Fortify Scan CloudFormation stack..."

aws cloudformation deploy \
    --template-file $TEMPLATE_FILE \
    --stack-name $STACK_NAME \
    --parameter-overrides file://$PARAMETERS_FILE \
    --capabilities CAPABILITY_NAMED_IAM \
    --region $REGION

echo "Stack deployment completed!"

# Get outputs
echo "Getting stack outputs..."
aws cloudformation describe-stacks \
    --stack-name $STACK_NAME \
    --region $REGION \
    --query 'Stacks[0].Outputs'
