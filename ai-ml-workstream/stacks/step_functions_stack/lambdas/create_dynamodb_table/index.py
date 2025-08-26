import boto3
import time
import json
import random

class TableAlreadyExistsError(Exception):
    pass

def wait_for_table_active(dynamodb, table_name, max_attempts=60):
    """Wait for table to become active, with timeout"""
    for i in range(max_attempts):
        try:
            response = dynamodb.describe_table(TableName=table_name)
            status = response['Table']['TableStatus']
            if status == 'ACTIVE':
                return True
            print(f"Table status is {status}, waiting... (attempt {i+1}/{max_attempts})")
            time.sleep(5)  # Wait 5 seconds between checks
        except Exception as e:
            print(f"Error checking table status: {str(e)}")
            time.sleep(5)
    raise Exception(f"Timeout waiting for table {table_name} to become active")

def lambda_handler(event, context):
    dynamodb = boto3.client('dynamodb')
    table_name = event['tableName']
    key_schema = event['keySchema']
    attribute_definitions = event['attributeDefinitions']
    billing_mode = event.get('billingMode', 'PROVISIONED')
    
    create_table_params = {
        'TableName': table_name,
        'KeySchema': key_schema,
        'AttributeDefinitions': attribute_definitions,
        'BillingMode': billing_mode
    }
    
    if billing_mode == 'PROVISIONED':
        provisioned_throughput = event.get('provisionedThroughput', {
            'ReadCapacityUnits': 5,
            'WriteCapacityUnits': 5
        })
        create_table_params['ProvisionedThroughput'] = provisioned_throughput
    
    if 'localSecondaryIndexes' in event:
        create_table_params['LocalSecondaryIndexes'] = event['localSecondaryIndexes']
    
    if 'globalSecondaryIndexes' in event:
        create_table_params['GlobalSecondaryIndexes'] = event['globalSecondaryIndexes']

    if 'streamSpecification' in event:
        create_table_params['StreamSpecification'] = event['streamSpecification']

    if 'sseSpecification' in event:
        create_table_params['SSESpecification'] = event['sseSpecification']
    
    if 'tags' in event:
        create_table_params['Tags'] = event['tags']
        
    try:
        # Check if table exists
        response = dynamodb.describe_table(TableName=table_name)
        current_status = response['Table']['TableStatus']
        print(f"Table {table_name} already exists with status {current_status}")
        
        error_details = {
            'tableName': table_name,
            'tableStatus': current_status,
            'message': f"Table {table_name} already exists with status {current_status}"
        }
        raise TableAlreadyExistsError(json.dumps(error_details))
        
    except TableAlreadyExistsError as e:
        raise Exception("TableAlreadyExists: " + str(e))
    except dynamodb.exceptions.ResourceNotFoundException:
        # Table doesn't exist, create it
        try:
            print(f"Creating table {table_name}")
            response = dynamodb.create_table(**create_table_params)
            
            # Wait for table to become active
            wait_for_table_active(dynamodb, table_name)
            
            return {
                'statusCode': 200,
                'body': json.dumps({
                    'message': f"Table {table_name} created successfully and is now active",
                    'tableArn': response['TableDescription']['TableArn']
                })
            }
        except Exception as e:
            print(f"Error creating table: {str(e)}")
            raise Exception("CreateTableError: " + str(e))