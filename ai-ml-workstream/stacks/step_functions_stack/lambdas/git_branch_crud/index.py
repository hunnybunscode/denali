import boto3
import json
import urllib.parse
import requests

TIMEOUT = (10, 15) # 10s for connect, 15s for read

class GiteaError(Exception):
    """Custom exception for Gitea-related errors"""
    pass

class ValidationError(Exception):
    """Custom exception for input validation errors"""
    pass

def lambda_handler(event, context):
    """
    Lambda function to perform CRUD operations on Git branches in a Gitea repository.
    Can handle either a single operation object or a list of operation objects.
    
    Expected event input (single operation):
    {
        "operation": "create|read|list|update|delete",
        "repo_url": "https://gitea.example.com/owner/repo.git",
        "base_branch": "main",           # Required for 'create'
        "branch_name": "feature-branch",  # Required for 'create', 'read', 'update', 'delete'
        "new_branch_name": "new-name",    # Required for 'update'
        "secret_name": "gitea/token"
    }
    
    Or list of operations:
    [
        {
            "operation": "delete",
            "repo_url": "https://gitea.example.com/owner/repo1.git",
            "branch_name": "feature-branch",
            "secret_name": "gitea/token"
        },
        {
            "operation": "delete",
            "repo_url": "https://gitea.example.com/owner/repo2.git", 
            "branch_name": "feature-branch",
            "secret_name": "gitea/token"
        }
    ]
    """
    # Check if input is a list of operations or a single operation
    if isinstance(event, list):
        results = []
        for operation_event in event:
            try:
                result = process_single_operation(operation_event, context)
                results.append(result)
            except Exception as e:
                print(f"Error processing operation: {str(e)}")
                import traceback
                traceback.print_exc()
                # Add error result to the results list
                results.append({
                    "success": False,
                    "operation": operation_event.get('operation', 'unknown'),
                    "error": str(e),
                    "repo_url": operation_event.get('repo_url', 'unknown')
                })
        return results
    else:
        # Process single operation
        return process_single_operation(event, context)

def process_single_operation(event, context):
    """Process a single operation event"""
    try:
        # Extract parameters from event
        operation = event.get('operation', 'create').lower()
        repo_url = event.get('repo_url')
        secret_name = event.get('secret_name')
        
        # Validate required parameters
        if not repo_url:
            raise ValidationError("Missing required parameter: repo_url")
        
        if not secret_name:
            raise ValidationError("Missing required parameter: secret_name")
        
        # Parse repository URL
        parsed_url = urllib.parse.urlparse(repo_url)
        path_parts = parsed_url.path.strip('/').split('/')
        
        if len(path_parts) < 2:
            raise ValidationError(f"Invalid repository URL format: {repo_url}")
        
        owner = path_parts[0]
        repo_name = path_parts[1].replace('.git', '')
        
        # Build base API URL
        api_base = f"{parsed_url.scheme}://{parsed_url.netloc}/api/v1"
        
        # Get authentication token
        auth_token = get_gitea_token_from_secrets(secret_name)
        if not auth_token:
            raise GiteaError(f"Failed to retrieve Gitea token from secret: {secret_name}")
        
        # Create API client context
        api_context = {
            'api_base': api_base,
            'owner': owner,
            'repo_name': repo_name,
            'auth_token': auth_token
        }
        
        # Execute the requested operation
        if operation == 'create':
            return create_branch(event, api_context)
        elif operation == 'read':
            return get_branch(event, api_context)
        elif operation == 'list':
            return list_branches(event, api_context)
        elif operation == 'update':
            return update_branch(event, api_context)
        elif operation == 'delete':
            return delete_branch(event, api_context)
        else:
            raise ValidationError(f"Invalid operation: {operation}")
    
    except ValidationError as e:
        print(f"Validation error: {str(e)}")
        raise
    except GiteaError as e:
        print(f"Gitea error: {str(e)}")
        raise
    except requests.exceptions.RequestException as e:
        print(f"HTTP request error: {str(e)}")
        raise GiteaError(f"Failed to communicate with Gitea API: {str(e)}")
    except Exception as e:
        print(f"Unexpected error: {str(e)}")
        import traceback
        traceback.print_exc()
        raise

