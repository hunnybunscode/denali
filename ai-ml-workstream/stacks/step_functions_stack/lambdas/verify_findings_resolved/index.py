import json
import defusedxml.ElementTree as ET
from datetime import datetime
import traceback

# Custom exceptions for step function error handling
class FortifyVerificationError(Exception):
    """Base exception for Fortify verification errors"""
    def __init__(self, message, error_code=None):
        self.message = message
        self.error_code = error_code or "VERIFICATION_ERROR"
        super().__init__(self.message)

class InvalidInputError(FortifyVerificationError):
    """Exception for invalid input data"""
    def __init__(self, message):
        super().__init__(message, "INVALID_INPUT")

class ParseError(FortifyVerificationError):
    """Exception for XML parsing errors"""
    def __init__(self, message):
        super().__init__(message, "PARSE_ERROR")

def parse_fvdl_content(fvdl_content):
    """
    Parse FVDL XML content to extract vulnerabilities.
    Returns list of vulnerabilities with InstanceID as key.
    """
    try:
        # Parse the XML content
        root = ET.fromstring(fvdl_content)
        
        # Check for namespace
        namespace = ''
        if '}' in root.tag:
            namespace = '{' + root.tag.split('}')[0].strip('{') + '}'
        
        # Extract vulnerabilities
        vulnerabilities = {}
        vuln_elems = root.findall(f'.//{namespace}Vulnerabilities/{namespace}Vulnerability')
        
        for vuln_elem in vuln_elems:
            vuln_data = {}
            
            # Extract InstanceID (required)
            instance_info = vuln_elem.find(f'./{namespace}InstanceInfo')
            if instance_info is not None:
                instance_id_elem = instance_info.find(f'./{namespace}InstanceID')
                if instance_id_elem is not None and instance_id_elem.text:
                    instance_id = instance_id_elem.text
                    vuln_data['InstanceID'] = instance_id
                else:
                    continue  # Skip vulnerabilities without InstanceID
            else:
                continue  # Skip vulnerabilities without InstanceInfo
            
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
                    
                severity_elem = class_info.find(f'./{namespace}DefaultSeverity')
                if severity_elem is not None and severity_elem.text:
                    vuln_data['DefaultSeverity'] = severity_elem.text
            
            # Extract additional InstanceInfo
            if instance_info is not None:
                severity_elem = instance_info.find(f'./{namespace}InstanceSeverity')
                if severity_elem is not None and severity_elem.text:
                    vuln_data['InstanceSeverity'] = severity_elem.text
                    
                confidence_elem = instance_info.find(f'./{namespace}Confidence')
                if confidence_elem is not None and confidence_elem.text:
                    vuln_data['Confidence'] = confidence_elem.text
            
            # Extract file and line information
            analysis_info = vuln_elem.find(f'./{namespace}AnalysisInfo')
            if analysis_info is not None:
                unified = analysis_info.find(f'./{namespace}Unified')
                if unified is not None:
                    repl_defs = unified.find(f'./{namespace}ReplacementDefinitions')
                    if repl_defs is not None:
                        for def_elem in repl_defs.findall(f'./{namespace}Def'):
                            if def_elem.get('key') == 'PrimaryLocation.file':
                                vuln_data['PrimaryFile'] = def_elem.get('value')
                            elif def_elem.get('key') == 'PrimaryLocation.line':
                                try:
                                    vuln_data['PrimaryLine'] = int(def_elem.get('value'))
                                except ValueError:
                                    pass
            
            vulnerabilities[instance_id] = vuln_data
        
        return vulnerabilities
        
    except ET.ParseError as e:
        raise ParseError(f"Failed to parse FVDL XML content: {str(e)}")
    except Exception as e:
        raise ParseError(f"Unexpected error parsing FVDL content: {str(e)}")

