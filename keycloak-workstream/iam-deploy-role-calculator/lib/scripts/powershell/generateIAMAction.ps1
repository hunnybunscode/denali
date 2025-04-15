using namespace System;

<#
.SYNOPSIS
    Create a text file action.txt from parsing Cloudformation template file

    Sample command:
    ./generateIAMAction.ps1 -TemplateFile (Get-ChildItem -File -Filter *.template.json -Path ../../jktruong+team-sentinel-taser-SharedServices-Admin.us-east-1.cdk.out | Select-Object -ExpandProperty FullName)
    ./generateIAMAction.ps1 -TemplateFile /Users/jktruong/workspace/engagements/c3e/bootstrap/jktruong+team-sentinel-taser-SharedServices-Admin.us-east-1.cdk.out/SapDomainServicesStack.template.json,cdk.out/BootstrapStack.template.json

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

param(
    [Parameter(Mandatory = $true, ValueFromPipeline = $true)]
    [string[]]$TemplateFile,

    [Parameter(Mandatory = $false, ValueFromPipeline = $false)]
    [string]$OutputDirectory = ".",

    [Parameter(Mandatory = $false, ValueFromPipeline = $false)]
    [switch]$Enhance = $false,

    [Parameter(Mandatory = $false, ValueFromPipeline = $false)]
    [string]$RoleArn,

    [Parameter(Mandatory = $false, ValueFromPipeline = $false)]
    [DateTime]$Since = (Get-Date).AddHours(-4),

    [Parameter(Mandatory = $false, ValueFromPipeline = $false)]
    [string]$Region = "us-west-1"
)


BEGIN {    
}

PROCESS {
    $processedResourceTypes = @()
    $skippedResourceTypes = @()

    $requiredActions = @()

    Write-Host "Preparing to process following files: $TemplateFile"

    foreach ( $templateFileJSONPath in $TemplateFile) {
        Write-Host -ForegroundColor DarkGreen "Processing file: $templateFileJSONPath"
        $template = Get-Content -Path $templateFileJSONPath | ConvertFrom-Json

        $resources = $template.Resources; 

        foreach ( $resource in $resources.psobject.properties) {
            $resourceType = $resource.Value.Type

            if ($resourceType.Contains("5Custom::") -or $resourceType.Contains("AWS::CDK::")) {
                Write-Warning "Skipping Type: $resourceType"
                $skippedResourceTypes += $resourceType
                continue
            }

            if ($resourceType -notcontains $skippedResourceTypes) {
                $processedResourceTypes += $resourceType;

                $eventActions = (rain build --schema $resourceType | ConvertFrom-Json).handlers
                if ($LASTEXITCODE -ne 0) {
                    Write-Warning "Unable to process: $resourceType"
                }
                elseif ($null -eq $eventActions) {
                    Write-Warning "Unable to process: $resourceType, no handlers found"
                }

                foreach ($eventAction in $eventActions.psobject.properties.Value) {
                    $removedActions = $eventAction.permissions | Where-Object { $_ -match "\." }
                    $requiredActions += $eventAction.permissions | Where-Object { $_ -notmatch "\." }
                    if ($removedActions.Count -gt 0) {
                        Write-Warning "[$resourceType]: Removed actions - $($removedActions -join ", ")"
                    }
                }
            }
        }   
    }

    if ($Enhance) {
        Write-host  "Using Enhanced generation ..."

        # Check for basic sts access
        aws sts get-caller-identity --output json 2>&1 | Out-Null
        if ($LASTEXITCODE -eq 0) {
            if ([string]::IsNullOrWhiteSpace($RoleArn)) {
                # Use the default arn found in SSM
                $RoleArn = (aws ssm get-parameter --with-decryption --region $Region --output json --name "cloudformation-admin-exec-role-arn" | ConvertFrom-Json).Parameter.Value
            }
    
            $cloudTrailArn = (aws ssm get-parameter --with-decryption --region $Region --output json --name "iam-analyzer-cloudtrail-arn" | ConvertFrom-Json).Parameter.Value
            $IamAnalyzerRoleArn = (aws ssm get-parameter --with-decryption --region $Region --output json --name "iam-analyzer-role-arn" | ConvertFrom-Json).Parameter.Value
    
            Write-Debug "CloudTrail ARN: $cloudTrailArn"
            Write-Debug "IAM Analyzer Role ARN: $IamAnalyzerRoleArn"
            Write-host "Calcuating using Role Arn: $RoleArn"
            Write-host "Starting Policy Generation ..."
    
            $cloudTrailDetails = @{
                accessRole = $IamAnalyzerRoleArn
                startTime  = $Since.ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ss.000K")
                trails     = @(@{
                        cloudTrailArn = $cloudTrailArn
                        regions       = @($Region)
                    })
            }
    
            $jobId = $null
            $queryResponse = $null
    
            while ($null -eq $jobId) {
                $queryResponse = (aws accessanalyzer start-policy-generation --region $Region --output json --policy-generation-details principalArn=$RoleArn --cloud-trail-details ($cloudTrailDetails | ConvertTo-Json -Depth 4)) | ConvertFrom-Json
                $jobId = $queryResponse.jobId;
                
                if ($null -eq $jobId) {
                    Write-Warning "Waiting for a JobID"
                    Start-Sleep -Seconds 5;
                }
                else {
                    Write-Host "Recieved Job ID - $jobId"
                }
            }
    
            # Wait for generation to complete
            $isComplete = $false
    
            while (-not $isComplete) {
                $queryResponse = aws accessanalyzer get-generated-policy --region $Region --output json --job-id $jobId | ConvertFrom-Json
                $status = $queryResponse.jobDetails.status 
                Write-host "[Job - $jobId] Query Status: $status"
                if ($status -eq "IN_PROGRESS") {
                    Write-Host "   Waiting ..."
                    Start-Sleep -Seconds 5;
                }
                elseif ($status -eq "FAILED" -or $status -eq "SUCCEEDED") {
                    $isComplete = $true
                    break;
                }
            }
            
            # Process the queryResponse
            $generatedPolicyResult = $queryResponse.generatedPolicyResult
            $generatedPolicies = $generatedPolicyResult.generatedPolicies

            Out-File -FilePath ( Join-Path -Path $OutputDirectory -ChildPath "quick_action.txt") -InputObject ($requiredActions | Sort-Object -Unique)
    
            if ($generatedPolicies.Count -gt 0) {
                Write-Host "Policy Generated ..."
    
                $generatedPolicy = ($generatedPolicies | Select-Object -First 1).policy | ConvertFrom-Json
                $generatedActions = ($generatedPolicy.Statement | Select-Object -First 1).Action
    
                Out-File -FilePath ( Join-Path -Path $OutputDirectory -ChildPath "generated_action.txt") -InputObject ($generatedActions | Sort-Object -Unique)
    
                $diffActions = $generatedActions | Where-Object { $requiredActions -notcontains $_ }
                if ($diffActions.Count -gt 0) {
                    Write-Host "Additional Actions: $($diffActions.Count)"                
                    Write-Host "  $($diffActions -join ', ' )"
                }
    
                $requiredActions += $diffActions
            } 
            else {
                Write-Host "No additional policy generated ..."
            }
        }
        else {
            Write-Error "Unable to use Enhance Param due to invalid credentials or dependencies"
        }
    }

    Out-File -FilePath ( Join-Path -Path $OutputDirectory -ChildPath "action.txt") -InputObject ($requiredActions | Sort-Object -Unique)
}

END {
}

