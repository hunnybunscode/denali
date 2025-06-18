import json
import os
import boto3
import xml.etree.ElementTree as ET
from datetime import datetime
import requests
import uuid
import urllib.parse
from decimal import Decimal

def get_relative_path(base_path, absolute_path):
    """
    Computes the git relative path given a base path and an absolute path.
    """
    if not absolute_path or not base_path:
        return absolute_path
    
    # Normalize paths to handle different path separators
    base_path = os.path.normpath(base_path)
    absolute_path = os.path.normpath(absolute_path)
    
    # If the absolute path starts with the base path, remove the base path portion
    if absolute_path.startswith(base_path):
        relative_path = absolute_path[len(base_path):]
        # Remove leading slash or backslash if present
        if relative_path.startswith('/') or relative_path.startswith('\\'):
            relative_path = relative_path[1:]
        return relative_path
    
    # If not a subfolder, return the absolute path
    return absolute_path

def get_gitea_token_from_secrets(secret_name):
    """
    Retrieve Gitea token from AWS Secrets Manager.
    """
    session = boto3.session.Session()
    secrets_client = session.client(service_name='secretsmanager')
    
    try:
        get_secret_value_response = secrets_client.get_secret_value(SecretId=secret_name)
        if 'SecretString' in get_secret_value_response:
            secret = json.loads(get_secret_value_response['SecretString'])
            return secret.get('token') or secret.get('GITEA_TOKEN') or secret.get('giteaToken')
    except Exception as e:
        print(f"Error retrieving secret {secret_name}: {str(e)}")
    
    return None

def download_files_from_gitea(repo_url, branch, secret_name=None):
    """
    Downloads files from Gitea repository using HTTP requests.
    Returns a list of downloaded file paths.
    """
    # Parse repository URL
    parsed_url = urllib.parse.urlparse(repo_url)
    
    # Extract repository owner and name from the URL path
    path_parts = parsed_url.path.strip('/').split('/')
    owner = path_parts[0]
    repo_name = path_parts[1].replace('.git', '')
    
    # Build base API URL
    api_base = f"{parsed_url.scheme}://{parsed_url.netloc}/api/v1"
    api_url = f"{api_base}/repos/{owner}/{repo_name}/contents"
    
    # Get authentication token from Secrets Manager if provided
    auth_token = None
    if secret_name:
        auth_token = get_gitea_token_from_secrets(secret_name)
        print(f"Retrieved token from Secrets Manager: {secret_name}")
    
    # Set up headers for API requests
    headers = {}
    if auth_token:
        headers['Authorization'] = f'token {auth_token}'
    
    # List of downloaded files
    downloaded_files = []
    
    # Function to recursively fetch files
    def fetch_directory_contents(path=""):
        nonlocal downloaded_files
        
        url = f"{api_url}/{path}" if path else api_url
        params = {'ref': branch} if branch else {}
        
        print(f"Fetching: {url} with params {params}")
        response = requests.get(url, headers=headers, params=params)
        
        if response.status_code != 200:
            print(f"Error fetching directory {path}: {response.status_code} {response.text}")
            return
        
        contents = response.json()
        
        # Process each item
        for item in contents:
            if item['type'] == 'file':
                # Check if it's an XML or FVDL file
                if item['name'].lower().endswith(('.xml', '.fvdl')):
                    # Download the file
                    download_url = item['download_url']
                    file_response = requests.get(download_url, headers=headers)
                    
                    if file_response.status_code == 200:
                        # Save to a temporary file
                        temp_file = os.path.join('/tmp', f"{uuid.uuid4().hex}_{item['name']}")
                        with open(temp_file, 'wb') as f:
                            f.write(file_response.content)
                        
                        # For XML files, check if it contains FVDL content
                        if item['name'].lower().endswith('.xml'):
                            try:
                                with open(temp_file, 'r') as f:
                                    content = f.read(1000)  # Just read the beginning
                                    if '<FVDL' in content:
                                        downloaded_files.append(temp_file)
                                        print(f"Found FVDL file: {item['name']}")
                                    else:
                                        os.remove(temp_file)
                            except:
                                os.remove(temp_file)
                        else:
                            downloaded_files.append(temp_file)
                            print(f"Downloaded FVDL file: {item['name']}")
            
            elif item['type'] == 'dir':
                # Recursively explore directories
                subdir_path = f"{path}/{item['name']}" if path else item['name']
                fetch_directory_contents(subdir_path)
    
    # Start recursive fetch
    fetch_directory_contents()
    
    return downloaded_files

