# AI/ML Workstream Deployment Guide

This guide provides step-by-step instructions for deploying the AI/ML workstream infrastructure using AWS CDK.

## Deployment Approaches

There are two deployment approaches available:

1. **Direct CDK Deployment** (Recommended - works with ProjAdmin role)
2. **CloudFormation Template Deployment** (Alternative approach)

**The CDK deployment approach now works successfully with permissions boundaries** thanks to the custom AFC2S bootstrap template that properly configures the role assumption chain.

## Prerequisites

### Development Environment
- AWS CLI configured with appropriate credentials
- Python 3.9+ installed
- Node.js 20+ installed (for CDK CLI)
- Docker installed and running
- Git installed
- Make installed (usually pre-installed on macOS/Linux, for Windows see installation notes below)

### Custom Bootstrap Requirements
This deployment requires a custom CDK bootstrap with AFC2S role naming and permissions boundaries:
- **IAM Prefix**: All roles must be prefixed with "AFC2S"
- **Permissions Boundary**: All roles must have the ProjAdminPolicy permissions boundary attached
- **Custom Bootstrap Template**: Use the provided `custom-bootstrap-template.yaml`

### Amazon Bedrock Prerequisites

**CRITICAL**: You must request access to Bedrock models before deployment. This process can take time, especially in GovCloud.

#### Required Model Access
- **Claude 3.5 Sonnet (anthropic.claude-3-5-sonnet-20240620-v1:0)**: Primary model used for code remediation
- **Claude 3.7 Sonnet (anthropic.claude-3-5-sonnet-20241022-v2:0)**: Alternative/newer model for code remediation
- **Region**: Ensure models are available in your deployment region (us-gov-west-1)

#### How to Request Model Access

**IMPORTANT FOR GOVCLOUD**: Anthropic models (Claude) require access to be requested in your **associated commercial AWS account** first, then the access will be available in GovCloud.

1. **Commercial Account Access Request** (Required for GovCloud):
   ```bash
   # Step 1: Log into your COMMERCIAL AWS account (not GovCloud)
   # Navigate to Amazon Bedrock console in commercial account
   # Go to Model access in the left navigation
   # Request access to both Claude models:
   # - Claude 3.5 Sonnet (anthropic.claude-3-5-sonnet-20240620-v1:0)
   # - Claude 3.7 Sonnet (anthropic.claude-3-5-sonnet-20241022-v2:0)
   # Wait for approval in commercial account
   # Access will then be available in your linked GovCloud account
   ```

2. **GovCloud Console Verification**:
   ```bash
   # After commercial account approval, verify in GovCloud
   # Navigate to Amazon Bedrock console in GovCloud (us-gov-west-1)
   # Go to Model access in the left navigation
   # Verify both Claude models show as "Available" or "Access granted"
   ```

2. **AWS CLI Method**:
   ```bash
   # Check current model access
   aws bedrock list-foundation-models --region us-gov-west-1

   # Request model access (if available via CLI in your region)
   aws bedrock put-model-invocation-logging-configuration \
     --region us-gov-west-1 \
     --logging-config '{
       "cloudWatchConfig": {
         "logGroupName": "/aws/bedrock/modelinvocations",
         "roleArn": "arn:aws-us-gov:iam::ACCOUNT:role/BedrockLoggingRole"
       }
     }'
   ```

3. **Verify Model Access**:
   ```bash
   # Test model access
   aws bedrock-runtime invoke-model \
     --region us-gov-west-1 \
     --model-id anthropic.claude-3-5-sonnet-20240620-v1:0 \
     --body '{"messages":[{"role":"user","content":"Hello"}],"max_tokens":100,"anthropic_version":"bedrock-2023-05-31"}' \
     --cli-binary-format raw-in-base64-out \
     response.json
   ```

