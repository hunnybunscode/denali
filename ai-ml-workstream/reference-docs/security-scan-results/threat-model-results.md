# Threat Model Results - STRIDE Analysis

## System Overview

The Denali AI-ML Workstream project implements an automated security vulnerability remediation system for software development. The system uses AWS Step Functions and Lambda functions to orchestrate a workflow that:

1. Analyzes code using Fortify scans to detect security vulnerabilities
2. Utilizes Amazon Bedrock (LLM) to automatically generate fixes for identified issues
3. Interacts with a version control system (Gitea) to manage code changes
4. Creates branches, commits fixes, and opens pull requests
5. Tracks the remediation process through issue management
6. Stores data about findings and fixes using DynamoDB

## Data Flow Diagram Components

### External Entities
- Developers/Users
- Fortify Scan System
- Gitea Version Control System

### Processes
- Step Functions Workflow
- Lambda Functions:
  - Git Branch CRUD
  - Git Issues CRUD
  - Git PR CRUD
  - Git Code Merge
  - Git Grab File
  - Code Remediation Bedrock
  - Parse Fortify Findings
  - Verify Findings Resolved

### Data Stores
- DynamoDB Tables
- AWS Secrets Manager
- Git Repositories

### Data Flows
1. Fortify scan results → Parse Fortify Findings → DynamoDB
2. Git Repository → Git Grab File → Code Remediation Bedrock
3. Code Remediation Bedrock → Git Code Merge → Git Repository
4. Step Functions → Git Branch/Issues/PR CRUD → Git Repository

## STRIDE Analysis

### Spoofing

| Threat | Risk Level | Existing Controls | Gaps | Recommendations |
|--------|------------|-------------------|------|-----------------|
| Unauthorized access to AWS resources | Medium | IAM roles and policies | Some IAM policies use wildcards | Restrict IAM policies to specific resources and actions |
| Unauthorized access to Git repositories | High | Gitea tokens stored in Secrets Manager | Hardcoded ARNs for secrets | Use environment variables or parameters for secret ARNs |
| Impersonation of Lambda functions | Low | IAM roles for Lambda functions | - | Continue using IAM roles for Lambda functions |

### Tampering

| Threat | Risk Level | Existing Controls | Gaps | Recommendations |
|--------|------------|-------------------|------|-----------------|
| Modification of code during remediation | High | VPC isolation for Lambda functions | No input validation for code | Implement input validation for code modifications |
| Modification of Fortify scan results | Medium | VPC isolation for Lambda functions | No integrity verification | Implement integrity checks for scan results |
| Unauthorized modification of Git repositories | High | Gitea authentication | No branch protection rules evident | Implement branch protection rules in Git repositories |
| Modification of Lambda function code | Medium | IAM permissions | - | Implement code signing for Lambda functions |

### Repudiation

| Threat | Risk Level | Existing Controls | Gaps | Recommendations |
|--------|------------|-------------------|------|-----------------|
| Denial of actions taken by the system | Medium | Git commit history | No audit logging | Implement comprehensive audit logging |
| Denial of code modifications | Medium | Git commit history | No digital signatures for commits | Implement GPG signing for Git commits |
| Denial of API calls | Medium | CloudTrail (assumed) | No explicit CloudTrail configuration | Ensure CloudTrail is enabled and properly configured |

### Information Disclosure

| Threat | Risk Level | Existing Controls | Gaps | Recommendations |
|--------|------------|-------------------|------|-----------------|
| Exposure of sensitive code | High | VPC isolation for Lambda functions | No data classification | Implement data classification for code repositories |
| Exposure of Gitea tokens | High | Secrets Manager | Hardcoded ARNs | Use environment variables or parameters for secret ARNs |
| Exposure of vulnerability information | Medium | VPC isolation for Lambda functions | No access controls for vulnerability data | Implement access controls for vulnerability data |
| Leakage through logs | Medium | - | Unencrypted CloudWatch Logs | Configure KMS encryption for CloudWatch Logs |
| XML External Entity (XXE) attacks | Critical | - | Using standard XML library | Replace with defusedxml library |

