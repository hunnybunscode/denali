import json
import re
import os
import boto3

def lambda_handler(event, context):
    """
    Lambda function that processes Fortify scan results, sends the code to an LLM for fixing,
    and formats output for GitHub issues and PRs.
    """
    try:
        # Extract input data
        fortify_result = event.get('fortify_result', {})
        file_content = event.get('file_content', '')
        
        # Extract necessary details from fortify_result
        source_file = fortify_result.get('sourceFile', '')
        line_number = fortify_result.get('line', 0)
        issue_type = fortify_result.get('type', '')
        subtype = fortify_result.get('subtype', '')
        function_name = fortify_result.get('function', '')
        project_name = fortify_result.get('projectName', '')
        
        # Create category and prepare code for LLM
        category = f"{issue_type}: {subtype}" if subtype else issue_type
        numbered_code = add_line_numbers(file_content, line_number)
        
        # Prepare the prompt for the LLM
        human_prompt = f"""You are a senior C programming expert specialized in code analysis and bug fixing.
                CODE CONTEXT:
                Source File: {source_file}
                Original Code:
                {numbered_code}

                ISSUE DETAILS:
                Category: {category}
                Line Number: {line_number}

                REQUIREMENTS:
                1. Fix the {category} issue at line {line_number}
                2. Maintain full compatibility with existing codebase
                3. Follow secure coding practices
                4. Preserve original code style and formatting
                5. Ensure no new vulnerabilities are introduced

                Please analyze and fix the code following these guidelines:
                - Consider all potential edge cases
                - Follow C best practices and standards
                - Maintain or improve code performance
                - Add necessary error handling
                - Preserve existing comments and documentation
                - Ensure thread safety if applicable

                Provide your response in this exact format:

                ANALYSIS:
                [Detailed technical analysis of the issue]
                - Root cause
                - Potential implications
                - Security considerations
                - Performance impact

                SOLUTION APPROACH:
                [Explanation of fix strategy]
                - Why this approach was chosen
                - Alternative approaches considered
                - Trade-offs made

                FALSE_POSITIVE: 
                [TRUE / FALSE]

                FIXED_CODE:
                [Complete fixed source code without line numbers]

                VERIFICATION_STEPS:
                [List of recommended tests/checks to validate the fix]

                The fixed code must be immediately usable as a source file with no additional formatting needed.
                """

        prompt = f"Human: {human_prompt}\n\nAssistant:"

        # Call the LLM for a fix
        llm_response = call_llm(prompt)
        
        # Parse the LLM response
        parsed_sections = parse_llm_sections(llm_response)
        
        # Format the output for GitHub
        output = format_github_output(
            fortify_result, 
            source_file, 
            function_name, 
            category, 
            line_number, 
            parsed_sections.get('analysis', ''),
            parsed_sections.get('solution_approach', ''),
            
            parsed_sections.get('fixed_code', ''), 
            parsed_sections.get('verification_steps', ''),
            project_name,
            parsed_sections.get('false_positive', '')
        )
        
        # Include the parsed sections in the output
        output['parsed_sections'] = parsed_sections
        
        return output
        
    except Exception as e:
        print(f"Error: {str(e)}")
        return {
            "error": str(e),
            "status": "failed"
        }

def add_line_numbers(code_content, target_line):
    """Add line numbers to the entire code content and highlight the target line"""
    if not code_content:
        return "No code content provided"
        
    lines = code_content.split('\n')
    
    # Create numbered code for the entire file
    numbered_lines = []
    for i, line in enumerate(lines):
        line_num = i + 1
        prefix = f"{line_num}: "
        if line_num == target_line:
            # Highlight the target line
            numbered_lines.append(f"→ {prefix}{line}")
        else:
            numbered_lines.append(f"  {prefix}{line}")
    
    return '\n'.join(numbered_lines)