#### Model Invocation Logging (Recommended)
Enable Bedrock logging for monitoring and compliance:
- **CloudWatch Logs**: Configure log destination for Bedrock invocations
- **Monitoring**: Set up CloudWatch alarms for failed invocations or high usage
- **Audit Trail**: Required for enterprise compliance and cost tracking

#### Important Notes
- **GovCloud Requirement**: Anthropic model access MUST be requested in your associated **commercial AWS account** first
- **Account Linking**: Ensure your GovCloud account is properly linked to a commercial account with Bedrock access
- **Timing**: Model access requests can take 24-48 hours or longer, especially for initial commercial account approval
- **Regional Availability**: Verify both Claude models are available in us-gov-west-1 after commercial account approval
- **Alternative Models**: If Claude 3.5 or 3.7 Sonnet are unavailable, you may need to modify the Lambda function to use Claude 3 Haiku or other available models
- **Cost Considerations**: Review Bedrock pricing for your expected usage volume in both commercial and GovCloud accounts

### AWS Infrastructure Requirements
- **EC2 Instance with Fortify Scan Environment**: A pre-configured EC2 instance that has:
  - Source code compilation environment set up
  - Fortify Static Code Analyzer (SCA) installed and configured
  - Access to the source code repositories
  - SSM Agent installed and running
  - Appropriate IAM role for SSM Document execution
  - Network connectivity to push scan results to Git repositories
- **SSM Document**: A Systems Manager document configured to run Fortify scans on the EC2 instance
  - **Same Account**: Create the SSM document in the same account as this solution
  - **Cross Account**: Create the SSM document in the account where the EC2 instance resides
  - **Document Name**: Must match the name used in Step Function input parameters
  - **Permissions**: EC2 instance must have IAM role with permission to execute the document
- **Git Repositories**: Access to both source code and scan results repositories
- **Secrets Manager**: API tokens for Git repository access stored in AWS Secrets Manager
- **Amazon Bedrock Model Access**: Request access to required AI models (see Bedrock Prerequisites below)

### Git Repository Configuration Requirements

To use your own Git repositories instead of the default ones, you'll need to update multiple components:

#### 1. SSM Document Updates
The SSM document (`FortifyScan-SSM-Doc-DenaliPOC-FortifyScan-LibNDCmath`) contains hardcoded repository URLs that need to be updated:
- **Source Repository URL**: Currently set to `https://gitea-denali.jakedlee.people.aws.dev/Denali-POC/libNDCmath.git`
- **Findings Repository URL**: Currently set to `https://gitea-denali.jakedlee.people.aws.dev/Denali-POC/libNDCmath-scan-results.git`

#### 2. Network Connectivity Requirements
- **EC2 Instance**: Must have network access to your Git repositories (internet access or VPC endpoints)
- **Lambda Functions**: Must have network access to your Git repositories if deployed in VPC
- **Security Groups**: Allow outbound HTTPS (port 443) traffic to your Git server
- **NAT Gateway/Internet Gateway**: Required if resources are in private subnets

#### 3. Authentication Configuration
- **Secrets Manager**: Update the secret (`gitea/api/token`) with API tokens for your Git repositories
- **Git Credentials**: Ensure the stored credentials have appropriate permissions:
  - Read access to source code repository
  - Read/Write access to scan results repository
  - Branch creation and push permissions

#### 4. Repository Structure Requirements
Your repositories should have:
- **Source Repository**: Contains the code to be scanned
- **Scan Results Repository**: Will store Fortify scan results and findings
- **Branch Access**: The specified branches must exist and be accessible

#### 5. Step Function Input Updates
Update the test input files with your repository URLs:
```json
{
  "codeRepo": "https://your-git-server.com/your-org/your-source-repo.git",
  "scanResultsRepo": "https://your-git-server.com/your-org/your-scan-results-repo.git"
}
```

#### 6. Fortify Scan Script Updates
The Fortify scan script on the EC2 instance may need updates for:
- Repository-specific build commands
- Dependency installation
- Compilation steps specific to your codebase