def parse_fvdl(file_path, base_path=''):
    """
    Simplified parser for FVDL XML file to extract vulnerabilities.
    """
    # Parse the XML
    tree = ET.parse(file_path)
    root = tree.getroot()
    
    # Check for namespace
    namespace = ''
    if '}' in root.tag:
        namespace = '{' + root.tag.split('}')[0].strip('{') + '}'
    
    # Extract build information
    build_info = {}
    build_elem = root.find(f'.//{namespace}Build')
    if build_elem is not None:
        build_id_elem = build_elem.find(f'./{namespace}BuildID')
        if build_id_elem is not None and build_id_elem.text:
            build_info['BuildID'] = build_id_elem.text
            
        num_files_elem = build_elem.find(f'./{namespace}NumberFiles')
        if num_files_elem is not None and num_files_elem.text:
            build_info['NumberFiles'] = int(num_files_elem.text)
            
        source_base_elem = build_elem.find(f'./{namespace}SourceBasePath')
        if source_base_elem is not None and source_base_elem.text:
            build_info['SourceBasePath'] = source_base_elem.text
            
        # Extract scan time if available
        scan_time_elem = build_elem.find(f'./{namespace}ScanTime')
        if scan_time_elem is not None and scan_time_elem.get('value'):
            build_info['ScanTime'] = scan_time_elem.get('value')
    
    # Get the source base path from build info
    source_base_path = build_info.get('SourceBasePath', '')
    print(f"Source base path from FVDL: '{source_base_path}'")
    print(f"Git base path from event: '{base_path}'")
    
    # Calculate the relative directory by removing base_path from source_base_path
    relative_dir = ""
    if base_path and source_base_path and source_base_path.startswith(base_path):
        relative_dir = source_base_path[len(base_path):]
        # Remove leading slash if present
        if relative_dir.startswith('/') or relative_dir.startswith('\\'):
            relative_dir = relative_dir[1:]
        print(f"Calculated relative directory: '{relative_dir}'")
    else:
        print(f"Warning: source_base_path does not start with base_path")
        
    def get_file_name_from_path(path):
        """Extract just the file name from a path."""
        return os.path.basename(path) if path else ""
    
    # Extract vulnerabilities
    vulnerabilities = []
    vuln_elems = root.findall(f'.//{namespace}Vulnerabilities/{namespace}Vulnerability')
    
    for vuln_elem in vuln_elems:
        vuln_data = {}
        
        # Extract ClassInfo
        class_info = vuln_elem.find(f'./{namespace}ClassInfo')
        if class_info is not None:
            class_id_elem = class_info.find(f'./{namespace}ClassID')
            if class_id_elem is not None and class_id_elem.text:
                vuln_data['ClassID'] = class_id_elem.text
                
            kingdom_elem = class_info.find(f'./{namespace}Kingdom')
            if kingdom_elem is not None and kingdom_elem.text:
                vuln_data['Kingdom'] = kingdom_elem.text
                
            type_elem = class_info.find(f'./{namespace}Type')
            if type_elem is not None and type_elem.text:
                vuln_data['Type'] = type_elem.text
                
            subtype_elem = class_info.find(f'./{namespace}Subtype')
            if subtype_elem is not None and subtype_elem.text:
                vuln_data['Subtype'] = subtype_elem.text
                
            severity_elem = class_info.find(f'./{namespace}DefaultSeverity')
            if severity_elem is not None and severity_elem.text:
                try:
                    # Store as string to avoid float issues with DynamoDB
                    vuln_data['DefaultSeverity'] = severity_elem.text
                except ValueError:
                    pass
        
        # Extract InstanceInfo
        instance_info = vuln_elem.find(f'./{namespace}InstanceInfo')
        if instance_info is not None:
            instance_id_elem = instance_info.find(f'./{namespace}InstanceID')
            if instance_id_elem is not None and instance_id_elem.text:
                vuln_data['InstanceID'] = instance_id_elem.text
                
            severity_elem = instance_info.find(f'./{namespace}InstanceSeverity')
            if severity_elem is not None and severity_elem.text:
                try:
                    # Store as string to avoid float issues with DynamoDB
                    vuln_data['InstanceSeverity'] = severity_elem.text
                except ValueError:
                    pass
                
            confidence_elem = instance_info.find(f'./{namespace}Confidence')
            if confidence_elem is not None and confidence_elem.text:
                try:
                    # Store as string to avoid float issues with DynamoDB
                    vuln_data['Confidence'] = confidence_elem.text
                except ValueError:
                    pass
        
        # Extract relevant AnalysisInfo details
        analysis_info = vuln_elem.find(f'./{namespace}AnalysisInfo')
        if analysis_info is not None:
            unified = analysis_info.find(f'./{namespace}Unified')
            if unified is not None:
                # Get function information
                context = unified.find(f'./{namespace}Context')
                if context is not None:
                    function_elem = context.find(f'./{namespace}Function')
                    if function_elem is not None and function_elem.get('name'):
                        vuln_data['Function'] = function_elem.get('name')
                    
                    # Get source location
                    src_loc = context.find(f'./{namespace}FunctionDeclarationSourceLocation') 
                    if src_loc is not None:
                        if src_loc.get('path'):
                            source_file = src_loc.get('path')
                            vuln_data['SourceFile'] = source_file
                            # Add git relative path - simply join relative dir with filename
                            file_name = get_file_name_from_path(source_file)
                            vuln_data['SourceFileRelative'] = os.path.join(relative_dir, file_name) if relative_dir else file_name
                        if src_loc.get('line'):
                            try:
                                vuln_data['Line'] = int(src_loc.get('line'))
                            except ValueError:
                                pass
                
                # Get primary location from ReplacementDefinitions
                repl_defs = unified.find(f'./{namespace}ReplacementDefinitions')
                if repl_defs is not None:
                    for def_elem in repl_defs.findall(f'./{namespace}Def'):
                        if def_elem.get('key') == 'PrimaryLocation.file':
                            primary_file = def_elem.get('value')
                            vuln_data['PrimaryFile'] = primary_file
                            # Add git relative path - simply join relative dir with filename
                            file_name = get_file_name_from_path(primary_file)
                            vuln_data['PrimaryFileRelative'] = os.path.join(relative_dir, file_name) if relative_dir else file_name
                        elif def_elem.get('key') == 'PrimaryLocation.line':
                            try:
                                vuln_data['PrimaryLine'] = int(def_elem.get('value'))
                            except ValueError:
                                pass
                        elif def_elem.get('key') == 'PrimaryCall.name':
                            vuln_data['PrimaryCall'] = def_elem.get('value')
        
        vulnerabilities.append(vuln_data)
    
    return vulnerabilities, build_info

