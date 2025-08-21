# Custom Bootstrap and Naming Requirements

## Overview
The customer environment requires specific naming conventions and permissions boundaries for all IAM roles. This document outlines the changes needed to comply with these requirements.

## Requirements Summary
1. **Role Naming**: All IAM roles must be prefixed with "AFC2S"
2. **Permissions Boundary**: All roles must have the ProjAdminPolicy permissions boundary attached
3. **Custom Bootstrap**: CDK bootstrap roles need to be renamed and configured with permissions boundaries

## 1. Custom CDK Bootstrap Requirements

### Current Challenge
- Default CDK bootstrap creates roles with standard names
- Customer environment requires "AFC2S" prefix and permissions boundaries
- Need custom bootstrap template with renamed roles

### Required Changes
1. **Custom Bootstrap Template**: Create a modified bootstrap template with:
   - Renamed roles (AFC2S prefix)
   - Permissions boundaries attached to all roles
   - Compatible with default CDK synthesizer

2. **Bootstrap Roles to Rename**:
   ```
   Default Name                    → Custom Name
   cdk-hnb659fds-cfn-exec-role-*   → AFC2S-cdk-hnb659fds-cfn-exec-role-*
   cdk-hnb659fds-deploy-role-*     → AFC2S-cdk-hnb659fds-deploy-role-*
   cdk-hnb659fds-file-publishing-* → AFC2S-cdk-hnb659fds-file-publishing-*
   cdk-hnb659fds-image-publishing-*→ AFC2S-cdk-hnb659fds-image-publishing-*
   cdk-hnb659fds-lookup-role-*     → AFC2S-cdk-hnb659fds-lookup-role-*
   ```

3. **Permissions Boundary**: Attach `arn:aws-us-gov:iam::YOUR-ACCOUNT-ID:policy/ProjAdminPolicy` to all roles

## 2. Application Code Changes Required

### Lambda Stack Changes
**File**: `stacks/lambda_stack.py`

```python
# Current
lambda_role = iam.Role(
    self,
    f"{config.namespace}-{config.version}-LambdaRole",
    assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
    managed_policies=[...]
)

# Required
lambda_role = iam.Role(
    self,
    f"AFC2S-{config.namespace}-{config.version}-LambdaRole",
    role_name=f"AFC2S-{config.namespace}-{config.version}-LambdaRole",
    assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
    managed_policies=[...],
    permissions_boundary=iam.ManagedPolicy.from_managed_policy_arn(
        self, "LambdaPermissionsBoundary",
        "arn:aws-us-gov:iam::YOUR-ACCOUNT-ID:policy/ProjAdminPolicy"
    )
)
```

### Step Functions Stack Changes
**File**: `stacks/step_functions_stack/step_functions_stack.py`

```python
# Current
state_machine_role = iam.Role(
    self,
    f"{config.namespace}-{config.version}-StepFunctionRole",
    assumed_by=iam.ServicePrincipal("states.amazonaws.com")
)

# Required
state_machine_role = iam.Role(
    self,
    f"AFC2S-{config.namespace}-{config.version}-StepFunctionRole",
    role_name=f"AFC2S-{config.namespace}-{config.version}-StepFunctionRole",
    assumed_by=iam.ServicePrincipal("states.amazonaws.com"),
    permissions_boundary=iam.ManagedPolicy.from_managed_policy_arn(
        self, "StepFunctionPermissionsBoundary",
        "arn:aws-us-gov:iam::YOUR-ACCOUNT-ID:policy/ProjAdminPolicy"
    )
)
```

### Configuration Changes
**File**: `config/deployment_config.yaml`

Add permissions boundary configuration:
```yaml
permissions:
  boundary_policy_arn: "arn:aws-us-gov:iam::YOUR-ACCOUNT-ID:policy/ProjAdminPolicy"
  role_prefix: "AFC2S"
```

**File**: `config/config.py`

Add new configuration fields:
```python
@dataclass
class Permissions:
    boundary_policy_arn: str
    role_prefix: str

@dataclass
class Config:
    # ... existing fields ...
    permissions: Permissions
```

## 3. Deployment Process Changes

### Bootstrap Command
```bash
# Instead of standard bootstrap
cdk bootstrap

# Use custom bootstrap template
cdk bootstrap --template custom-bootstrap-template.yaml
```

### Deploy Command
```bash
# Use default synthesizer (not legacy)
cdk deploy --context config_file=config/deployment_config.yaml
```

## 4. Files That Need Modification

### Core Infrastructure
- [ ] `stacks/lambda_stack.py` - Add AFC2S prefix and permissions boundary to Lambda role
- [ ] `stacks/step_functions_stack/step_functions_stack.py` - Add AFC2S prefix and permissions boundary to Step Functions role

### Configuration
- [ ] `config/deployment_config.yaml` - Add permissions boundary and prefix configuration
- [ ] `config/config.py` - Add Permissions dataclass and fields

### Bootstrap
- [ ] Create `custom-bootstrap-template.yaml` - Modified CDK bootstrap template
- [ ] Update `DEPLOYMENT_GUIDE.md` - Document custom bootstrap process

### Documentation
- [ ] `DEPLOYMENT_GUIDE.md` - Add custom bootstrap instructions
- [ ] `CLI_TESTING_COMMANDS.md` - Update with custom role names

## 5. Testing Considerations

### Role Name Updates
All CLI commands and references need to use the new role names:
```bash
# Old
aws iam get-role --role-name "your-name-v1-LambdaRole"

# New
aws iam get-role --role-name "AFC2S-your-name-v1-LambdaRole"
```

### Cross-Account References
If using cross-account deployment, ensure the AFC2S prefix is used in:
- Step Function JSON definitions
- Cross-account trust relationships
- Resource ARN references

## 6. Implementation Priority

### Phase 1: Core Changes
1. Update Lambda stack with AFC2S prefix and permissions boundary
2. Update Step Functions stack with AFC2S prefix and permissions boundary
3. Update configuration files

### Phase 2: Bootstrap
1. Create custom bootstrap template
2. Test bootstrap process
3. Update deployment documentation

### Phase 3: Validation
1. Test deployment with new naming
2. Verify permissions boundary compliance
3. Update CLI testing commands

## 7. Risks and Mitigations

### Risk: Bootstrap Complexity
**Mitigation**: Get the working bootstrap template from colleague who has done this before

### Risk: Role Name References
**Mitigation**: Systematic update of all role references in code and documentation

### Risk: Permissions Boundary Conflicts
**Mitigation**: Test permissions boundary compatibility with required AWS services

## Next Steps
1. Obtain working custom bootstrap template from colleague
2. Implement Phase 1 changes (core infrastructure)
3. Test deployment in development environment
4. Update documentation and CLI commands