### Cross-Account Deployment Considerations
If the EC2 instance with Fortify is in a different AWS account than where this solution is deployed, additional configuration is required:

#### In the Fortify Account (where EC2 instance resides):
1. **SSM Document**: Create the Fortify scan SSM document in this account (same document that would be created in same-account scenario)

2. **Cross-Account IAM Role**: Create an IAM role that can be assumed by the Step Functions execution role from the solution account:
   ```json
   {
     "Version": "2012-10-17",
     "Statement": [
       {
         "Effect": "Allow",
         "Principal": {
           "AWS": "arn:aws:iam::SOLUTION-ACCOUNT-ID:role/StepFunctionRole"
         },
         "Action": "sts:AssumeRole"
       }
     ]
   }
   ```

2. **SSM Permissions**: The cross-account role needs permissions to:
   - `ssm:SendCommand` on the target EC2 instance
   - `ssm:GetCommandInvocation` to check execution status
   - `ssm:DescribeInstanceInformation` to verify instance availability

3. **EC2 Instance Tags**: Tag the EC2 instance appropriately for cross-account identification

#### In the Solution Account (where Step Functions are deployed):
1. **Update Step Functions IAM Role**: Add permission to assume the cross-account role:
   ```json
   {
     "Version": "2012-10-17",
     "Statement": [
       {
         "Effect": "Allow",
         "Action": "sts:AssumeRole",
         "Resource": "arn:aws:iam::FORTIFY-ACCOUNT-ID:role/CrossAccountSSMRole"
       }
     ]
   }
   ```

2. **Modify Step Function Definition**: Update the SSM SendCommand task to use cross-account role:
   ```json
   {
     "Type": "Task",
     "Resource": "arn:aws:states:::aws-sdk:ssm:sendCommand",
     "Parameters": {
       "DocumentName": "...",
       "InstanceIds": ["..."],
       "Parameters": {...}
     },
     "Credentials": {
       "RoleArn": "arn:aws:iam::FORTIFY-ACCOUNT-ID:role/CrossAccountSSMRole"
     }
   }
   ```

#### Network Considerations:
- **VPC Peering or Transit Gateway**: If instances are in different VPCs across accounts
- **Security Groups**: Allow necessary communication between accounts
- **DNS Resolution**: Ensure proper name resolution across accounts if needed

#### Alternative Approaches:
1. **Cross-Account Lambda**: Deploy a Lambda function in the Fortify account that the Step Functions can invoke
2. **SQS/SNS**: Use messaging services for cross-account communication
3. **EventBridge**: Use custom events to trigger actions across accounts

## Architecture Overview

The deployment creates two main stacks:
1. **Lambda Stack**: Creates all Lambda functions with shared IAM roles and layers
2. **Step Functions Stack**: Creates state machines using JSON definitions with template variable replacement

## Customization for Your Environment

### Before Deployment: Repository Configuration

If you're using your own Git repositories (not the default Denali POC repos), you'll need to:

1. **Update SSM Document**:
   ```bash
   # Get the current SSM document
   aws ssm get-document --name "FortifyScan-SSM-Doc-DenaliPOC-FortifyScan-LibNDCmath" --region us-gov-west-1

   # Update the document with your repository URLs
   # Replace REPO_URL and FINDINGS_REPO_URL variables in the script
   ```

2. **Update Secrets Manager**:
   ```bash
   # Update the secret with your Git API token
   aws secretsmanager update-secret \
     --secret-id "gitea/api/token" \
     --secret-string "your-git-api-token" \
     --region us-gov-west-1
   ```

3. **Verify Network Connectivity**:
   ```bash
   # Test from EC2 instance
   curl -I https://your-git-server.com

   # Test Git clone access
   git clone https://your-git-server.com/your-org/your-repo.git /tmp/test-clone
   ```

