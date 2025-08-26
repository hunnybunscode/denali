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
    Lambda function to perform CRUD operations on Git issues in a Gitea repository.
    
    Expected event input:
    {
        "operation": "create|read|list|update|delete",
        "repo_url": "https://gitea.example.com/owner/repo.git",
        "issue_id": 123,                 # Required for 'read', 'update', 'delete'
        "title": "Issue title",          # Required for 'create', optional for 'update'
        "body": "Issue description",     # Optional for 'create' and 'update'
        "assignees": ["username1"],      # Optional for 'create' and 'update'
        "labels": [1, 2, 3],             # Optional for 'create' and 'update' (must be label IDs, not names)
        "milestone": 1,                  # Optional for 'create' and 'update'
        "state": "open|closed",          # Optional for 'update'
        "branch": "feature-branch",      # Optional for 'create' and 'update'
        "secret_name": "gitea/token"
    }
    """
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
            return create_issue(event, api_context)
        elif operation == 'read':
            return get_issue(event, api_context)
        elif operation == 'list':
            return list_issues(event, api_context)
        elif operation == 'update':
            return update_issue(event, api_context)
        elif operation == 'delete':
            return delete_issue(event, api_context)
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

def create_issue(event, api_context):
    """Create a new issue in a repository"""
    title = event.get('title')
    body = event.get('body', '')
    assignees = event.get('assignees', [])
    labels = event.get('labels', [])
    milestone = event.get('milestone')
    branch = event.get('branch')  # Get branch parameter
    
    # Validate required parameters
    if not title:
        raise ValidationError("Missing required parameter: title")
    
    print(f"Creating issue '{title}' in {api_context['owner']}/{api_context['repo_name']}")
    
    # Set up headers for API requests
    headers = {
        'Authorization': f'token {api_context["auth_token"]}',
        'Content-Type': 'application/json'
    }
    
    # Create the issue using the correct endpoint
    issue_url = f"{api_context['api_base']}/repos/{api_context['owner']}/{api_context['repo_name']}/issues"
    
    # Add branch information to the body if provided
    if branch:
        body_with_branch = body + f"\n\n**Branch**: `{branch}`" if body else f"**Branch**: `{branch}`"
    else:
        body_with_branch = body
    
    # Build the payload
    payload = {
        "title": title,
        "body": body_with_branch
    }
    
    # Add optional parameters if provided
    if assignees:
        payload["assignees"] = assignees
    if labels:
        # Make sure labels are provided as IDs (integers)
        if all(isinstance(label, int) or str(label).isdigit() for label in labels):
            payload["labels"] = [int(label) for label in labels]  # Ensure all are integers
        else:
            print("Warning: Labels must be provided as numeric IDs, not strings. Labels will be ignored.")
    if milestone:
        payload["milestone"] = milestone
    
    # Add branch as ref directly in the payload if Gitea supports this
    if branch:
        payload["ref"] = branch
    
    print(f"Creating issue with payload: {json.dumps(payload)}")
    print(f"Using URL: {issue_url}")
    
    response = requests.post(issue_url, headers=headers, json=payload, timeout=TIMEOUT)
    
    # Log response details
    print(f"Response status code: {response.status_code}")
    try:
        print(f"Response JSON: {json.dumps(response.json(), indent=2)}")
    except:
        print(f"Response text: {response.text}")
    
    if response.status_code != 201:
        raise GiteaError(f"Failed to create issue: {response.text}")
    
    issue_data = response.json()
    issue_number = issue_data['number']
    
    # If branch is provided, ensure it's linked to the issue
    if branch:
        try:
            # Method 1: Try linking through the Git references API
            print(f"Attempting to link branch '{branch}' to issue #{issue_number}")
            
            # Get SHA of the branch
            branch_url = f"{api_context['api_base']}/repos/{api_context['owner']}/{api_context['repo_name']}/branches/{branch}"
            branch_response = requests.get(branch_url, headers=headers, timeout=TIMEOUT)
            
            if branch_response.status_code != 200:
                print(f"Warning: Unable to find branch '{branch}'. Status: {branch_response.status_code}")
            else:
                # Get the commit SHA from the branch
                branch_data = branch_response.json()
                commit_sha = branch_data.get('commit', {}).get('id')
                
                if commit_sha:
                    # Method 2: Create an issue attachment for the branch
                    ref_url = f"{api_context['api_base']}/repos/{api_context['owner']}/{api_context['repo_name']}/issues/{issue_number}/attachments"
                    ref_payload = {
                        "branch": branch
                    }
                    
                    ref_response = requests.post(ref_url, headers=headers, json=ref_payload, timeout=TIMEOUT)
                    print(f"Branch attachment response: {ref_response.status_code}")
                    
                    # Method 3: Create a Git reference (this might be more for PRs)
                    # Some Gitea instances might support this format
                    gitref_url = f"{api_context['api_base']}/repos/{api_context['owner']}/{api_context['repo_name']}/git/refs/heads/{branch}"
                    gitref_response = requests.get(gitref_url, headers=headers, timeout=TIMEOUT)
                    print(f"Git ref response: {gitref_response.status_code}")
        except Exception as e:
            print(f"Warning: Failed to link branch to issue: {str(e)}")
    
    return {
        "success": True,
        "operation": "create",
        "issue": issue_data,
        "branch": branch if branch else None,
        "repo": {
            "owner": api_context['owner'],
            "name": api_context['repo_name']
        }
    }

def get_issue(event, api_context):
    """Get information about a specific issue"""
    issue_id = event.get('issue_id')
    
    # Validate required parameters
    if not issue_id:
        raise ValidationError("Missing required parameter: issue_id")
    
    print(f"Getting information for issue {issue_id} in {api_context['owner']}/{api_context['repo_name']}")
    
    # Set up headers for API requests
    headers = {
        'Authorization': f'token {api_context["auth_token"]}'
    }
    
    # Get issue information using the API
    issue_url = f"{api_context['api_base']}/repos/{api_context['owner']}/{api_context['repo_name']}/issues/{issue_id}"
    
    response = requests.get(issue_url, headers=headers, timeout=TIMEOUT)
    
    # Log response details
    print(f"Response status code: {response.status_code}")
    
    if response.status_code == 404:
        return {
            "success": False,
            "operation": "read",
            "message": f"Issue {issue_id} not found"
        }
    
    if response.status_code != 200:
        raise GiteaError(f"Failed to get issue information: {response.text}")
    
    issue_data = response.json()
    
    # Extract branch information from the body if present
    branch = None
    body = issue_data.get('body', '')
    if "**Branch**:" in body:
        try:
            branch_part = body.split("**Branch**: `")[1]
            branch = branch_part.split("`")[0]
        except:
            pass
    
    response_data = {
        "success": True,
        "operation": "read",
        "issue": issue_data,
        "repo": {
            "owner": api_context['owner'],
            "name": api_context['repo_name']
        }
    }
    
    if branch:
        response_data["branch"] = branch
    
    return response_data

def list_issues(event, api_context):
    """List issues in a repository"""
    state = event.get('state', 'open')
    labels = event.get('labels', [])
    milestone = event.get('milestone')
    
    print(f"Listing issues in {api_context['owner']}/{api_context['repo_name']}")
    
    # Set up headers for API requests
    headers = {
        'Authorization': f'token {api_context["auth_token"]}'
    }
    
    # List issues using the API
    issues_url = f"{api_context['api_base']}/repos/{api_context['owner']}/{api_context['repo_name']}/issues"
    
    # Build query parameters
    params = {'state': state}
    if labels and all(isinstance(label, int) or str(label).isdigit() for label in labels):
        # If labels are provided as IDs
        params['labels'] = ','.join(str(label) for label in labels)
    
    if milestone:
        params['milestone'] = milestone
    
    response = requests.get(issues_url, headers=headers, params=params, timeout=TIMEOUT)
    
    # Log response details
    print(f"Response status code: {response.status_code}")
    
    if response.status_code != 200:
        raise GiteaError(f"Failed to list issues: {response.text}")
    
    issues = response.json()
    
    # Extract branch information from the body if present for each issue
    for issue in issues:
        body = issue.get('body', '')
        if "**Branch**:" in body:
            try:
                branch_part = body.split("**Branch**: `")[1]
                issue['branch'] = branch_part.split("`")[0]
            except:
                pass
    
    return {
        "success": True,
        "operation": "list",
        "issues": issues,
        "repo": {
            "owner": api_context['owner'],
            "name": api_context['repo_name']
        }
    }

def update_issue(event, api_context):
    """Update an issue in the repository"""
    issue_id = event.get('issue_id')
    title = event.get('title')
    body = event.get('body')
    assignees = event.get('assignees')
    labels = event.get('labels')
    milestone = event.get('milestone')
    state = event.get('state')
    branch = event.get('branch')
    
    # Validate required parameters
    if not issue_id:
        raise ValidationError("Missing required parameter: issue_id")
    
    # At least one update parameter should be provided
    if not any([title is not None, body is not None, assignees is not None, 
                labels is not None, milestone is not None, state, branch is not None]):
        raise ValidationError("No update parameters provided")
    
    print(f"Updating issue {issue_id} in {api_context['owner']}/{api_context['repo_name']}")
    
    # Set up headers for API requests
    headers = {
        'Authorization': f'token {api_context["auth_token"]}',
        'Content-Type': 'application/json'
    }
    
    # First get current issue details
    get_issue_url = f"{api_context['api_base']}/repos/{api_context['owner']}/{api_context['repo_name']}/issues/{issue_id}"
    get_response = requests.get(get_issue_url, headers=headers, timeout=TIMEOUT)
    
    if get_response.status_code != 200:
        raise GiteaError(f"Failed to get issue information: {get_response.text}")
    
    current_issue = get_response.json()
    current_body = current_issue.get('body', '')
    
    # Handle body update with branch reference
    if branch is not None and body is None:
        # If updating branch but not explicitly updating body, prepare body
        if "**Branch**:" in current_body:
            # Replace existing branch information in body
            parts = current_body.split("**Branch**:")
            remaining = parts[1].split("`", 2)
            if len(remaining) >= 2:
                body = parts[0] + f"**Branch**: `{branch}`" + remaining[2]
            else:
                body = parts[0] + f"**Branch**: `{branch}`"
        else:
            # Add branch information to current body
            body = current_body + (f"\n\n**Branch**: `{branch}`" if current_body else f"**Branch**: `{branch}`")
    elif branch is not None and body is not None:
        # If updating both branch and body
        if "**Branch**:" not in body:
            # Add branch information to new body
            body = body + (f"\n\n**Branch**: `{branch}`" if body else f"**Branch**: `{branch}`")
        else:
            # Replace branch in new body
            parts = body.split("**Branch**:")
            remaining = parts[1].split("`", 2)
            if len(remaining) >= 2:
                body = parts[0] + f"**Branch**: `{branch}`" + remaining[2]
            else:
                body = parts[0] + f"**Branch**: `{branch}`"
    
    # Build payload with only the parameters that are provided
    payload = {}
    if title is not None:
        payload['title'] = title
    if body is not None:
        payload['body'] = body
    if assignees is not None:
        payload['assignees'] = assignees
    if labels is not None:
        if all(isinstance(label, int) or str(label).isdigit() for label in labels):
            payload["labels"] = [int(label) for label in labels]
        else:
            print("Warning: Labels must be provided as numeric IDs, not strings. Labels will be ignored.")
    if milestone is not None:
        payload['milestone'] = milestone
    if state:
        payload['state'] = state
    
    # Add branch reference directly to payload
    if branch is not None:
        payload['ref'] = branch
    
    print(f"Updating issue with payload: {json.dumps(payload)}")
    
    # Update the issue using the API
    issue_url = f"{api_context['api_base']}/repos/{api_context['owner']}/{api_context['repo_name']}/issues/{issue_id}"
    response = requests.patch(issue_url, headers=headers, json=payload, timeout=TIMEOUT)
    
    # Log response details
    print(f"Response status code: {response.status_code}")
    
    # Check if the response contains valid JSON before trying to parse it
    try:
        issue_data = response.json()
        print(f"Response JSON: {json.dumps(issue_data, indent=2)}")
    except json.JSONDecodeError:
        print(f"Response text (not JSON): {response.text}")
        issue_data = None
    
    # Accept a range of successful status codes (200-204)
    if not (200 <= response.status_code < 300):
        raise GiteaError(f"Failed to update issue: {response.text}")
    
    # If we didn't get JSON data back but the status was successful, fetch the issue again
    if not issue_data and 200 <= response.status_code < 300:
        get_response = requests.get(get_issue_url, headers=headers, timeout=TIMEOUT)
        if get_response.status_code == 200:
            issue_data = get_response.json()
        else:
            print(f"Warning: Could not fetch updated issue data: {get_response.status_code}")
            issue_data = {"number": issue_id, "message": "Issue updated successfully"}
    
    # Extract branch information for response
    updated_branch = None
    if issue_data:
        if issue_data.get('ref'):
            updated_branch = issue_data.get('ref')
        elif "**Branch**:" in issue_data.get('body', ''):
            try:
                branch_part = issue_data['body'].split("**Branch**: `")[1]
                updated_branch = branch_part.split("`")[0]
            except:
                pass
    
    return {
        "success": True,
        "operation": "update",
        "issue": issue_data or {"message": "Issue updated but details not available"},
        "branch": updated_branch or branch,  # Fall back to input branch if extraction fails
        "repo": {
            "owner": api_context['owner'],
            "name": api_context['repo_name']
        }
    }

def delete_issue(event, api_context):
    """Delete an issue from the repository"""
    issue_id = event.get('issue_id')
    
    # Validate required parameters
    if not issue_id:
        raise ValidationError("Missing required parameter: issue_id")
    
    print(f"Deleting issue {issue_id} from {api_context['owner']}/{api_context['repo_name']}")
    
    # Set up headers for API requests
    headers = {
        'Authorization': f'token {api_context["auth_token"]}'
    }
    
    # NOTE: Gitea might not support direct issue deletion through API
    # A common approach is to close the issue instead
    issue_url = f"{api_context['api_base']}/repos/{api_context['owner']}/{api_context['repo_name']}/issues/{issue_id}"
    
    # Try to delete, but if not supported, close the issue instead
    response = requests.delete(issue_url, headers=headers, timeout=TIMEOUT)
    
    # Log response details
    print(f"Response status code: {response.status_code}")
    
    if response.status_code == 404:
        return {
            "success": False,
            "operation": "delete",
            "message": f"Issue {issue_id} not found"
        }
    
    if response.status_code not in (200, 204):
        # If direct deletion is not supported, try closing the issue
        print("Direct deletion not supported, attempting to close the issue instead")
        close_payload = {"state": "closed"}
        close_response = requests.patch(
            issue_url, 
            headers={**headers, 'Content-Type': 'application/json'}, 
            json=close_payload,
            timeout=TIMEOUT
        )
        
        if close_response.status_code != 200:
            raise GiteaError(f"Failed to close issue: {close_response.text}")
        
        return {
            "success": True,
            "operation": "delete",
            "message": f"Issue {issue_id} closed (direct deletion not supported)",
            "repo": {
                "owner": api_context['owner'],
                "name": api_context['repo_name']
            }
        }
    
    return {
        "success": True,
        "operation": "delete",
        "message": f"Issue {issue_id} deleted",
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