def create_branch(event, api_context):
    """Create a new branch in a repository"""
    base_branch = event.get('base_branch')
    branch_name = event.get('branch_name')
    create_behavior = event.get('create_behavior')

    # Validate required parameters
    if not branch_name:
        raise ValidationError("Missing required parameter: branch_name")
    
    if not base_branch:
        raise ValidationError("Missing required parameter: base_branch")
    
    print(f"Creating branch {branch_name} from {base_branch} in {api_context['owner']}/{api_context['repo_name']} with behavior {create_behavior}")
    
    # Set up headers for API requests
    headers = {
        'Authorization': f'token {api_context["auth_token"]}',
        'Content-Type': 'application/json'
    }
    
    
    if create_behavior and create_behavior=='delete_if_exists':
        # Does the branch already exist?  If so delete it
        try:
            get_branch_result = get_branch(event, api_context)
            if get_branch_result["success"]==True:
                print("The branch already exists, will delete it")
                try:
                    delete_branch(event, api_context)
                except GiteaError as ex:
                    print(f"Error deleting existing branch. Errors {ex}")
        except GiteaError as ex:
            print(f"Error getting branch. Exception: {ex}")
    
    # Create the branch using the correct endpoint
    branch_url = f"{api_context['api_base']}/repos/{api_context['owner']}/{api_context['repo_name']}/branches"
    payload = {
        "new_branch_name": branch_name,
        "old_branch_name": base_branch
    }
    
    print(f"Creating branch with payload: {json.dumps(payload)}")
    print(f"Using URL: {branch_url}")
    
    response = requests.post(branch_url, headers=headers, json=payload, timeout=TIMEOUT)
    
    # Log response details
    print(f"Response status code: {response.status_code}")
    try:
        print(f"Response JSON: {json.dumps(response.json(), indent=2)}")
    except:
        print(f"Response text: {response.text}")
    
    if response.status_code != 201:
        raise GiteaError(f"Failed to create branch: {response.text}")
    
    return {
        "success": True,
        "operation": "create",
        "branch": branch_name,
        "base_branch": base_branch,
        "repo": {
            "owner": api_context['owner'],
            "name": api_context['repo_name']
        }
    }

def get_branch(event, api_context):
    """Get information about a specific branch"""
    branch_name = event.get('branch_name')
    
    # Validate required parameters
    if not branch_name:
        raise ValidationError("Missing required parameter: branch_name")
    
    print(f"Getting information for branch {branch_name} in {api_context['owner']}/{api_context['repo_name']}")
    
    # Set up headers for API requests
    headers = {
        'Authorization': f'token {api_context["auth_token"]}'
    }
    
    # Get branch information using the API
    branch_url = f"{api_context['api_base']}/repos/{api_context['owner']}/{api_context['repo_name']}/branches/{branch_name}"
    
    response = requests.get(branch_url, headers=headers, timeout=TIMEOUT)
    
    # Log response details
    print(f"Response status code: {response.status_code}")
    
    if response.status_code == 404:
        return {
            "success": False,
            "operation": "read",
            "message": f"Branch {branch_name} not found"
        }
    
    if response.status_code != 200:
        raise GiteaError(f"Failed to get branch information: {response.text}")
    
    branch_data = response.json()
    
    return {
        "success": True,
        "operation": "read",
        "branch": branch_data,
        "repo": {
            "owner": api_context['owner'],
            "name": api_context['repo_name']
        }
    }

def list_branches(event, api_context):
    """List all branches in a repository"""
    print(f"Listing branches in {api_context['owner']}/{api_context['repo_name']}")
    
    # Set up headers for API requests
    headers = {
        'Authorization': f'token {api_context["auth_token"]}'
    }
    
    # List branches using the API
    branches_url = f"{api_context['api_base']}/repos/{api_context['owner']}/{api_context['repo_name']}/branches"
    
    response = requests.get(branches_url, headers=headers, timeout=TIMEOUT)
    
    # Log response details
    print(f"Response status code: {response.status_code}")
    
    if response.status_code != 200:
        raise GiteaError(f"Failed to list branches: {response.text}")
    
    branches = response.json()
    
    return {
        "success": True,
        "operation": "list",
        "branches": branches,
        "repo": {
            "owner": api_context['owner'],
            "name": api_context['repo_name']
        }
    }

