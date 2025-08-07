#!/bin/bash

# Script to configure EKS cluster access for Admin role
# Run this after CDK deployment to grant kubectl access

set -e

echo "=== Configuring EKS Cluster Access ==="

# Auto-detect AWS configuration
AWS_ACCOUNT=$(aws sts get-caller-identity --query Account --output text)
AWS_REGION=$(aws configure get region || echo "us-east-1")
CLUSTER_NAME="SharedServices"

echo "✅ AWS Account: $AWS_ACCOUNT"
echo "✅ AWS Region: $AWS_REGION"
echo "✅ Cluster: $CLUSTER_NAME"

# Update kubeconfig
echo "Updating kubeconfig..."
aws eks update-kubeconfig --region $AWS_REGION --name $CLUSTER_NAME

# Test if kubectl works
echo "Testing kubectl access..."
if kubectl get nodes > /dev/null 2>&1; then
    echo "✅ kubectl access working!"
    
    # Try to configure aws-auth ConfigMap
    echo "Configuring cluster access for Admin role..."
    kubectl apply -f - <<EOF
apiVersion: v1
kind: ConfigMap
metadata:
  name: aws-auth
  namespace: kube-system
data:
  mapRoles: |
    - rolearn: arn:aws:iam::${AWS_ACCOUNT}:role/Admin
      username: admin
      groups:
        - system:masters
EOF
    
    if [ $? -eq 0 ]; then
        echo "✅ Admin role access configured successfully!"
    else
        echo "⚠️  Failed to configure Admin role access, but kubectl is working"
    fi
else
    echo "❌ kubectl access not working."
    echo "Since you deployed the cluster, try running CDK with the same credentials:"
    echo ""
    echo "  # Re-run deployment to ensure access"
    echo "  ENVIRONMENT=dev-dynamic cdk deploy --all"
    echo ""
    echo "Or contact your team lead to manually add your role to the cluster."
fi

# Only show success if we actually configured something
echo "Script completed. Test kubectl access with: kubectl get nodes"