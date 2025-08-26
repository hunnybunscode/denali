# Code Scan Results

This document summarizes the findings from the security scans performed on the Denali AI-ML Workstream project. The scans include Semgrep, Bandit, CFN_Nag, Checkov, and Gitleaks.

## High and Critical Findings

### Critical Findings

1. ~~**XML External Entity (XXE) Vulnerability in parse_fortify_findings_dynamodb/index.py**~~ `FIXED`
   - **Severity**: ERROR
   - **Tool**: Semgrep
   - **Location**: `ai-ml-workstream/stacks/step_functions_stack/lambdas/parse_fortify_findings_dynamodb/index.py`
   - **Description**: The native Python `xml` library is being used instead of `defusedxml`. This makes the application vulnerable to XML External Entity (XXE) attacks, which can lead to data leakage, denial of service, and other security issues.
   - **Impact**: An attacker could craft malicious XML input that could lead to unauthorized access to local files, server-side request forgery, or denial of service attacks.
   - **Remediation**: Replace the standard `xml` library with `defusedxml` which is specifically designed to prevent XXE attacks.

2. **Hardcoded Secrets in Multiple Files**
   - **Severity**: ERROR
   - **Tool**: Gitleaks
   - **Location**: Multiple files including SHCA/security-hub-compliance-analyzer.yaml, keycloak-workstream files, and NiceDCV-Workstream/cdk_app/dcv-key-pair.pem
   - **Description**: Multiple API keys, passwords, and a private key were detected in the codebase.
   - **Impact**: Hardcoded secrets can lead to unauthorized access if the code is exposed. Private keys should never be stored in code repositories.
   - **Remediation**: Move all secrets to AWS Secrets Manager or another secure secret storage solution, and reference them dynamically in the code.

3. **Arbitrary Sleep in Lambda Functions**
   - **Severity**: ERROR
   - **Tool**: Semgrep
   - **Location**: `ai-ml-workstream/stacks/step_functions_stack/lambdas/create_dynamodb_table/index.py`
   - **Description**: Hardcoded `time.sleep()` calls were detected in Lambda functions, which can lead to unnecessary billing and timeouts.
   - **Impact**: This can cause Lambda functions to run longer than necessary, increasing costs and potentially causing timeouts.
   - **Remediation**: Remove unnecessary sleep calls or implement proper asynchronous handling.

4. **Eval Usage in Code**
   - **Severity**: WARNING
   - **Tool**: Semgrep/Bandit
   - **Location**: `diode-workstream/daffodil/app.py` and `diode-workstream/daffodil/daffodil_conversion/daffodil_conversion_stack.py`
   - **Description**: The code uses `eval()` which can execute arbitrary code.
   - **Impact**: If user input is passed to eval(), it could lead to remote code execution vulnerabilities.
   - **Remediation**: Replace eval() with safer alternatives like ast.literal_eval() or proper parsing functions.

### High Severity Findings

1. ~~**Missing Timeout in HTTP Requests**~~ `FIXED`
   - **Severity**: WARNING
   - **Tool**: Semgrep/Bandit
   - **Location**: Multiple Lambda functions in `stacks/step_functions_stack/lambdas/`
   - **Description**: HTTP requests are made without setting a timeout, which could cause Lambda functions to hang indefinitely.
   - **Impact**: This can lead to increased costs, degraded performance, and potential denial of service.
   - **Remediation**: Add appropriate timeouts to all HTTP requests.

2. **Missing Error Handling in HTTP Requests**
   - **Severity**: WARNING
   - **Tool**: Semgrep
   - **Location**: Multiple Lambda functions in `stacks/step_functions_stack/lambdas/`
   - **Description**: HTTP requests don't use `raise_for_status()` to check for HTTP errors.
   - **Impact**: Failed requests might not be properly detected, leading to silent failures and unexpected behavior.
   - **Remediation**: Add proper error handling with `raise_for_status()` after each request.

3. **Missing Encoding Parameter in File Operations**
   - **Severity**: WARNING
   - **Tool**: Semgrep
   - **Location**: `ai-ml-workstream/config/config.py` and `ai-ml-workstream/stacks/step_functions_stack/lambdas/parse_fortify_findings_dynamodb/index.py`
   - **Description**: Files are opened without specifying an encoding, which can lead to encoding issues.
   - **Impact**: This can cause corruption of files with special characters and cross-platform compatibility issues.
   - **Remediation**: Always specify encoding (e.g., `encoding="utf-8"`) when opening files in text mode.

4. **Dynamic URL Usage in urllib**
   - **Severity**: WARNING
   - **Tool**: Semgrep
   - **Location**: `diode-workstream/cross-account/validation-account/ec2-files/utils.py`
   - **Description**: Dynamic values are used with urllib, which supports file:// schemes.
   - **Impact**: This could potentially allow an attacker to read arbitrary files if they can control the URL.
   - **Remediation**: Validate URLs before using them or switch to the requests library with proper validation.

## Medium and Low Severity Findings

### IAM Policy Issues