4. **Update Test Input Files**:
   - Modify `test-inputs/test-workflow-input.json`
   - Modify `test-inputs/remediation-input.json`
   - Replace repository URLs with your actual repositories

## Step-by-Step Deployment

## Option 1: Direct CDK Deployment (Recommended)

This approach now works successfully with permissions boundaries thanks to the custom AFC2S bootstrap template.

### Why Use This Approach?

**Proven to Work**: The custom bootstrap template properly configures the role assumption chain (ProjAdmin → AFC2S-deploy-role → AFC2S-cfn-exec-role) to work with permissions boundaries.

**Standard CDK Experience**: Uses familiar CDK commands and workflows while maintaining security compliance.

### Prerequisites for CloudFormation Deployment

1. **Bootstrap must be deployed first** (see Bootstrap Setup section below)
2. **CDK synthesis environment** (local machine or CI/CD pipeline with CDK installed)
3. **Target environment** with ProjAdmin credentials

### CloudFormation Deployment Steps

#### Step 1: Synthesize CDK Templates (Development Environment)

```bash
# Navigate to project directory
cd /path/to/ai-ml-workstream

# Create and activate Python virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
npm install -g aws-cdk

# Configure deployment settings
# Edit config/deployment_config.yaml with your values

# Synthesize CloudFormation templates
cdk synth --all --context config_file=config/deployment_config.yaml
```

This creates CloudFormation templates in the `cdk.out/` directory.

#### Step 2: Deploy Templates (Target Environment with ProjAdmin)

```bash
# Deploy Lambda Stack
aws cloudformation deploy \
  --template-file cdk.out/ProjAdmin-v1-LambdaStack.template.json \
  --stack-name ProjAdmin-v1-LambdaStack \
  --capabilities CAPABILITY_NAMED_IAM \
  --region us-gov-west-1

# Deploy Step Functions Stack
aws cloudformation deploy \
  --template-file cdk.out/ProjAdmin-v1-StepFunctionsStack.template.json \
  --stack-name ProjAdmin-v1-StepFunctionsStack \
  --capabilities CAPABILITY_NAMED_IAM \
  --region us-gov-west-1
```

#### Step 3: Verify Deployment

```bash
# Check stack status
aws cloudformation describe-stacks --stack-name ProjAdmin-v1-LambdaStack --region us-gov-west-1
aws cloudformation describe-stacks --stack-name ProjAdmin-v1-StepFunctionsStack --region us-gov-west-1

# Verify IAM roles have AFC2S prefix and permissions boundaries
aws iam list-roles --query "Roles[?contains(RoleName, 'AFC2S-ProjAdmin')].[RoleName,PermissionsBoundary.PermissionsBoundaryArn]" --output table
```

### Advantages of CloudFormation Deployment

✅ **Works with permissions boundaries** - No role assumption chain issues
✅ **Simpler permission model** - Uses your credentials directly
✅ **Same security compliance** - All roles still get AFC2S prefix and permissions boundaries
✅ **Standard CloudFormation features** - Rollback, change sets, drift detection
✅ **CI/CD friendly** - Easy to integrate into deployment pipelines

### Template Transfer Methods

**For Air-Gapped Environments**:
1. Synthesize templates in development environment
2. Transfer `cdk.out/` directory via approved methods
3. Deploy templates in target environment

**For Connected Environments**:
1. Store templates in approved artifact repository
2. Download and deploy in target environment

---

## Option 2: CloudFormation Template Deployment (Alternative Approach)

Use this approach if you prefer to deploy CloudFormation templates directly or encounter any issues with the CDK approach.

### 1. Custom Bootstrap Setup

**IMPORTANT**: This deployment requires a custom CDK bootstrap with AFC2S role naming and permissions boundaries. You must complete this step before deploying the application.

#### Bootstrap with Custom Template

