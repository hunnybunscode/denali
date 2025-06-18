import boto3
import json
import urllib.parse
import requests

class GiteaError(Exception):
    """Custom exception for Gitea-related errors"""
    pass

class ValidationError(Exception):
    """Custom exception for input validation errors"""
    pass

def lambda_handler(event, context):
    """
    Lambda function to perform CRUD operations on pull requests in a Gitea repository.
    
    Expected event input:
    {
        "operation": "create|read|list|update|close|merge",
        "repo_url": "https://gitea.example.com/owner/repo.git",
        "secret_name": "gitea/token",
        
        // Fields for create:
        "source_branch": "feature-branch",  // Source branch containing changes
        "target_branch": "main",            // Target branch for merging (typically main)
        "title": "Add new feature",         // PR title
        "description": "This PR adds...",   // PR description (optional)
        "labels": ["enhancement", "bug"],   // Labels to apply (optional)
        "assignees": ["username1"],         // Assignees for the PR (optional)
        
        // Fields for read, update, close, merge:
        "pr_number": 123,                   // PR number to read, update or close
        
        // Additional fields for update:
        "new_title": "Updated title",       // New PR title (optional for update)
        "new_description": "Updated desc",  // New PR description (optional for update)
        "new_target_branch": "dev",         // New target branch (optional for update)
        
        // Fields for list:
        "state": "open",                    // Filter PRs by state: open|closed|all (optional)
        "sort": "created",                  // Sort by: oldest|recentupdate|leastupdate|mostcomment|leastcomment|priority (optional)
        "limit": 10                         // Limit number of PRs returned (optional)
    }
    """
    try:
        # Extract parameters from event
        operation = event.get('operation', 'read').lower()
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
            return create_pull_request(event, api_context)
        elif operation == 'read':
            return get_pull_request(event, api_context)
        elif operation == 'list':
            return list_pull_requests(event, api_context)
        elif operation == 'update':
            return update_pull_request(event, api_context)
        elif operation == 'close':
            return close_pull_request(event, api_context)
        elif operation == 'merge':
            return merge_pull_request(event, api_context)
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

def create_pull_request(event, api_context):
    """Create a new pull request"""
    # Extract parameters
    source_branch = event.get('source_branch')
    target_branch = event.get('target_branch')
    title = event.get('title')
    description = event.get('description', '')
    labels = event.get('labels', [])
    assignees = event.get('assignees', [])
    
    # Validate required parameters
    if not source_branch:
        raise ValidationError("Missing required parameter: source_branch")
    if not target_branch:
        raise ValidationError("Missing required parameter: target_branch")
    if not title:
        raise ValidationError("Missing required parameter: title")
    
    print(f"Creating PR from {source_branch} into {target_branch} in {api_context['owner']}/{api_context['repo_name']}")
    
    # Set up headers for API requests
    headers = {
        'Authorization': f'token {api_context["auth_token"]}',
        'Content-Type': 'application/json'
    }
    
    # Create the pull request using the API
    pr_url = f"{api_context['api_base']}/repos/{api_context['owner']}/{api_context['repo_name']}/pulls"
    
    # Prepare payload
    payload = {
        "head": source_branch,
        "base": target_branch,
        "title": title,
        "body": description
    }
    
    print(f"Creating PR with payload: {json.dumps(payload)}")
    
    # Create the PR
    response = requests.post(pr_url, headers=headers, json=payload)
    
    # Log response details
    print(f"Response status code: {response.status_code}")
    
    if response.status_code not in (200, 201):
        raise GiteaError(f"Failed to create pull request: {response.text}")
    
    pr_data = response.json()
    pr_number = pr_data.get('number')
    
    # If PR was created successfully and labels were provided, add them
    if pr_number and labels:
        add_labels_to_pr(pr_number, labels, api_context)
    
    # If PR was created successfully and assignees were provided, add them
    if pr_number and assignees:
        add_assignees_to_pr(pr_number, assignees, api_context)
    
    return {
        "success": True,
        "operation": "create",
        "pull_request": {
            "number": pr_number,
            "url": pr_data.get('html_url'),
            "title": title,
            "source_branch": source_branch,
            "target_branch": target_branch
        },
        "repo": {
            "owner": api_context['owner'],
            "name": api_context['repo_name']
        }
    }

