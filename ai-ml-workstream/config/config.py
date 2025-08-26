import yaml
from dataclasses import dataclass
from typing import List

@dataclass
class Subnet:
    subnet_id: str
    availability_zone: str

@dataclass
class Networking:
    vpc_id: str
    subnets: List[Subnet]
    security_group_id: str

@dataclass
class Permissions:
    boundary_policy_arn: str
    role_prefix: str

@dataclass
class LambdaFunctions:
    git_branch_crud: str
    git_issues_crud: str
    git_code_merge_and_push: str
    create_dynamodb_table: str
    parse_fortify_findings: str
    dynamodb_table_scan: str
    bedrock_llm_call: str
    git_file_crud: str
    verify_findings_resolved: str
    git_pr_crud: str

@dataclass
class Config:
    namespace: str
    region: str
    version: str
    networking: Networking
    lambda_functions: LambdaFunctions
    permissions: Permissions
    remediation_state_machine: str

def get_configs(config_file: str) -> Config:
    with open(config_file, 'r') as f:
        config = yaml.safe_load(f)

    networking = Networking(
        vpc_id=config['networking']['vpc_id'],
        subnets=[Subnet(**s) for s in config['networking']['subnets']],
        security_group_id=config['networking']['security_group_id']
    )

    permissions = Permissions(
        boundary_policy_arn=config['permissions']['boundary_policy_arn'],
        role_prefix=config['permissions']['role_prefix']
    )

    lambda_functions = LambdaFunctions(
        git_branch_crud=config['lambda_functions']['git_branch_crud'],
        git_issues_crud=config['lambda_functions']['git_issues_crud'],
        git_code_merge_and_push=config['lambda_functions']['git_code_merge_and_push'],
        create_dynamodb_table=config['lambda_functions']['create_dynamodb_table'],
        parse_fortify_findings=config['lambda_functions']['parse_fortify_findings'],
        dynamodb_table_scan=config['lambda_functions']['dynamodb_table_scan'],
        bedrock_llm_call=config['lambda_functions']['bedrock_llm_call'],
        git_file_crud=config['lambda_functions']['git_file_crud'],
        verify_findings_resolved=config['lambda_functions']['verify_findings_resolved'],
        git_pr_crud=config['lambda_functions']['git_pr_crud']
    )

    return Config(
        namespace=config['namespace'],
        version=config['version'],
        region=config['region'],
        networking=networking,
        lambda_functions=lambda_functions,
        permissions=permissions,
        remediation_state_machine=config['remediation_state_machine']
    )
