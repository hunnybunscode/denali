import boto3
import time
import json
import logging

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

def wait_for_table_active(dynamodb, table_name, max_attempts=60):
    """
    Wait for table to become active, with timeout.

    Args:
        dynamodb: DynamoDB client
        table_name: Name of the table to wait for
        max_attempts: Maximum number of attempts (default 60, 5 minutes)

    Returns:
        dict: Table description when active

    Raises:
        Exception: If timeout is reached or table enters invalid state
    """
    for i in range(max_attempts):
        try:
            response = dynamodb.describe_table(TableName=table_name)
            status = response['Table']['TableStatus']

            if status == 'ACTIVE':
                logger.info(f"Table {table_name} is now ACTIVE")
                return response['Table']
            elif status == 'DELETING':
                raise Exception(f"Table {table_name} is being deleted and cannot be used")
            else:
                logger.info(f"Table {table_name} status is {status}, waiting... (attempt {i+1}/{max_attempts})")
                time.sleep(5)  # Wait 5 seconds between checks

        except dynamodb.exceptions.ResourceNotFoundException:
            raise Exception(f"Table {table_name} was deleted while waiting for it to become active")
        except Exception as e:
            if "is being deleted" in str(e):
                raise e
            logger.warning(f"Error checking table status: {str(e)}")
            time.sleep(5)

    raise Exception(f"Timeout waiting for table {table_name} to become active after {max_attempts * 5} seconds")

def validate_table_configuration(existing_table, expected_config):
    """
    Validate that existing table configuration matches expected configuration.

    Args:
        existing_table: Table description from describe_table
        expected_config: Expected configuration parameters

    Returns:
        dict: Validation results with warnings if any
    """
    warnings = []

    # Check key schema
    existing_key_schema = existing_table.get('KeySchema', [])
    expected_key_schema = expected_config.get('keySchema', [])

    if existing_key_schema != expected_key_schema:
        warnings.append(f"Key schema mismatch - existing: {existing_key_schema}, expected: {expected_key_schema}")

    # Check billing mode
    existing_billing_mode = existing_table.get('BillingModeSummary', {}).get('BillingMode', 'PROVISIONED')
    expected_billing_mode = expected_config.get('billingMode', 'PROVISIONED')

    if existing_billing_mode != expected_billing_mode:
        warnings.append(f"Billing mode mismatch - existing: {existing_billing_mode}, expected: {expected_billing_mode}")

    return {
        'valid': len(warnings) == 0,
        'warnings': warnings
    }

def lambda_handler(event, context):
    """
    Create DynamoDB table with graceful handling of existing tables.

    This function will:
    1. Check if table already exists
    2. If exists and ACTIVE, return success with table info
    3. If exists but not ACTIVE, wait for it to become ACTIVE
    4. If doesn't exist, create it and wait for ACTIVE status
    5. Optionally validate table configuration matches expectations
    """
    try:
        dynamodb = boto3.client('dynamodb')
        table_name = event['tableName']
        key_schema = event['keySchema']
        attribute_definitions = event['attributeDefinitions']
        billing_mode = event.get('billingMode', 'PROVISIONED')
        validate_config = event.get('validateConfiguration', False)

        logger.info(f"Processing table operation for: {table_name}")

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
            existing_table = response['Table']
            current_status = existing_table['TableStatus']

            logger.info(f"Table {table_name} already exists with status: {current_status}")

            # Handle different table states
            if current_status == 'ACTIVE':
                logger.info(f"Table {table_name} is already ACTIVE")

                # Optionally validate configuration
                validation_result = {'valid': True, 'warnings': []}
                if validate_config:
                    validation_result = validate_table_configuration(existing_table, event)
                    if validation_result['warnings']:
                        logger.warning(f"Configuration validation warnings: {validation_result['warnings']}")

                return {
                    'statusCode': 200,
                    'body': json.dumps({
                        'message': f"Table {table_name} already exists and is ACTIVE",
                        'tableArn': existing_table['TableArn'],
                        'tableStatus': current_status,
                        'existed': True,
                        'validation': validation_result
                    })
                }

            elif current_status in ['CREATING', 'UPDATING']:
                logger.info(f"Table {table_name} is {current_status}, waiting for ACTIVE status")

                # Wait for table to become active
                active_table = wait_for_table_active(dynamodb, table_name)

                return {
                    'statusCode': 200,
                    'body': json.dumps({
                        'message': f"Table {table_name} was {current_status} and is now ACTIVE",
                        'tableArn': active_table['TableArn'],
                        'tableStatus': 'ACTIVE',
                        'existed': True,
                        'waitedForActive': True
                    })
                }

            elif current_status == 'DELETING':
                raise Exception(f"Table {table_name} is currently being deleted and cannot be used")

            else:
                raise Exception(f"Table {table_name} is in unexpected state: {current_status}")

        except dynamodb.exceptions.ResourceNotFoundException:
            # Table doesn't exist, create it
            logger.info(f"Table {table_name} does not exist, creating it")

            try:
                response = dynamodb.create_table(**create_table_params)
                logger.info(f"Table creation initiated for {table_name}")

                # Wait for table to become active
                active_table = wait_for_table_active(dynamodb, table_name)

                return {
                    'statusCode': 200,
                    'body': json.dumps({
                        'message': f"Table {table_name} created successfully and is now ACTIVE",
                        'tableArn': active_table['TableArn'],
                        'tableStatus': 'ACTIVE',
                        'existed': False,
                        'created': True
                    })
                }

            except Exception as e:
                logger.error(f"Error creating table {table_name}: {str(e)}")
                raise Exception(f"CreateTableError: {str(e)}")

    except Exception as e:
        logger.error(f"Lambda execution failed: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps({
                'error': str(e),
                'message': f"Failed to process table operation for {event.get('tableName', 'unknown')}"
            })
        }