#!/usr/bin/env python3
"""
Script to check if the required AFC2S bootstrap roles exist in the AWS account.
"""

import boto3
import sys
from botocore.exceptions import ClientError, NoCredentialsError

def check_bootstrap_roles():
    """Check if the required AFC2S bootstrap roles exist."""

    print("🔍 Checking for AFC2S bootstrap roles...")

    try:
        # Get current account and region
        sts = boto3.client('sts')
        account_info = sts.get_caller_identity()
        account_id = account_info['Account']

        # Get current region
        session = boto3.Session()
        region = session.region_name or 'us-gov-west-1'

        print(f"📍 Account: {account_id}")
        print(f"📍 Region: {region}")
        print()

        # Expected role names with v1 qualifier
        expected_roles = [
            f"AFC2S-cdk-v1-cfn-exec-role-{account_id}-{region}",
            f"AFC2S-cdk-v1-deploy-role-{account_id}-{region}",
            f"AFC2S-cdk-v1-file-pub-role-{account_id}-{region}",
            f"AFC2S-cdk-v1-image-pub-role-{account_id}-{region}",
            f"AFC2S-cdk-v1-lookup-role-{account_id}-{region}"
        ]

        iam = boto3.client('iam')

        print("Checking for required bootstrap roles:")
        all_exist = True

        for role_name in expected_roles:
            try:
                response = iam.get_role(RoleName=role_name)
                role = response['Role']

                # Check permissions boundary
                permissions_boundary = role.get('PermissionsBoundary', {})
                boundary_arn = permissions_boundary.get('PermissionsBoundaryArn', 'None')

                print(f"✅ {role_name}")
                print(f"   Permissions Boundary: {boundary_arn}")

                # Verify it's the expected ProjAdminPolicy
                if 'ProjAdminPolicy' in boundary_arn:
                    print(f"   ✅ Correct permissions boundary")
                else:
                    print(f"   ⚠️  Unexpected permissions boundary")

            except ClientError as e:
                if e.response['Error']['Code'] == 'NoSuchEntity':
                    print(f"❌ {role_name} - NOT FOUND")
                    all_exist = False
                else:
                    print(f"❌ {role_name} - Error: {e}")
                    all_exist = False

            print()

        if all_exist:
            print("🎉 All required AFC2S bootstrap roles exist!")
            print("✅ Ready for CDK deployment with v1 qualifier")
        else:
            print("⚠️  Some bootstrap roles are missing.")
            print("💡 You may need to deploy the custom bootstrap first:")
            print("   aws cloudformation deploy \\")
            print("     --template-file bootstrap/custom-bootstrap-template.yaml \\")
            print("     --stack-name CDKToolkit \\")
            print("     --parameter-overrides file://bootstrap/bootstrap-parameters-projadmin.json \\")
            print("     --capabilities CAPABILITY_NAMED_IAM")

        return all_exist

    except NoCredentialsError:
        print("❌ AWS credentials not configured")
        print("💡 Please configure AWS CLI credentials first")
        return False
    except Exception as e:
        print(f"❌ Error checking bootstrap roles: {e}")
        return False

if __name__ == "__main__":
    success = check_bootstrap_roles()
    sys.exit(0 if success else 1)