```bash
# Bootstrap using the custom template with AFC2S prefix and permissions boundary
cdk bootstrap \
  --template custom-bootstrap-template.yaml \
  --parameters aaIamPrefix=AFC2S \
  --parameters aaPermissionBoundaryArn=arn:aws-us-gov:iam::{YOUR-ACCOUNT-ID}:policy/ProjAdminPolicy \
  --qualifier v1 \
  --region us-gov-west-1
```

#### Verify Bootstrap Roles

After bootstrapping, verify the custom roles were created:

```bash
# Check that AFC2S-prefixed roles exist
aws iam list-roles --query "Roles[?contains(RoleName, 'AFC2S-cdk-v1')].[RoleName,PermissionsBoundary.PermissionsBoundaryArn]" --output table

# Expected roles:
# - AFC2S-cdk-v1-cfn-exec-role-{AccountId}-{Region}
# - AFC2S-cdk-v1-deploy-role-{AccountId}-{Region}
# - AFC2S-cdk-v1-file-pub-role-{AccountId}-{Region}
# - AFC2S-cdk-v1-image-pub-role-{AccountId}-{Region}
# - AFC2S-cdk-v1-lookup-role-{AccountId}-{Region}
```

### 2. Verify Bedrock Model Access

**IMPORTANT**: Verify you have access to required Bedrock models before proceeding with deployment.

**GovCloud Users**: Ensure you have requested Anthropic model access in your **commercial AWS account** first. The access will then be available in your linked GovCloud account.

```bash
# Test Claude 3.5 Sonnet access
aws bedrock-runtime invoke-model \
  --region us-gov-west-1 \
  --model-id anthropic.claude-3-5-sonnet-20240620-v1:0 \
  --body '{"messages":[{"role":"user","content":"Test"}],"max_tokens":10,"anthropic_version":"bedrock-2023-05-31"}' \
  --cli-binary-format raw-in-base64-out \
  bedrock-test-response.json

# Check if the test was successful
if [ $? -eq 0 ]; then
  echo "✅ Bedrock model access confirmed"
  cat bedrock-test-response.json
  rm bedrock-test-response.json
else
  echo "❌ Bedrock model access failed"
  echo ""
  echo "For GovCloud users:"
  echo "1. Ensure you requested access in your COMMERCIAL AWS account first"
  echo "2. Verify your GovCloud account is linked to the commercial account"
  echo "3. Wait for commercial account approval, then check GovCloud console"
  echo ""
  echo "See 'Amazon Bedrock Prerequisites' section above for detailed instructions"
  exit 1
fi
```

### 3. Environment Setup

```bash
# Clone or navigate to the project directory
cd /path/to/ai-ml-workstream

# Create and activate Python virtual environment
python3 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install Python dependencies
pip install -r requirements.txt
```

### 4. Install Required Tools

```bash
# Install CDK CLI globally
npm install -g aws-cdk

# Verify CDK installation
cdk --version

# Verify Make is installed
make --version

# If Make is not installed:
# - macOS: Install Xcode Command Line Tools: xcode-select --install
# - Linux: sudo apt-get install build-essential (Ubuntu/Debian) or sudo yum install make (RHEL/CentOS)
# - Windows: Install via Chocolatey: choco install make, or use WSL
```

### 5. Configure AWS Credentials

```bash
# Verify AWS credentials are configured
aws sts get-caller-identity

# Expected output should show your account ID and role
```

### 6. Enable Bedrock Model Invocation Logging

**Important**: Enable Bedrock logging before deployment for monitoring and compliance:

```bash
# Enable Bedrock model invocation logging
aws bedrock put-model-invocation-logging-configuration \
  --logging-config '{
    "cloudWatchConfig": {
      "logGroupName": "/aws/bedrock/modelinvocations",
      "roleArn": "arn:aws-us-gov:iam::ACCOUNT-ID:role/BedrockLoggingRole"
    },
    "textDataDeliveryEnabled": false,
    "imageDataDeliveryEnabled": false,
    "embeddingDataDeliveryEnabled": false
  }' \
  --region us-gov-west-1

# Verify logging configuration
aws bedrock get-model-invocation-logging-configuration --region us-gov-west-1
```

