# Welcome to IAM Deploy Role Calculator
This project will generate a list of IAM actions related to an IAM Role usage and a CFN/CDK Template File. This is a tool that could generate the bulk to necessary IAM Actions (Create, Update, Delete) to complete deployment.
If using the `-Enhance` flag, it will catch a bit more IAM Actions but however it will only track your recent action ie for Create, or Delete or Update over time.
If `action.txt.` file exist in the workspace, it will update the IAM role `cloudformation-test-exec-role`, which you can use to validate your CFN/CDK Template file to catch missed IAM Actions

## Useful commands

* `npm run build`   compile typescript to js
* `npm run watch`   watch for changes and compile
* `npm run test`    perform the jest unit tests
* `npx cdk deploy`  deploy this stack to your default AWS account/region
* `npx cdk diff`    compare deployed stack with current state
* `npx cdk synth`   emits the synthesized CloudFormation template

## Prerequisites
* AWS Rain 1.x+
* NodeJS 20+
* Powershell 7.x+
* AWS CLI v2+

## Deployment
> Tested on Standard AWS

1. Deploy the CDK Stack with your AWS console programmatic access credentials and default CDK default region
   ````bash
   EXPORT CDK_DEFAULT_REGION=us-west-1
   npm ci
   cdk bootstrap
   cdk deploy
   ```

2. Use the powershell script under a powershell terminal using your AWS console programmatic access credentials
    Sample command
   ```pwsh
     ./generateIAMAction.ps1 -TemplateFile /Users/jktruong/workspace/engagements/c3e/bootstrap/jktruong+team-deployment-taser-SharedServices-Admin.us-east-1.cdk.out/SapDomainServicesStack.template.json,cdk.out/BootstrapStack.template.json
    ```

3. Read the output text `action.txt` for the list of IAM Actions related to target role

## Usage
Powershell script usage for `generateIAMAction.ps1`

```
<#
.SYNOPSIS
    Create a text file action.txt from parsing Cloudformation template file

    Sample command:
    ./generateIAMAction.ps1 -TemplateFile (Get-ChildItem -File -Filter *.template.json -Path ../../jktruong+team-deployment-taser-SharedServices-Admin.us-east-1.cdk.out | Select-Object -ExpandProperty FullName)
    ./generateIAMAction.ps1 -TemplateFile /Users/jktruong/workspace/engagements/c3e/bootstrap/jktruong+team-deployment-taser-SharedServices-Admin.us-east-1.cdk.out/SapDomainServicesStack.template.json,cdk.out/BootstrapStack.template.json

.DESCRIPTION
    This script generate an action.txt text file containing estimated needed resource actions from a Cloudformation Stack Template (JSON) to assist in the creation of IAM Policy.
    If template file is a YAML file, convert it to JSON file.

    Depends on having rain installed (brew install rain)

.PARAMETER TemplateFile
    File path of each Cloudformation template json file

.PARAMETER OutputDirectory
    Set the output Directory for the action.txt

.PARAMETER Enhance
    File path of each Cloudformation template json file

.PARAMETER RoleArn
    Query the enhancement scan on a specific role arn. Default: arn:XXX:iam::XXXXXXXXXX:role/cloudformation-admin-exec-role

.PARAMETER Since
    Set how back to read the Cloudtrail logs. Default: 4 hours from now

.PARAMETER Region
    Set the AWS Region to query on
#>
```