def get_pull_request(event, api_context):
    """Get details of a specific pull request"""
    # Extract parameters
    pr_number = event.get('pr_number')
    
    # Validate required parameters
    if not pr_number:
        raise ValidationError("Missing required parameter: pr_number")
    
    print(f"Getting PR #{pr_number} in {api_context['owner']}/{api_context['repo_name']}")
    
    # Set up headers for API requests
    headers = {
        'Authorization': f'token {api_context["auth_token"]}'
    }
    
    # Get the pull request using the API
    pr_url = f"{api_context['api_base']}/repos/{api_context['owner']}/{api_context['repo_name']}/pulls/{pr_number}"
    
    response = requests.get(pr_url, headers=headers)
    
    # Log response details
    print(f"Response status code: {response.status_code}")
    
    if response.status_code == 404:
        return {
            "success": False,
            "operation": "read",
            "message": f"Pull request #{pr_number} not found"
        }
    
    if response.status_code != 200:
        raise GiteaError(f"Failed to get pull request: {response.text}")
    
    pr_data = response.json()
    
    return {
        "success": True,
        "operation": "read",
        "pull_request": pr_data,
        "repo": {
            "owner": api_context['owner'],
            "name": api_context['repo_name']
        }
    }

def list_pull_requests(event, api_context):
    """List pull requests in the repository"""
    # Extract optional parameters
    state = event.get('state', 'open')  # Default to 'open'
    sort = event.get('sort')
    limit = event.get('limit')
    
    print(f"Listing {state} PRs in {api_context['owner']}/{api_context['repo_name']}")
    
    # Set up headers for API requests
    headers = {
        'Authorization': f'token {api_context["auth_token"]}'
    }
    
    # Build query parameters
    params = {'state': state}
    if sort:
        params['sort'] = sort
    if limit:
        params['limit'] = limit
    
    # List pull requests using the API
    pr_url = f"{api_context['api_base']}/repos/{api_context['owner']}/{api_context['repo_name']}/pulls"
    
    response = requests.get(pr_url, headers=headers, params=params)
    
    # Log response details
    print(f"Response status code: {response.status_code}")
    
    if response.status_code != 200:
        raise GiteaError(f"Failed to list pull requests: {response.text}")
    
    pr_list = response.json()
    
    return {
        "success": True,
        "operation": "list",
        "pull_requests": pr_list,
        "count": len(pr_list),
        "repo": {
            "owner": api_context['owner'],
            "name": api_context['repo_name']
        }
    }