### Denial of Service

| Threat | Risk Level | Existing Controls | Gaps | Recommendations |
|--------|------------|-------------------|------|-----------------|
| Lambda function resource exhaustion | Medium | - | No concurrent execution limits | Set appropriate concurrent execution limits |
| Step Functions execution timeouts | Low | Timeout configuration | - | Continue monitoring timeout configurations |
| HTTP request hanging | High | - | No timeouts for HTTP requests | Add timeouts to all HTTP requests |
| Git API rate limiting | Medium | - | No rate limiting handling | Implement backoff strategies for API calls |

### Elevation of Privilege

| Threat | Risk Level | Existing Controls | Gaps | Recommendations |
|--------|------------|-------------------|------|-----------------|
| Exploitation of Lambda vulnerabilities | Medium | IAM roles | Some IAM policies use wildcards | Restrict IAM policies to specific resources and actions |
| Command injection through code remediation | High | - | No input validation | Implement input validation for all external inputs |
| Privilege escalation through Step Functions | Low | IAM roles | - | Continue using principle of least privilege |

## Critical Findings and Recommendations

### Critical Findings:

1. **XML External Entity (XXE) Vulnerability**
   - The parse_fortify_findings_dynamodb Lambda function uses the standard XML library, which is vulnerable to XXE attacks.
   - This could allow an attacker to read arbitrary files, perform server-side request forgery, or cause denial of service.

2. **Missing HTTP Request Timeouts**
   - Multiple Lambda functions make HTTP requests without timeouts.
   - This could lead to Lambda functions hanging indefinitely, causing increased costs and potential denial of service.

3. **Hardcoded Secrets and ARNs**
   - The code contains hardcoded ARNs for secrets and potentially other sensitive information.
   - This violates security best practices and makes secret rotation more difficult.

4. **Overly Permissive IAM Policies**
   - Some IAM policies use wildcard resources and actions.
   - This violates the principle of least privilege and could allow unintended access.

5. **Lack of Input Validation**
   - There is limited evidence of input validation for external inputs.
   - This could lead to injection attacks or other security vulnerabilities.

### Key Recommendations:

1. **Replace XML Library**
   - Replace the standard XML library with defusedxml to prevent XXE attacks.
   - Example: `import defusedxml.ElementTree as ET` instead of `import xml.etree.ElementTree as ET`.

2. **Add HTTP Request Timeouts**
   - Add timeouts to all HTTP requests to prevent hanging.
   - Example: `requests.get(url, timeout=10)` instead of `requests.get(url)`.

3. **Implement Proper Error Handling**
   - Add proper error handling to all HTTP requests.
   - Example: `response.raise_for_status()` after each request.

4. **Move Hardcoded Secrets to Parameters**
   - Use environment variables or parameters for secret ARNs.
   - Example: `secret_arn = os.environ.get('GITEA_TOKEN_SECRET_ARN')`.

5. **Restrict IAM Policies**
   - Restrict IAM policies to specific resources and actions.
   - Avoid using wildcards in IAM policies.

6. **Implement Input Validation**
   - Add input validation for all external inputs.
   - Validate and sanitize code before modification.

7. **Configure Lambda Function Safeguards**
   - Set concurrent execution limits for Lambda functions.
   - Configure Dead Letter Queues for Lambda functions.
   - Configure encryption for Lambda environment variables.

8. **Enhance Logging and Monitoring**
   - Implement comprehensive audit logging.
   - Configure KMS encryption for CloudWatch Logs.
   - Set up alerts for security-related events.

9. **Implement Git Security Controls**
   - Implement branch protection rules in Git repositories.
   - Consider implementing GPG signing for Git commits.

10. **Regular Security Testing**
    - Perform regular security testing, including penetration testing and code reviews.
    - Automate security scanning in the CI/CD pipeline.