def process_existing_findings(dynamo_items):
    """
    Process existing findings from DynamoDB scan results.
    Returns dictionary with InstanceID as key.
    """
    existing_findings = {}
    
    if not isinstance(dynamo_items, list):
        raise InvalidInputError("DynamoDB items must be a list")
    
    for item in dynamo_items:
        if 'InstanceID' in item:
            existing_findings[item['InstanceID']] = item
    
    return existing_findings

def compare_findings(new_findings, existing_findings, target_instance_id=None):
    """
    Compare new findings with existing findings.
    If target_instance_id is provided, specifically check if that finding was resolved.
    Returns analysis results.
    """
    new_instance_ids = set(new_findings.keys())
    existing_instance_ids = set(existing_findings.keys())
    
    # Findings that are resolved (in existing but not in new)
    resolved_findings = existing_instance_ids - new_instance_ids
    
    # New findings (in new but not in existing)
    new_findings_ids = new_instance_ids - existing_instance_ids
    
    # Persistent findings (in both)
    persistent_findings = new_instance_ids & existing_instance_ids
    
    # Check target finding status
    target_finding_status = None
    target_finding_details = None
    
    if target_instance_id:
        if target_instance_id in resolved_findings:
            target_finding_status = "RESOLVED"
            # Create a simplified version of the finding details
            finding = existing_findings[target_instance_id]
            target_finding_details = {
                'InstanceID': target_instance_id,
                'Type': finding.get('type', 'Unknown'),
                'Kingdom': finding.get('kingdom', 'Unknown'),
                'Severity': finding.get('severity', 'Unknown'),
                'PrimaryFile': finding.get('primaryFile', 'Unknown')
            }
        elif target_instance_id in persistent_findings:
            target_finding_status = "PERSISTENT"
            # Create a simplified version of the finding details
            finding = new_findings[target_instance_id]
            target_finding_details = {
                'InstanceID': target_instance_id,
                'Type': finding.get('Type', 'Unknown'),
                'Kingdom': finding.get('Kingdom', 'Unknown'),
                'Severity': finding.get('InstanceSeverity', 'Unknown'),
                'PrimaryFile': finding.get('PrimaryFile', 'Unknown')
            }
        elif target_instance_id in existing_instance_ids:
            # Was in existing but somehow not categorized properly
            target_finding_status = "UNKNOWN"
            # Create a simplified version of the finding details
            finding = existing_findings[target_instance_id]
            target_finding_details = {
                'InstanceID': target_instance_id,
                'Type': finding.get('type', 'Unknown'),
                'Kingdom': finding.get('kingdom', 'Unknown'),
                'Severity': finding.get('severity', 'Unknown'),
                'PrimaryFile': finding.get('primaryFile', 'Unknown')
            }
        else:
            target_finding_status = "NOT_FOUND_IN_ORIGINAL"
    
    # Build detailed results
    results = {
        'summary': {
            'total_new_findings': len(new_findings),
            'total_existing_findings': len(existing_findings),
            'resolved_count': len(resolved_findings),
            'new_count': len(new_findings_ids),
            'persistent_count': len(persistent_findings)
        },
        'target_finding': {
            'instance_id': target_instance_id,
            'status': target_finding_status,
            'details': target_finding_details
        } if target_instance_id else None,
        'resolved_findings': [],
        'new_findings': [],
        'persistent_findings': []
    }
    
    # Add details for resolved findings
    for instance_id in resolved_findings:
        finding = existing_findings[instance_id]
        finding_detail = {
            'InstanceID': instance_id,
            'Type': finding.get('type', 'Unknown'),
            'Kingdom': finding.get('kingdom', 'Unknown'),
            'Severity': finding.get('severity', 'Unknown'),
            'PrimaryFile': finding.get('primaryFile', 'Unknown'),
            'is_target': instance_id == target_instance_id
        }
        results['resolved_findings'].append(finding_detail)
    
    # Add details for new findings
    for instance_id in new_findings_ids:
        finding = new_findings[instance_id]
        results['new_findings'].append({
            'InstanceID': instance_id,
            'Type': finding.get('Type', 'Unknown'),
            'Kingdom': finding.get('Kingdom', 'Unknown'),
            'Severity': finding.get('InstanceSeverity', 'Unknown'),
            'PrimaryFile': finding.get('PrimaryFile', 'Unknown')
        })
    
    # Add details for persistent findings
    for instance_id in persistent_findings:
        finding = new_findings[instance_id]
        finding_detail = {
            'InstanceID': instance_id,
            'Type': finding.get('Type', 'Unknown'),
            'Kingdom': finding.get('Kingdom', 'Unknown'),
            'Severity': finding.get('InstanceSeverity', 'Unknown'),
            'PrimaryFile': finding.get('PrimaryFile', 'Unknown'),
            'is_target': instance_id == target_instance_id
        }
        results['persistent_findings'].append(finding_detail)
    
    return results