def update_pull_request(event, api_context):
    """Update an existing pull request"""
    # Extract parameters
    pr_number = event.get('pr_number')
    new_title = event.get('new_title')
    new_description = event.get('new_description')
    new_target_branch = event.get('new_target_branch')
    
    # Validate required parameters
    if not pr_number:
        raise ValidationError("Missing required parameter: pr_number")
    if not (new_title or new_description or new_target_branch):
        raise ValidationError("At least one update field must be provided: new_title, new_description, or new_target_branch")
    
    print(f"Updating PR #{pr_number} in {api_context['owner']}/{api_context['repo_name']}")
    
    # Set up headers for API requests
    headers = {
        'Authorization': f'token {api_context["auth_token"]}',
        'Content-Type': 'application/json'
    }
    
    # Update the pull request using the API
    pr_url = f"{api_context['api_base']}/repos/{api_context['owner']}/{api_context['repo_name']}/pulls/{pr_number}"
    
    # Prepare payload with only the fields to update
    payload = {}
    if new_title:
        payload['title'] = new_title
    if new_description:
        payload['body'] = new_description
    if new_target_branch:
        payload['base'] = new_target_branch
    
    print(f"Updating PR with payload: {json.dumps(payload)}")
    
    # Update the PR
    response = requests.patch(pr_url, headers=headers, json=payload)
    
    # Log response details
    print(f"Response status code: {response.status_code}")
    
    # Check if the response contains valid PR data
    try:
        pr_data = response.json()
        # Verify we have a PR number which indicates success
        if pr_data and 'number' in pr_data:
            return {
                "success": True,
                "operation": "update",
                "pull_request": {
                    "number": pr_number,
                    "url": pr_data.get('html_url'),
                    "title": pr_data.get('title'),
                    "updated_fields": list(payload.keys())
                },
                "repo": {
                    "owner": api_context['owner'],
                    "name": api_context['repo_name']
                }
            }
    except ValueError:
        # Response is not valid JSON
        pass
    
    # If we get here, it's an error
    if response.status_code >= 400:
        raise GiteaError(f"Failed to update pull request: {response.text}")
    
    # Accept other 2xx status codes as success
    if 200 <= response.status_code < 300:
        return {
            "success": True,
            "operation": "update",
            "pull_request": {
                "number": pr_number,
                "updated_fields": list(payload.keys())
            },
            "repo": {
                "owner": api_context['owner'],
                "name": api_context['repo_name']
            }
        }
    
    # Any other status code is an error
    raise GiteaError(f"Failed to update pull request: {response.text}")

def close_pull_request(event, api_context):
    """Close a pull request"""
    # Extract parameters
    pr_number = event.get('pr_number')
    
    # Validate required parameters
    if not pr_number:
        raise ValidationError("Missing required parameter: pr_number")
    
    print(f"Closing PR #{pr_number} in {api_context['owner']}/{api_context['repo_name']}")
    
    # Set up headers for API requests
    headers = {
        'Authorization': f'token {api_context["auth_token"]}',
        'Content-Type': 'application/json'
    }
    
    # Close the pull request using the API
    pr_url = f"{api_context['api_base']}/repos/{api_context['owner']}/{api_context['repo_name']}/pulls/{pr_number}"
    
    # Prepare payload to close PR
    payload = {
        "state": "closed"
    }
    
    # Close the PR
    response = requests.patch(pr_url, headers=headers, json=payload)
    
    # Log response details
    print(f"Response status code: {response.status_code}")
    
    # Check if the response contains valid PR data
    try:
        pr_data = response.json()
        # Verify that the PR is closed which indicates success
        if pr_data and pr_data.get('state') == 'closed':
            return {
                "success": True,
                "operation": "close",
                "pull_request": {
                    "number": pr_number,
                    "state": "closed",
                    "url": pr_data.get('html_url'),
                    "closed_at": pr_data.get('closed_at')
                },
                "repo": {
                    "owner": api_context['owner'],
                    "name": api_context['repo_name']
                }
            }
    except ValueError:
        # Response is not valid JSON
        pass
    
    # If we get here and status code is in the success range, assume success
    if 200 <= response.status_code < 300:
        return {
            "success": True,
            "operation": "close",
            "pull_request": {
                "number": pr_number,
                "state": "closed"
            },
            "repo": {
                "owner": api_context['owner'],
                "name": api_context['repo_name']
            }
        }
    
    # Any other status code is an error
    raise GiteaError(f"Failed to close pull request: {response.text}")

