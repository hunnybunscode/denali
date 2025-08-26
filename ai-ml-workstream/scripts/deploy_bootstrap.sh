#!/bin/bash

# Deploy AFC2S Bootstrap with v1 qualifier and permissions boundaries
# This will update the existing bootstrap to use proper permissions boundaries

echo "🚀 Deploying AFC2S Bootstrap with v1 qualifier..."
echo "================================================"

# Check AWS credentials
echo "👤 Current AWS Identity:"
aws sts get-caller-identity

echo ""
echo "📋 Bootstrap Parameters:"
cat bootstrap/bootstrap-parameters-projadmin.json

echo ""
echo "🚀 Deploying/Updating CDKToolkit stack..."

aws cloudformation deploy \
  --template-file bootstrap/custom-bootstrap-template.yaml \
  --stack-name CDKToolkit-v1 \
  --parameter-overrides file://bootstrap/bootstrap-parameters-projadmin.json \
  --capabilities CAPABILITY_NAMED_IAM \
  --region us-gov-west-1

if [ $? -eq 0 ]; then
    echo ""
    echo "🎉 Bootstrap deployment completed!"
    echo ""
    echo "🔍 Verifying AFC2S roles with v1 qualifier..."
    aws iam list-roles --query "Roles[?contains(RoleName, 'AFC2S-cdk-v1')].[RoleName,PermissionsBoundary.PermissionsBoundaryArn]" --output table
else
    echo "❌ Bootstrap deployment failed!"
    exit 1
fi