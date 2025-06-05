import os
import subprocess
import logging
import yaml


LOG_LEVELS = {
    "DEBUG": logging.DEBUG,
    "INFO": logging.INFO,
    "WARNING": logging.WARNING,
    "ERROR": logging.ERROR,
    "CRITICAL": logging.CRITICAL,
}


# Fetch Debugging level based from ENVIRONMENT Variable DEBUG_LEVEL
DEBUG_LEVEL = os.environ.get("DEBUG_LEVEL")

LOG_LEVEL = LOG_LEVELS.get(DEBUG_LEVEL, logging.INFO)
logging.basicConfig(level=LOG_LEVEL, force=True)


# Create the cdk bootstrap yaml file and parse it
def create_cdk_bootstrap_yaml_file():
    logging.info("Creating cdk bootstrap yaml file")
    subprocess.call("cdk bootstrap --show-template > cdk.output.yaml", env=os.environ.copy(), shell=True)
    logging.debug("cdk bootstrap yaml file created")


def parse_cdk_bootstrap_yaml_file():
    logging.debug("Parsing cdk bootstrap yaml file")
    with open("cdk.output.yaml", "r") as file:
        data = yaml.safe_load(file)
    return data


# Check if cdk bootstrap yaml file exists
# if not os.path.exists("cdk.output.yaml"):
create_cdk_bootstrap_yaml_file()

# Parse yaml file with PyYAML
logging.info("Parsing cdk bootstrap yaml file")
bootstrap_data = parse_cdk_bootstrap_yaml_file()

# Read the environment variable
logging.debug("Reading environment variables")

# Get the environment variable
environment = os.environ.get("ENVIRONMENT") or "dev"
logging.info(f"Environment: {environment}")

# Read the configuration yaml file based on the environment variable
logging.debug("Reading configuration yaml file")
with open(f"env/{environment}/configuration.yaml", "r") as file:
    config = yaml.safe_load(file)

logging.debug("Configuration yaml file read")
logging.info(f"Configuration: {config}")
environment_config = config.get("environment", {})
logging.debug(f"Environment Config: {environment_config}")

environment_name = environment_config.get("name")
environment_region = environment_config.get("region")
environment_account = environment_config.get("account")
environment_iam = environment_config.get("iam", {})
environment_execute = environment_config.get("execute", True)
environment_qualifier = environment_config.get("qualifier", "a")

# Check if region and account is defined
if not environment_region or not environment_account:
    logging.error("Region and account must be defined")
    exit(1)


# Check if environment_iam is empty
if not environment_iam:
    logging.info("No IAM configuration found")
else:
    iam_prefix = environment_iam.get("prefix", None)
    iam_permission_boundary_arn = environment_iam.get("permissionBoundaryArn", None)

    # Parse bootstrap data for all iam roles and then update them
    resources = bootstrap_data.get("Resources", {}).items()

    # Get all resources who has Type: AWS::IAM::Role
    iam_roles = [resource for resource in resources if resource[1].get("Type") == "AWS::IAM::Role"]
    # logging.info(f"IAM Roles: {iam_roles}")

    if iam_prefix is not None:
        logging.info(f"Updating Role Name with Prefix - {iam_prefix}")
        # Get the old Role Name, Add prefix to old role name and update
        for resource_name, resource in iam_roles:
            role_name = resource["Properties"]["RoleName"]["Fn::Sub"]

            role_name_short = role_name.replace("cdk-${Qualifier}-", "")
            role_name_short = role_name_short.replace("-${AWS::AccountId}-${AWS::Region}", "")
            test_role_name = role_name.replace("${Qualifier}", "a")
            test_role_name = test_role_name.replace("${AWS::Region}", environment_region)
            test_role_name = test_role_name.replace("${AWS::AccountId}", environment_account)
            test_full_role_name = f"{iam_prefix}-{test_role_name}"

            new_role_name = f"{iam_prefix}-{role_name}"

            # Check if Permission Boundary ARN is defined
            if iam_permission_boundary_arn is not None:
                resource["Properties"]["PermissionsBoundary"] = iam_permission_boundary_arn

            # Check the length of the new role name is less than 64 characters
            if len(test_full_role_name) > 64:
                logging.warning(f"Role Name {new_role_name} is greater than 64 characters")
                logging.warning(f"Role Name {new_role_name} will be truncated to 64 characters")

                role_name_parts = role_name_short.split("-")
                role_name_shorten = "".join(part[0] for part in role_name_parts)
                new_role_name = new_role_name.replace(role_name_short, role_name_shorten)

                logging.warning(f"Role Name {new_role_name} will be updated")

            resource["Properties"]["RoleName"]["Fn::Sub"] = new_role_name
            logging.info(f"Updated Role Name - {role_name} to {new_role_name}")

# Check is region starts with us-iso
if environment_region.startswith("us-iso"):
    logging.info("Region starts with us-iso, removing known issues")

    # Remove the ImageTagMutability and ImageScanningConfiguration properties
    container_assets_repository = bootstrap_data["Resources"]["ContainerAssetsRepository"]["Properties"]
    container_assets_repository.pop("ImageTagMutability", None)
    container_assets_repository.pop("ImageScanningConfiguration", None)

# Write the cdk bootstrap yaml file

logging.debug("Writing cdk bootstrap yaml file")
with open("cdk.output.yaml", "w") as file:
    yaml.dump(bootstrap_data, file)
    logging.debug("cdk bootstrap yaml file written")

if iam_permission_boundary_arn is not None:
    logging.info(f"Using Permission Boundary ARN: {iam_permission_boundary_arn}")

logging.info("Deploying cdk bootstrap yaml file")

command = f"aws cloudformation deploy --template-file cdk.output.yaml --stack-name CDKToolkit-Bootstrap-{environment_name} --capabilities CAPABILITY_IAM CAPABILITY_NAMED_IAM --region {environment_region} --parameter-overrides Qualifier={environment_qualifier} --tags Environment={environment_name}"
logging.info(f"Command:\n  {command}")

if environment_execute:
    logging.info("Executing command ...")
    subprocess.call(command, env=os.environ.copy(), shell=True)