def merge_pull_request(event, api_context):
    """Merge a pull request"""
    # Extract parameters
    pr_number = event.get('pr_number')
    merge_message = event.get('merge_message', '')
    merge_method = event.get('merge_method', 'merge')  # merge, rebase, rebase-merge, squash
    delete_branch = event.get('delete_branch_after_merge', False)
    
    # Validate required parameters
    if not pr_number:
        raise ValidationError("Missing required parameter: pr_number")
    
    # Validate merge method
    valid_merge_methods = ['merge', 'rebase', 'rebase-merge', 'squash']
    if merge_method not in valid_merge_methods:
        raise ValidationError(f"Invalid merge_method. Must be one of: {', '.join(valid_merge_methods)}")
    
    print(f"Merging PR #{pr_number} in {api_context['owner']}/{api_context['repo_name']} using method: {merge_method}")
    
    # Set up headers for API requests
    headers = {
        'Authorization': f'token {api_context["auth_token"]}',
        'Content-Type': 'application/json'
    }
    
    # Merge the pull request using the API
    merge_url = f"{api_context['api_base']}/repos/{api_context['owner']}/{api_context['repo_name']}/pulls/{pr_number}/merge"
    
    # Prepare payload for merge
    payload = {
        "Do": merge_method,
        "MergeMessageField": merge_message,
        "MergeTitleField": "",  # Let Gitea generate the title
        "delete_branch_after_merge": delete_branch
    }
    
    print(f"Merging PR with payload: {json.dumps(payload)}")
    
    # Merge the PR
    response = requests.post(merge_url, headers=headers, json=payload)
    
    # Log response details
    print(f"Response status code: {response.status_code}")
    
    # Check if the response indicates successful merge
    try:
        merge_data = response.json()
        # If we have a response with merged info, we're good
        if 'merged' in merge_data or 'message' in merge_data:
            return {
                "success": True,
                "operation": "merge",
                "pull_request": {
                    "number": pr_number,
                    "merged": True,
                    "merge_method": merge_method,
                    "branch_deleted": delete_branch,
                    "message": merge_data.get('message', 'Pull request merged successfully')
                },
                "repo": {
                    "owner": api_context['owner'],
                    "name": api_context['repo_name']
                }
            }
    except ValueError:
        # Response is not valid JSON
        pass
    
    # If we get here and status code is in the success range, assume success
    if 200 <= response.status_code < 300:
        return {
            "success": True,
            "operation": "merge",
            "pull_request": {
                "number": pr_number,
                "merged": True,
                "merge_method": merge_method,
                "branch_deleted": delete_branch
            },
            "repo": {
                "owner": api_context['owner'],
                "name": api_context['repo_name']
            }
        }
    
    # Any other status code is an error
    raise GiteaError(f"Failed to merge pull request: {response.text}")

def add_labels_to_pr(pr_number, labels, api_context):
    """Add labels to a pull request"""
    if not labels:
        return
    
    print(f"Adding labels {labels} to PR #{pr_number}")
    
    # Set up headers for API requests
    headers = {
        'Authorization': f'token {api_context["auth_token"]}',
        'Content-Type': 'application/json'
    }
    
    # Add labels to the PR
    labels_url = f"{api_context['api_base']}/repos/{api_context['owner']}/{api_context['repo_name']}/issues/{pr_number}/labels"
    
    payload = labels
    
    # Add the labels
    response = requests.post(labels_url, headers=headers, json=payload)
    
    if response.status_code not in (200, 201):
        print(f"Warning: Failed to add labels to PR #{pr_number}: {response.text}")

def add_assignees_to_pr(pr_number, assignees, api_context):
    """Add assignees to a pull request"""
    if not assignees:
        return
    
    print(f"Adding assignees {assignees} to PR #{pr_number}")
    
    # Set up headers for API requests
    headers = {
        'Authorization': f'token {api_context["auth_token"]}',
        'Content-Type': 'application/json'
    }
    
    # Add assignees to the PR
    assignees_url = f"{api_context['api_base']}/repos/{api_context['owner']}/{api_context['repo_name']}/issues/{pr_number}/assignees"
    
    payload = {
        "assignees": assignees
    }
    
    # Add the assignees
    response = requests.post(assignees_url, headers=headers, json=payload)
    
    if response.status_code not in (200, 201):
        print(f"Warning: Failed to add assignees to PR #{pr_number}: {response.text}")

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