def float_to_decimal(obj):
    """Helper function to convert float values to Decimal for DynamoDB compatibility"""
    if isinstance(obj, float):
        return Decimal(str(obj))
    elif isinstance(obj, dict):
        return {k: float_to_decimal(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [float_to_decimal(x) for x in obj]
    elif isinstance(obj, str) and obj.replace('.', '', 1).isdigit():
        # Convert string numbers to Decimal if they look like floats
        try:
            return Decimal(obj)
        except:
            return obj
    else:
        return obj

def save_to_dynamodb(vulnerabilities, build_info, table_name, project_name, scan_timestamp=None):
    """Save vulnerability data to DynamoDB."""
    dynamodb = boto3.resource('dynamodb')
    table = dynamodb.Table(table_name)
    
    # Generate timestamp if not provided
    if scan_timestamp is None:
        scan_timestamp = datetime.now().isoformat()
    
    # Convert build_info numbers to Decimal
    build_info = float_to_decimal(build_info)
    
    for vuln in vulnerabilities:
        # Check if the vulnerability has an InstanceID
        if 'InstanceID' not in vuln:
            print(f"Skipping vulnerability without InstanceID: {vuln}")
            continue
            
        item = {
            'projectName': project_name,
            'scanTimestamp': scan_timestamp,
            'InstanceID': vuln.get('InstanceID')  # Keep the original attribute name
        }
        
        # Add build info
        for key, value in build_info.items():
            item[key] = value
        
        # Add vulnerability fields - extended to include relative paths
        fields_to_copy = [
            ('ClassID', 'classID'), 
            ('Kingdom', 'kingdom'), 
            ('Type', 'type'), 
            ('Subtype', 'subtype'), 
            ('DefaultSeverity', 'defaultSeverity'),
            ('InstanceSeverity', 'severity'), 
            ('Confidence', 'confidence'), 
            ('Function', 'function'),
            ('SourceFile', 'sourceFile'), 
            ('SourceFileRelative', 'sourceFileRelative'),  # Added relative path
            ('Line', 'line'),
            ('PrimaryFile', 'primaryFile'), 
            ('PrimaryFileRelative', 'primaryFileRelative'),  # Added relative path
            ('PrimaryLine', 'primaryLine'),
            ('PrimaryCall', 'primaryCall')
        ]
        
        for src_field, dest_field in fields_to_copy:
            if src_field in vuln and vuln[src_field]:
                # Convert any float values to Decimal
                item[dest_field] = float_to_decimal(vuln[src_field])
        
        # Write to DynamoDB
        table.put_item(Item=item)

def lambda_handler(event, context):
    try:
        print(f"Starting Fortify scan result processing")
        
        # Get parameters from the event
        main_branch = event.get('mainBranch')
        scan_results_repo = event.get('scanResultsRepo')
        project_name = event.get('projectName')
        table_name = event.get('tableName')
        secret_name = event.get('secretName')  # Name of the secret in Secrets Manager
        base_path = event.get('basePath', '')  # Get the base path for computing relative paths
        
        print(f"Base path for relative path calculation: {base_path}")
        
        # Validate required parameters
        if not all([scan_results_repo, project_name, table_name]):
            return {
                'statusCode': 400,
                'body': json.dumps('Missing required parameters in event')
            }
        
        # Download files from Gitea repository
        print(f"Downloading FVDL files from repository: {scan_results_repo}")
        fvdl_files = download_files_from_gitea(scan_results_repo, main_branch, secret_name)
        
        print(f"Found {len(fvdl_files)} FVDL files")
        
        if not fvdl_files:
            return {
                'statusCode': 404,
                'body': json.dumps('No FVDL files found in the repository')
            }
        
        # Generate a single timestamp for all vulnerabilities in this run
        scan_timestamp = datetime.now().isoformat()
        
        # Process all FVDL files found
        total_vulnerabilities = 0
        for fvdl_file in fvdl_files:
            print(f"Processing file: {fvdl_file}")
            vulnerabilities, build_info = parse_fvdl(fvdl_file, base_path)
            print(f"Found {len(vulnerabilities)} vulnerabilities")
            
            save_to_dynamodb(vulnerabilities, build_info, table_name, project_name, scan_timestamp)
            total_vulnerabilities += len(vulnerabilities)
            
            # Clean up the temporary file
            os.remove(fvdl_file)
        
        return {
            'statusCode': 200,
            'body': json.dumps({
                'message': 'Successfully processed vulnerability data',
                'projectName': project_name,
                'totalVulnerabilities': total_vulnerabilities,
                'filesProcessed': len(fvdl_files),
                'scanTimestamp': scan_timestamp
            })
        }
            
    except Exception as e:
        import traceback
        print(f"Error: {str(e)}")
        print(traceback.format_exc())
        return {
            'statusCode': 500,
            'body': json.dumps({
                'error': str(e),
                'traceback': traceback.format_exc()
            })
        }