# Subnet Tagger

Interactive tool to tag all subnets across AWS VPCs with CDK and Kubernetes ALB controller tags.

## What it does

**Tags applied automatically:**

**🌍 Public subnets:**
- `aws-cdk:subnet-type: Public`
- `kubernetes.io/role/elb: 1`

**🔒 Private subnets:**
- `aws-cdk:subnet-type: Private`
- `kubernetes.io/role/internal-elb: 1`
- `kubernetes.io/role/cni: 1`

**🚫 Isolated subnets:**
- `aws-cdk:subnet-type: Isolated`
- `kubernetes.io/role/internal-elb: 1`
- `kubernetes.io/role/cni: 1`

## Usage

```bash
# Install dependencies
npm install

# Run interactive subnet tagger
npm run tag-subnets
```

## Features

- ✅ **Interactive CLI** - Choose specific VPCs or tag all
- ✅ **Auto-detection** of subnet types (Public/Private/Isolated)
- ✅ **AWS Console tags** - Applied to actual AWS resources
- ✅ **Inventory generation** - Creates `VPC-INVENTORY.md` with all details
- ✅ **Organized output** - Beautiful markdown tables for easy viewing

## Generated Files

- `VPC-INVENTORY.md` - Complete inventory of all VPCs and subnets with tags

## Example Interaction

```
🏷️ Subnet Tagger - CDK + Kubernetes ALB Controller Tags

Found 2 VPCs:

1. vpc-014f5c11797a4b3d0 - vpc-BootstrapStack (10.0.0.0/16)
2. vpc-037578bc40b4ca79f - Development-VPC (10.1.2.0/24)
3. Tag ALL VPCs

Select option (number): 2
🚀 Tagging subnets in VPC vpc-037578bc40b4ca79f...
  Found 3 subnets in VPC vpc-037578bc40b4ca79f
    ✅ Tagged subnet-08373d5820b871744 as Isolated
    ✅ Tagged subnet-0d097bc1805dabf90 as Isolated
    ✅ Tagged subnet-0c3f97197fc2bc128 as Isolated

📄 Generating VPC inventory...
✅ Generated VPC-INVENTORY.md
```

## Why These Tags Matter

- **CDK tags** help identify subnet types for infrastructure automation
- **Kubernetes ALB Controller** uses these tags to automatically discover subnets for load balancers
- **ELB tags** tell AWS Load Balancer Controller where to place internet-facing load balancers
- **Internal-ELB tags** specify subnets for internal load balancers
- **CNI tags** mark subnets available for Kubernetes pod networking

## Project Structure

```
subnet-tagger/
├── scripts/interactive-tagger.js  # Main tagging script
├── package.json                   # Dependencies
├── README.md                      # This file
└── VPC-INVENTORY.md              # Generated inventory (after running)
```

## Prerequisites

- AWS CLI configured with appropriate permissions
- EC2 permissions: `DescribeVpcs`, `DescribeSubnets`, `DescribeRouteTables`, `CreateTags`