def get_mock_response():
    """Return a mock response for testing purposes"""
    return """
    ANALYSIS:
    This is a mock analysis of the code issue.
    
    SOLUTION APPROACH:
    This is a mock solution approach.
    
    FIXED_CODE:
    // This is mock fixed code
    int main() {
        // Fixed implementation
        return 0;
    }
    
    VERIFICATION_STEPS:
    1. Test step one
    2. Test step two
    """

def call_llm(prompt):
    """Call the LLM to get a code fix"""
    # Get LLM service configuration from environment variables
    llm_service = os.environ.get('LLM_SERVICE', 'bedrock')
    
    if llm_service.lower() == 'bedrock':
        return call_bedrock(prompt)
    elif llm_service.lower() == 'sagemaker':
        return call_sagemaker(prompt)
    else:
        # For testing or if no LLM service is specified
        return get_mock_response()
        
def call_bedrock(prompt):
    """Call AWS Bedrock to get a code fix"""
    try:
        bedrock = boto3.client('bedrock-runtime')
        model_id = os.environ.get('BEDROCK_MODEL_ID', 'anthropic.claude-3-5-sonnet-20240620-v1:0')
        
        # Check if using Claude 3 or newer models (which use Messages API)
        if 'claude-3' in model_id:
            response = bedrock.invoke_model(
                modelId=model_id,
                body=json.dumps({
                    "anthropic_version": "bedrock-2023-05-31",
                    "max_tokens": 2000,
                    "temperature": 0.2,
                    "messages": [
                        {
                            "role": "user",
                            "content": prompt
                        }
                    ]
                })
            )
            
            response_body = json.loads(response['body'].read())
            return response_body.get('content', [{}])[0].get('text', '')
        else:
            # Legacy format for older Claude models
            response = bedrock.invoke_model(
                modelId=model_id,
                body=json.dumps({
                    "prompt": prompt,
                    "max_tokens_to_sample": 2000,
                    "temperature": 0.2
                })
            )
            
            response_body = json.loads(response['body'].read())
            return response_body.get('completion', '')
            
    except Exception as e:
        print(f"Error calling Bedrock: {e}")
        return get_mock_response()

def call_sagemaker(prompt):
    """Call a SageMaker endpoint to get a code fix"""
    try:
        runtime = boto3.client('sagemaker-runtime')
        endpoint_name = os.environ.get('SAGEMAKER_ENDPOINT_NAME')
        
        response = runtime.invoke_endpoint(
            EndpointName=endpoint_name,
            ContentType='application/json',
            Body=json.dumps({"prompt": prompt})
        )
        
        return json.loads(response['Body'].read().decode())['generated_text']
    except Exception as e:
        print(f"Error calling SageMaker: {e}")
        return get_mock_response()

def parse_llm_sections(response):
    """Parse the LLM response to extract all sections"""
    print(f"LLM Response: {response}")
    
    # Initialize sections dictionary
    sections = {
        'analysis': '',
        'solution_approach': '',
        'fixed_code': '',
        'verification_steps': '',
        'false_positive': '',
        'raw_response': response  # Store the full raw response for reference
    }
    
    # Extract sections using regex patterns
    try:
        # Extract Analysis section
        analysis_match = re.search(r'ANALYSIS:(.*?)(?=SOLUTION APPROACH:|SOLUTION_APPROACH:|$)', 
                                  response, re.DOTALL | re.IGNORECASE)
        if analysis_match:
            sections['analysis'] = analysis_match.group(1).strip()
            
        # Extract Solution Approach section
        solution_match = re.search(r'(?:SOLUTION APPROACH:|SOLUTION_APPROACH:)(.*?)(?=FALSE_POSITIVE:|FALSE POSITIVE:|$)', 
                                  response, re.DOTALL | re.IGNORECASE)
        if solution_match:
            sections['solution_approach'] = solution_match.group(1).strip()

        # Extract False Positive section
        false_positive_match = re.search(r'(?:FALSE_POSITIVE:|FALSE POSITIVE:)(.*?)(?=FIXED_CODE:|FIXED CODE:|$)', 
                                  response, re.DOTALL | re.IGNORECASE)
        if false_positive_match:
            sections['false_positive'] = false_positive_match.group(1).strip()
            
        # Extract Fixed Code section
        fixed_code_match = re.search(r'(?:FIXED_CODE:|FIXED CODE:)(.*?)(?=VERIFICATION_STEPS:|VERIFICATION STEPS:|$)', 
                                    response, re.DOTALL | re.IGNORECASE)
        if fixed_code_match:
            code_content = fixed_code_match.group(1).strip()
            # Try to extract code from code blocks if present
            code_block_match = re.search(r'```(?:c|cpp)?\s*(.*?)```', code_content, re.DOTALL)
            if code_block_match:
                sections['fixed_code'] = code_block_match.group(1).strip()
            else:
                sections['fixed_code'] = code_content
                
        # Extract Verification Steps section
        verification_match = re.search(r'(?:VERIFICATION_STEPS:|VERIFICATION STEPS:)(.*?)$', 
                                      response, re.DOTALL | re.IGNORECASE)
        if verification_match:
            sections['verification_steps'] = verification_match.group(1).strip()
            
    except Exception as e:
        print(f"Error parsing LLM sections: {e}")
    
    return sections
    