### 7. Configure Deployment Settings

Edit `config/deployment_config.yaml` with your specific values:

```yaml
namespace: "your-name"  # Replace with your identifier
version: "v1"
region: "us-gov-west-1"  # Your target AWS region
networking:
  vpc_id: "vpc-xxxxxx"               # Replace with your VPC ID
  subnets:
    - subnet_id: "subnet-xxxxxx"     # Replace with your subnet IDs
      availability_zone: "us-gov-west-1a"
    - subnet_id: "subnet-yyyyyy"
      availability_zone: "us-gov-west-1b"
  security_group_id: "sg-xxxxxx"     # Replace with your security group ID

lambda_functions:
  git_branch_crud: "Git_Branch_CRUD"
  git_issues_crud: "Git_Issues_CRUD"
  git_code_merge_and_push: "Git_Code_Merge_and_Push"
  create_dynamodb_table: "Create_DynamoDB_Table"
  parse_fortify_findings: "Parse_Fortify_Findings_into_DynamoDB"
  dynamodb_table_scan: "DynamoDB_Table_Scan"
  bedrock_llm_call: "Code_Remediation_Bedrock"
  git_file_crud: "Git_Grab_File"
  verify_findings_resolved: "Verify_Findings_Resolved"
  git_pr_crud: "Git_PR_CRUD"

remediation_state_machine: "DenaliPOC-Remediation-Test"
```

### 8. Bootstrap CDK (First-time setup only)

```bash
# Bootstrap CDK in your AWS account/region (only needed once per account/region)
make bootstrap

# Alternative: Direct CDK command
# cdk bootstrap
```

### 9. Synthesize CloudFormation Templates (Recommended)

```bash
# Generate CloudFormation templates to verify everything compiles correctly
make synth

# This is equivalent to:
# cdk synth --all --context config_file=config/deployment_config.yaml
```

### 10. Deploy the Infrastructure (Recommended)

```bash
# Deploy both stacks using Makefile (recommended approach)
make deploy

# This automatically:
# - Uses the default config file (config/deployment_config.yaml)
# - Deploys both stacks in the correct order (Lambda stack first, then Step Functions)
# - Equivalent to: cdk deploy --all --context config_file=config/deployment_config.yaml

# Optional: Use custom config file
make deploy CONFIG_FILE=config/my-custom-config.yaml
```

### 11. Verify Deployment

```bash
# Check deployment status
aws cloudformation describe-stacks --stack-name your-namespace-v1-LambdaStack
aws cloudformation describe-stacks --stack-name your-namespace-v1-StepFunctionsStack

# List all CDK stacks
cdk list --context config_file=config/deployment_config.yaml
```

## Alternative: Direct CDK Commands

If you prefer to use CDK commands directly instead of the Makefile:

```bash
# Synthesize templates
cdk synth --all --context config_file=config/deployment_config.yaml

# Deploy both stacks
cdk deploy --all --context config_file=config/deployment_config.yaml

# Deploy individual stacks
cdk deploy --context config_file=config/deployment_config.yaml your-namespace-v1-LambdaStack
cdk deploy --context config_file=config/deployment_config.yaml your-namespace-v1-StepFunctionsStack
```

## Troubleshooting

### CDK Role Assumption Issues

If you encounter errors like:
```
Role arn:aws-us-gov:iam::ACCOUNT:role/AFC2S-cdk-v1-cfn-exec-role-ACCOUNT-REGION is invalid or cannot be assumed
```

**Root Cause**: CDK's role assumption chain (your-role → deploy-role → cfn-exec-role) fails when permissions boundaries are applied to bootstrap roles.

**Solution**: Use the CloudFormation template deployment approach instead:

