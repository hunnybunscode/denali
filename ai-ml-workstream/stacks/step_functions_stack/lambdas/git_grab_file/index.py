import boto3
import json
import urllib.parse
import requests
import base64

class GiteaError(Exception):
    """Custom exception for Gitea-related errors"""
    pass

class ValidationError(Exception):
    """Custom exception for input validation errors"""
    pass

def lambda_handler(event, context):
    """
    Lambda function to get the contents of a file from a Gitea repository.
    
    Expected event input:
    {
        "repo_url": "https://gitea.example.com/owner/repo.git",
        "file_path": "path/to/file",   # Required: path to the file in the repository
        "branch": "main",              # Optional, defaults to default branch if not specified
        "secret_name": "gitea/token"   # Required: name of the secret containing Gitea token
    }
    """
    try:
        # Extract parameters from event
        repo_url = event.get('repo_url')
        branch = event.get('branch')
        file_path = event.get('file_path')
        secret_name = event.get('secret_name')
        
        # Validate required parameters
        if not repo_url:
            raise ValidationError("Missing required parameter: repo_url")
        
        if not file_path:
            raise ValidationError("Missing required parameter: file_path")
        
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
        
        # Fetch file content
        file_content, file_info = get_file_content(api_base, owner, repo_name, file_path, branch, auth_token)
        
        return {
            "success": True,
            "file_path": file_path,
            "branch": branch or file_info.get('branch', 'default'),
            "repo": {
                "owner": owner,
                "name": repo_name
            },
            "content": file_content,
            "metadata": {
                "sha": file_info.get('sha'),
                "size": file_info.get('size'),
                "encoding": file_info.get('encoding')
            }
        }
    
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

def get_file_content(api_base, owner, repo_name, file_path, branch, auth_token):
    """Get content of a file from a Git repository"""
    print(f"Getting content for file {file_path} from {owner}/{repo_name}, branch {branch or 'default'}")
    
    # Set up headers for API requests
    headers = {
        'Authorization': f'token {auth_token}',
        'Accept': 'application/json'
    }
    
    # Build the API URL for the contents endpoint
    contents_url = f"{api_base}/repos/{owner}/{repo_name}/contents/{file_path}"
    
    # Add branch parameter if specified
    params = {}
    if branch:
        params['ref'] = branch
    
    # Make the API request
    response = requests.get(contents_url, headers=headers, params=params)
    
    # Log response details
    print(f"Response status code: {response.status_code}")
    
    if response.status_code == 404:
        raise GiteaError(f"File not found: {file_path}")
        
    if response.status_code != 200:
        raise GiteaError(f"Failed to get file content: {response.text}")
    
    # Parse the response
    content_data = response.json()
    
    # Check if we got a directory instead of a file
    if isinstance(content_data, list):
        raise ValidationError(f"Path is a directory, not a file: {file_path}")
    
    # Get the file content (usually base64 encoded)
    file_content = ""
    if content_data.get('encoding') == 'base64':
        try:
            file_content = base64.b64decode(content_data.get('content', '')).decode('utf-8')
        except UnicodeDecodeError:
            # Handle binary files
            file_content = base64.b64decode(content_data.get('content', '')).hex()
            content_data['is_binary'] = True
    else:
        file_content = content_data.get('content', '')
    
    file_info = {
        'sha': content_data.get('sha'),
        'size': content_data.get('size'),
        'encoding': content_data.get('encoding'),
        'is_binary': content_data.get('is_binary', False)
    }
    
    return file_content, file_info

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