def format_github_output(fortify_result, source_file, function_name, category, line_number, 
                         analysis, solution_approach, modified_code, verification_steps, project_name, false_positive):
    """Format the output for GitHub issues and PRs"""
    # Create branch name
    safe_project_name = project_name.lower().replace(' ', '-')
    safe_category = category.replace(' ', '_').replace(':', '_').lower()
    branch_name = f"fix/{safe_project_name}/{safe_category}/{function_name.lower()}_{line_number}-t1"
    
    # Create issue/PR titles
    issue_title = f"Fix {category} in {source_file} at line {line_number}"
    pr_title = f"Fix {category} vulnerability in {source_file}"
    
    # Combine analysis and solution for reasoning
    reasoning = f"## Analysis\n{analysis}\n\n## Solution Approach\n{solution_approach}"
    
    # Create issue body with all sections
    issue_body = f"""## Security Issue: {category}
        **File:** {source_file}
        **Function:** {function_name}
        **Line:** {line_number}
        **Severity:** {fortify_result.get('severity', 'Unknown')}/5

        ### Issue Description
        {reasoning}

        ### Is False Positive?
        {false_positive}

        ### Proposed Fix
        ```c
        {modified_code}
        ```
        
        ### Verification Steps
        {verification_steps}
        
        ### Fortify Report Details

        {json.dumps(fortify_result, indent=2)}
    """

    # Create commit message
    commit_message = f"Fix {category} in {function_name} at {source_file}:{line_number}"

    # Create PR description
    pr_description = f"""This PR addresses a {category} vulnerability in {source_file} at line {line_number}.
        Issue

        The function {function_name} contains a {category} vulnerability.
        Fix

        {reasoning}
        
        Verification Steps
        {verification_steps}
        
        Fortify Report

        Severity: {fortify_result.get('severity', 'Unknown')}/5

        Instance ID: {fortify_result.get('InstanceID', 'N/A')}
    """
    #Create labels

    severity = int(fortify_result.get('severity', 0))
    issue_labels = ["security", category.lower().replace(' ', '-').replace(':', '-')]

    if severity >= 4:
        issue_labels.append("high-priority")
    elif severity >= 2:
        issue_labels.append("medium-priority")
    else:
        issue_labels.append("low-priority")

    pr_labels = issue_labels.copy()
    pr_labels.append("needs-review")

    return {
        "branchName": branch_name[:63], # Limit branch name length for Git
        "issueTitle": issue_title,
        "issueBody": issue_body,
        "filePath": source_file,
        "codeBody": modified_code,
        "commitMessage": commit_message,
        "prTitle": pr_title,
        "prDescription": pr_description,
        "issueLabels": issue_labels,
        "prLabels": pr_labels,
        "analysis": analysis, 
        "solution_approach": solution_approach,
        "fixed_code": modified_code,
        "verification_steps": verification_steps
    }