def lambda_handler(event, context):
    """
    Main lambda handler for verifying Fortify findings.
    Expects git_file and dynamo_scan_results from step function.
    """
    try:
        print(f"Starting Fortify findings verification")
        print(f"Event keys: {list(event.keys()) if isinstance(event, dict) else 'Not a dict'}")
        
        # Validate input structure
        if not isinstance(event, dict):
            raise InvalidInputError("Event must be a dictionary")
        
        # Extract git file information
        git_file = event.get('git_file')
        if not git_file:
            raise InvalidInputError("Missing 'git_file' in event")
        
        if not git_file.get('success'):
            raise InvalidInputError(f"Git file retrieval failed: {git_file}")
        
        fvdl_content = git_file.get('content')
        if not fvdl_content:
            raise InvalidInputError("Missing FVDL content in git_file")
        
        # Extract DynamoDB scan results
        dynamo_scan = event.get('dynamo_scan_results')
        if dynamo_scan is None:
            raise InvalidInputError("Missing 'dynamo_scan_results' in event")
        
        # Handle both direct items list or nested structure
        dynamo_items = dynamo_scan
        if isinstance(dynamo_scan, dict) and 'Items' in dynamo_scan:
            dynamo_items = dynamo_scan['Items']
        
        # Extract target finding information (the original finding we're trying to fix)
        target_instance_id = event.get('target_finding', {}).get('instance_id')
        
        # If not found directly, check in previous_chat if available
        if not target_instance_id and 'previous_chat' in event:
            previous_chat = event.get('previous_chat', {})
            # Check if there's a Fortify Report Details section with InstanceID
            issue_body = previous_chat.get('issueBody', '')
            if issue_body and 'InstanceID' in issue_body:
                # Try to extract InstanceID from the JSON in the issue body
                import re
                match = re.search(r'"InstanceID":\s*"([^"]+)"', issue_body)
                if match:
                    target_instance_id = match.group(1)
                    print(f"Found target instance ID in issue body: {target_instance_id}")
            
            # Also check PR description
            pr_description = previous_chat.get('prDescription', '')
            if not target_instance_id and pr_description and 'Instance ID:' in pr_description:
                match = re.search(r'Instance ID:\s*(\w+)', pr_description)
                if match:
                    target_instance_id = match.group(1)
                    print(f"Found target instance ID in PR description: {target_instance_id}")
        
        # If still not found, try alternative field names
        if not target_instance_id:
            target_instance_id = event.get('original_finding_id') or event.get('target_instance_id')
        
        print(f"Processing {len(dynamo_items)} existing findings from DynamoDB")
        if target_instance_id:
            print(f"Target finding to verify: {target_instance_id}")
        else:
            print("Warning: No target finding specified - will perform general comparison only")
        
        # Parse new findings from FVDL content
        print("Parsing new FVDL findings...")
        new_findings = parse_fvdl_content(fvdl_content)
        print(f"Found {len(new_findings)} new findings")
        
        # Process existing findings from DynamoDB scan
        print("Processing existing findings from DynamoDB scan...")
        existing_findings = process_existing_findings(dynamo_items)
        print(f"Processed {len(existing_findings)} existing findings")
        
        # Compare findings
        print("Comparing findings...")
        comparison_results = compare_findings(new_findings, existing_findings, target_instance_id)
        
        # Prepare response
        response = {
            'statusCode': 200,
            'verification_timestamp': datetime.now().isoformat(),
            'comparison_results': {
                'summary': comparison_results['summary'],
                'target_finding': comparison_results['target_finding']
            }
        }
        
        # Limit the number of findings included in the response to prevent truncation
        max_findings = 10  # Adjust this number as needed
        
        # Add limited number of findings to the response
        if comparison_results['resolved_findings']:
            response['comparison_results']['resolved_findings'] = comparison_results['resolved_findings'][:max_findings]
            if len(comparison_results['resolved_findings']) > max_findings:
                response['comparison_results']['resolved_findings_truncated'] = True
                response['comparison_results']['total_resolved_findings'] = len(comparison_results['resolved_findings'])
        else:
            response['comparison_results']['resolved_findings'] = []
            
        if comparison_results['new_findings']:
            response['comparison_results']['new_findings'] = comparison_results['new_findings'][:max_findings]
            if len(comparison_results['new_findings']) > max_findings:
                response['comparison_results']['new_findings_truncated'] = True
                response['comparison_results']['total_new_findings'] = len(comparison_results['new_findings'])
        else:
            response['comparison_results']['new_findings'] = []
            
        if comparison_results['persistent_findings']:
            response['comparison_results']['persistent_findings'] = comparison_results['persistent_findings'][:max_findings]
            if len(comparison_results['persistent_findings']) > max_findings:
                response['comparison_results']['persistent_findings_truncated'] = True
                response['comparison_results']['total_persistent_findings'] = len(comparison_results['persistent_findings'])
        else:
            response['comparison_results']['persistent_findings'] = []
        
        print(f"Verification completed successfully")
        print(f"Summary: {comparison_results['summary']}")
        
        # Ensure the response is serializable
        try:
            # Test JSON serialization
            json.dumps(response)
        except (TypeError, OverflowError) as e:
            print(f"Warning: Response contains non-serializable data: {str(e)}")
            # Create a simplified response
            response = {
                'statusCode': 200,
                'verification_timestamp': datetime.now().isoformat(),
                'comparison_results': {
                    'summary': comparison_results['summary'],
                    'target_finding': {
                        'instance_id': comparison_results.get('target_finding', {}).get('instance_id'),
                        'status': comparison_results.get('target_finding', {}).get('status')
                    } if comparison_results.get('target_finding') else None,
                    'note': "Full findings data was truncated due to serialization issues"
                }
            }
        
        return response
        
    except (InvalidInputError, ParseError) as e:
        # Known errors - return structured error for step function
        error_response = {
            'statusCode': 400,
            'error': {
                'type': e.error_code,
                'message': e.message,
                'timestamp': datetime.now().isoformat()
            }
        }
        print(f"Verification failed with known error: {e.message}")
        return error_response
        
    except Exception as e:
        # Unexpected errors
        error_response = {
            'statusCode': 500,
            'error': {
                'type': 'UNEXPECTED_ERROR',
                'message': str(e),
                'traceback': traceback.format_exc(),
                'timestamp': datetime.now().isoformat()
            }
        }
        print(f"Verification failed with unexpected error: {str(e)}")
        print(traceback.format_exc())
        return error_response
# Expected Input Format:
# {
#   "git_file": {
#     "success": true,
#     "content": "<FVDL XML content>",
#     ...
#   },
#   "dynamo_scan_results": [...],
#   "target_finding": {
#     "instance_id": "18EC1AA3328C2538A0B3F4D7C4E9B1BF",
#     "type": "Unchecked Return Value",
#     "file": "fft.c"
#   },
#   "attempt_count": 1
# }