def update_branch(event, api_context):
    """Rename a branch in the repository"""
    branch_name = event.get('branch_name')
    new_branch_name = event.get('new_branch_name')
    
    # Validate required parameters
    if not branch_name:
        raise ValidationError("Missing required parameter: branch_name")
    
    if not new_branch_name:
        raise ValidationError("Missing required parameter: new_branch_name")
    
    print(f"Renaming branch from {branch_name} to {new_branch_name} in {api_context['owner']}/{api_context['repo_name']}")
    
    # Set up headers for API requests
    headers = {
        'Authorization': f'token {api_context["auth_token"]}',
        'Content-Type': 'application/json'
    }
    
    # In Gitea, there's no direct API to rename a branch, so we need to:
    # 1. Create a new branch from the old one
    # 2. Delete the old branch
    
    # First, get the SHA of the old branch
    branch_url = f"{api_context['api_base']}/repos/{api_context['owner']}/{api_context['repo_name']}/branches/{branch_name}"
    response = requests.get(branch_url, headers=headers, timeout=TIMEOUT)
    
    if response.status_code != 200:
        raise GiteaError(f"Failed to get branch information: {response.text}")
    
    branch_data = response.json()
    commit_sha = branch_data['commit']['id']
    
    # Create the new branch
    create_url = f"{api_context['api_base']}/repos/{api_context['owner']}/{api_context['repo_name']}/branches"
    create_payload = {
        "new_branch_name": new_branch_name,
        "old_branch_name": branch_name
    }
    
    create_response = requests.post(create_url, headers=headers, json=create_payload, timeout=TIMEOUT)
    
    if create_response.status_code != 201:
        raise GiteaError(f"Failed to create new branch: {create_response.text}")
    
    # Delete the old branch
    delete_url = f"{api_context['api_base']}/repos/{api_context['owner']}/{api_context['repo_name']}/branches/{branch_name}"
    delete_response = requests.delete(delete_url, headers=headers, timeout=TIMEOUT)
    
    if delete_response.status_code not in (200, 204):
        # If deletion fails, we should report but not fail the whole operation
        print(f"Warning: Could not delete old branch: {delete_response.text}")
    
    return {
        "success": True,
        "operation": "update",
        "old_branch": branch_name,
        "new_branch": new_branch_name,
        "repo": {
            "owner": api_context['owner'],
            "name": api_context['repo_name']
        }
    }

def delete_branch(event, api_context):
    """Delete a branch from the repository"""
    branch_name = event.get('branch_name')
    
    # Validate required parameters
    if not branch_name:
        raise ValidationError("Missing required parameter: branch_name")
    
    print(f"Deleting branch {branch_name} from {api_context['owner']}/{api_context['repo_name']}")
    
    # Set up headers for API requests
    headers = {
        'Authorization': f'token {api_context["auth_token"]}'
    }
    
    # Delete the branch using the API
    branch_url = f"{api_context['api_base']}/repos/{api_context['owner']}/{api_context['repo_name']}/branches/{branch_name}"
    
    response = requests.delete(branch_url, headers=headers, timeout=TIMEOUT) 
    
    # Log response details
    print(f"Response status code: {response.status_code}")
    
    if response.status_code not in (200, 204):
        raise GiteaError(f"Failed to delete branch: {response.text}")
    
    return {
        "success": True,
        "operation": "delete",
        "branch": branch_name,
        "repo": {
            "owner": api_context['owner'],
            "name": api_context['repo_name']
        }
    }

def get_gitea_token_from_secrets(secret_name):
    """
    Retrieve Gitea token from AWS Secrets Manager.
    """
    if not secret_name:
        raise ValidationError("No secret name provided")
        
    session = boto3.session.Session()
    secrets_client = session.client(service_name='secretsmanager')
    
    try:
        get_secret_value_response = secrets_client.get_secret_value(SecretId=secret_name)
        if 'SecretString' in get_secret_value_response:
            secret = json.loads(get_secret_value_response['SecretString'])
            token = secret.get('token') or secret.get('GITEA_TOKEN') or secret.get('giteaToken')
            if not token:
                raise ValidationError("Token not found in secret")
            return token
    except Exception as e:
        print(f"Error retrieving secret {secret_name}: {str(e)}")
        raise GiteaError(f"Failed to retrieve secret: {str(e)}")
    
    raise GiteaError("Failed to retrieve token from secret")