```bash
# Synthesize templates
cdk synth --all --context config_file=config/deployment_config.yaml

# Deploy with CloudFormation directly
aws cloudformation deploy \
  --template-file cdk.out/YourStack-LambdaStack.template.json \
  --stack-name YourStack-LambdaStack \
  --capabilities CAPABILITY_NAMED_IAM
```

**Why This Works**:
- Bypasses CDK's complex role assumption chain
- Uses your credentials directly with CloudFormation
- Maintains all security compliance (AFC2S prefix, permissions boundaries)

### Bootstrap Permission Issues

If bootstrap deployment fails with:
```
User is not authorized to perform: iam:CreateRole
```

**Root Cause**: The role you're using has a permissions boundary that blocks IAM role creation.

**Solutions**:
1. **Remove permissions boundary temporarily** during bootstrap deployment
2. **Use a role without permissions boundary** for bootstrap (Admin role)
3. **Have customer's admin team deploy bootstrap** for you

### Docker Issues
If you encounter Docker connectivity issues during Lambda layer bundling:

```bash
# Clean Docker system
docker system prune -f

# Test Docker connectivity
docker pull hello-world

# If issues persist, restart Docker Desktop
```

### CDK Synthesis Conflicts
If you get "Another CLI is currently synthing" error:

```bash
# Use different output directory
cdk synth --context config_file=config/deployment_config.yaml --output cdk.out.temp
```

### Permission Issues
Ensure your AWS credentials have the following permissions:
- CloudFormation full access
- Lambda full access
- Step Functions full access
- IAM role creation and management
- VPC and networking access
- Secrets Manager access
- DynamoDB access
- Bedrock access

## Cleanup

To remove all deployed resources:

```bash
# Destroy all stacks using Makefile (recommended)
make clean

# Alternative: Direct CDK command
# cdk destroy --all --context config_file=config/deployment_config.yaml
```

## Architecture Components

### Lambda Functions Created:
- Git Branch CRUD operations
- Git Issues CRUD operations
- Git Code Merge and Push
- DynamoDB Table Creation
- Fortify Findings Parser
- DynamoDB Table Scanner
- Bedrock LLM Integration
- Git File Operations
- Findings Verification
- Git Pull Request CRUD

### Step Functions Created:
- Remediation State Machine (JSON-based definition)
- Test State Machine (JSON-based definition)

### Key Features:
- Template-based JSON Step Function definitions
- Configurable Lambda function names
- Shared IAM roles and policies
- Lambda layer with requests package
- VPC-enabled Lambda functions
- Comprehensive error handling and retries

## Testing the Deployed Workflows

After successful deployment, test the Step Functions using AWS CLI commands:

### Quick Test Commands
```bash
# List your deployed Step Functions
aws stepfunctions list-state-machines --region us-gov-west-1 \
  --query "stateMachines[?contains(name, 'your-namespace')]"

# Execute test workflow (requires valid EC2 instance and SSM document)
aws stepfunctions start-execution \
  --state-machine-arn "arn:aws-us-gov:states:us-gov-west-1:ACCOUNT:stateMachine:your-namespace-v1TestStepFunction-XXXXX" \
  --name "test-execution-$(date +%s)" \
  --input file://test-inputs/test-workflow-input.json \
  --region us-gov-west-1

# Monitor execution status
aws stepfunctions describe-execution \
  --execution-arn "EXECUTION_ARN_FROM_PREVIOUS_COMMAND" \
  --region us-gov-west-1
```

For comprehensive testing instructions, see [CLI_TESTING_COMMANDS.md](CLI_TESTING_COMMANDS.md).

## Support

For issues or questions, refer to:
- AWS CDK Documentation: https://docs.aws.amazon.com/cdk/
- AWS Step Functions Documentation: https://docs.aws.amazon.com/step-functions/
- Project README.md for additional context
- [CLI_TESTING_COMMANDS.md](CLI_TESTING_COMMANDS.md) for testing procedures