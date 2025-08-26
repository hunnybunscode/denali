import boto3
import json
import urllib.parse
import requests
import base64

TIMEOUT = (10, 15) # 10s for connect, 15s for read

class GiteaError(Exception):
    """Custom exception for Gitea-related errors"""
    pass

class ValidationError(Exception):
    """Custom exception for input validation errors"""
    pass

def lambda_handler(event, context):
    """
    Lambda function to update a file in a specific branch in a Gitea repository.
    
    Expected event input:
    {
        "repo_url": "https://gitea.example.com/owner/repo.git",
        "branch_name": "feature-branch",  # The branch where the file exists
        "file_path": "path/to/file.txt",  # Path to the file in the repository
        "content": "New content for the file", # New content for the file
        "commit_message": "Update file content", # Commit message
        "secret_name": "gitea/token" # Secret name where Gitea token is stored
    }
    """
    try:
        # Extract parameters from event
        repo_url = event.get('repo_url')
        branch_name = event.get('branch_name')
        file_path = event.get('file_path')
        content = event.get('content')
        commit_message = event.get('commit_message', 'Update file via API')
        secret_name = event.get('secret_name')
        
        # Validate required parameters
        if not repo_url:
            raise ValidationError("Missing required parameter: repo_url")
        if not branch_name:
            raise ValidationError("Missing required parameter: branch_name")
        if not file_path:
            raise ValidationError("Missing required parameter: file_path")
        if content is None:  # Allow empty string as valid content
            raise ValidationError("Missing required parameter: content")
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
        
        # Update the file in the repository
        return update_file(file_path, content, commit_message, branch_name, api_context)
    
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

def update_file(file_path, content, commit_message, branch_name, api_context):
    """Update a file in the repository"""
    print(f"Updating file {file_path} in branch {branch_name} of {api_context['owner']}/{api_context['repo_name']}")
    
    # Set up headers for API requests
    headers = {
        'Authorization': f'token {api_context["auth_token"]}',
        'Content-Type': 'application/json'
    }
    
    # First, check if the file exists and get its SHA if it does
    get_file_url = f"{api_context['api_base']}/repos/{api_context['owner']}/{api_context['repo_name']}/contents/{file_path}?ref={branch_name}"
    get_response = requests.get(get_file_url, headers=headers, timeout=TIMEOUT)
    
    sha = None
    if get_response.status_code == 200:
        # File exists, get its SHA
        file_data = get_response.json()
        sha = file_data.get('sha')
    elif get_response.status_code != 404:
        # Some other error occurred
        raise GiteaError(f"Failed to check file existence: {get_response.text}")
    
    # Update or create the file using the API
    update_url = f"{api_context['api_base']}/repos/{api_context['owner']}/{api_context['repo_name']}/contents/{file_path}"
    
    # Base64 encode the content
    content_bytes = content.encode('utf-8')
    base64_content = base64.b64encode(content_bytes).decode('utf-8')
    
    payload = {
        "message": commit_message,
        "content": base64_content,
        "branch": branch_name
    }
    
    if sha:
        payload["sha"] = sha
    
    print(f"Updating file with payload: {json.dumps({**payload, 'content': '(content in base64)'})}") 
    
    response = requests.put(update_url, headers=headers, json=payload, timeout=TIMEOUT)
    
    # Log response details
    print(f"Response status code: {response.status_code}")
    
    if response.status_code not in (200, 201):
        raise GiteaError(f"Failed to update file: {response.text}")
    
    response_data = response.json()
    
    return {
        "success": True,
        "operation": "update_file",
        "file_path": file_path,
        "branch": branch_name,
        "commit": {
            "message": commit_message,
            "sha": response_data.get('commit', {}).get('sha')
        },
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