1. **Overly Permissive IAM Policies**
   - **Severity**: WARNING
   - **Tool**: CFN_Nag/Checkov
   - **Description**: Multiple IAM policies use wildcard (*) resources or actions.
   - **Impact**: This violates the principle of least privilege and could allow unintended access.
   - **Remediation**: Restrict IAM policies to only the specific resources and actions needed.

### Lambda Function Configuration Issues

1. **Lambda Functions Not in VPC**
   - **Severity**: WARNING
   - **Tool**: CFN_Nag/Checkov
   - **Description**: Some Lambda functions are not configured to run inside a VPC.
   - **Impact**: This reduces network isolation and security.
   - **Remediation**: Configure all Lambda functions to run inside a VPC with appropriate security groups.

2. **Missing Concurrent Execution Limits**
   - **Severity**: WARNING
   - **Tool**: CFN_Nag/Checkov
   - **Description**: Lambda functions don't have concurrent execution limits defined.
   - **Impact**: This could lead to resource exhaustion or unexpected costs.
   - **Remediation**: Set appropriate concurrent execution limits for all Lambda functions.

3. **Missing Dead Letter Queues**
   - **Severity**: WARNING
   - **Tool**: CFN_Nag/Checkov
   - **Description**: Lambda functions don't have Dead Letter Queues configured.
   - **Impact**: Failed executions might not be properly tracked or retried.
   - **Remediation**: Configure Dead Letter Queues for all Lambda functions.

### S3 Bucket Configuration Issues

1. **Missing S3 Bucket Logging**
   - **Severity**: WARNING
   - **Tool**: CFN_Nag/Checkov
   - **Description**: S3 buckets don't have access logging enabled.
   - **Impact**: This makes it difficult to audit access and detect unauthorized access attempts.
   - **Remediation**: Enable access logging for all S3 buckets.

2. **Missing S3 Bucket Versioning**
   - **Severity**: WARNING
   - **Tool**: Checkov
   - **Description**: S3 buckets don't have versioning enabled.
   - **Impact**: This increases the risk of data loss due to accidental deletion or overwriting.
   - **Remediation**: Enable versioning for all S3 buckets.

### Encryption Issues

1. **Unencrypted CloudWatch Logs**
   - **Severity**: WARNING
   - **Tool**: CFN_Nag/Checkov
   - **Description**: CloudWatch Log Groups are not encrypted with KMS.
   - **Impact**: Log data might contain sensitive information that should be encrypted at rest.
   - **Remediation**: Configure KMS encryption for all CloudWatch Log Groups.

2. **Unencrypted SQS Queues**
   - **Severity**: WARNING
   - **Tool**: Checkov
   - **Description**: SQS queues don't specify KMS encryption.
   - **Impact**: Messages in the queue might contain sensitive data that should be encrypted.
   - **Remediation**: Configure KMS encryption for all SQS queues.

3. **Unencrypted Lambda Environment Variables**
   - **Severity**: WARNING
   - **Tool**: Checkov
   - **Description**: Lambda functions have environment variables that are not encrypted.
   - **Impact**: Environment variables might contain sensitive configuration that should be encrypted.
   - **Remediation**: Configure encryption for Lambda environment variables.

## Informational Findings

1. **Unquoted Variable Expansion in Shell Scripts**
   - **Severity**: INFO
   - **Tool**: Semgrep
   - **Location**: Various shell scripts
   - **Description**: Variable expansions in shell scripts are not properly quoted.
   - **Impact**: This could lead to unexpected behavior if variables contain spaces or special characters.
   - **Remediation**: Always quote variable expansions in shell scripts.

2. **Try-Except-Pass Patterns**
   - **Severity**: INFO
   - **Tool**: Bandit
   - **Location**: Various Python files
   - **Description**: Code uses try-except blocks that silently pass on exceptions.
   - **Impact**: This can hide errors and make debugging difficult.
   - **Remediation**: Add proper error handling and logging in exception blocks.

3. **Use of Standard Random Number Generators**
   - **Severity**: INFO
   - **Tool**: Bandit
   - **Location**: Various Python files
   - **Description**: Standard random number generators are used in security contexts.
   - **Impact**: These are not suitable for cryptographic purposes.
   - **Remediation**: Use secure random number generators from the `secrets` module for security-sensitive operations.

## Remediation Priorities

### Immediate Action Required:
1. Fix the XML External Entity (XXE) vulnerability by replacing the standard XML library with defusedxml
2. Remove all hardcoded secrets and move them to AWS Secrets Manager
3. Remove or replace eval() usage with safer alternatives
4. Add timeouts to all HTTP requests
5. Add proper error handling to HTTP requests

### High Priority:
1. Configure Lambda functions to run inside VPCs
2. Add proper encoding parameters to file operations
3. Fix dynamic URL usage in urllib
4. Restrict IAM policies to follow the principle of least privilege

### Medium Priority:
1. Configure Dead Letter Queues for Lambda functions
2. Set concurrent execution limits for Lambda functions
3. Enable encryption for CloudWatch Logs, SQS queues, and Lambda environment variables
4. Enable access logging and versioning for S3 buckets

### Low Priority:
1. Fix unquoted variable expansions in shell scripts
2. Improve exception handling in try-except blocks
3. Replace standard random number generators with secure alternatives
