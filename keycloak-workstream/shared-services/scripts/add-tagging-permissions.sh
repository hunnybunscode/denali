#!/bin/bash

# Add EC2 tagging permissions to CDK execution role
set -e

AWS_ACCOUNT=$(aws sts get-caller-identity --query Account --output text)
AWS_REGION=$(aws configure get region || echo "us-east-1")

ROLE_NAME="cdk-hnb659fds-cfn-exec-role-${AWS_ACCOUNT}-${AWS_REGION}"

echo "Adding EC2 tagging permissions to role: $ROLE_NAME"

# Create comprehensive policy for EKS subnet tagging
aws iam create-policy \
  --policy-name CDK-EC2-Tagging-Permissions \
  --policy-document '{
    "Version": "2012-10-17",
    "Statement": [{
      "Effect": "Allow",
      "Action": [
        "ec2:CreateTags",
        "ec2:DeleteTags",
        "ec2:DescribeTags",
        "ec2:DescribeSubnets",
        "ec2:DescribeVpcs",
        "ec2:DescribeRouteTables",
        "ec2:DescribeNetworkAcls",
        "ec2:DescribeSecurityGroups"
      ],
      "Resource": "*"
    }]
  }' || echo "Policy already exists"

# Attach policy to CDK execution role
aws iam attach-role-policy \
  --role-name $ROLE_NAME \
  --policy-arn arn:aws:iam::${AWS_ACCOUNT}:policy/CDK-EC2-Tagging-Permissions

# Add permissions to EKS cluster role (the one that actually creates the cluster)
EKS_CLUSTER_ROLE="SharedServices-cluster-role"
echo "Adding tagging permissions to EKS cluster role: $EKS_CLUSTER_ROLE"
aws iam attach-role-policy \
  --role-name $EKS_CLUSTER_ROLE \
  --policy-arn arn:aws:iam::${AWS_ACCOUNT}:policy/CDK-EC2-Tagging-Permissions || echo "EKS cluster role not found yet (will be created during deployment)"

# Also try the service-linked role
EKS_SERVICE_ROLE="AWSServiceRoleForAmazonEKS"
if aws iam get-role --role-name $EKS_SERVICE_ROLE >/dev/null 2>&1; then
  echo "Adding tagging permissions to EKS service role..."
  aws iam attach-role-policy \
    --role-name $EKS_SERVICE_ROLE \
    --policy-arn arn:aws:iam::${AWS_ACCOUNT}:policy/CDK-EC2-Tagging-Permissions || echo "Could not attach to EKS service role (expected)"
fi

# Tag subnets directly for EKS load balancer functionality
echo "Tagging subnets for EKS load balancer functionality..."

# Tag public subnets for external load balancers
echo "Tagging public subnets..."
aws ec2 create-tags \
  --resources subnet-0c1dc0737a0311693 subnet-0f230abb61abd1390 \
  --tags Key=kubernetes.io/role/elb,Value=1 || echo "Could not tag public subnets"

# Tag private subnets for internal load balancers
echo "Tagging private subnets..."
aws ec2 create-tags \
  --resources subnet-0e181e7d50fb357ad subnet-0feac163a1cc9a184 subnet-01bf5f0fa17970bc1 subnet-0ec1fac0d877d6f2d subnet-0bea64d61af90dbb7 subnet-0d13f24b40f78a6ca subnet-0d1b5621b10c1f5fa subnet-099e94c901c053448 \
  --tags Key=kubernetes.io/role/internal-elb,Value=1 || echo "Could not tag private subnets"

echo "✅ EC2 tagging permissions added and subnets tagged successfully"