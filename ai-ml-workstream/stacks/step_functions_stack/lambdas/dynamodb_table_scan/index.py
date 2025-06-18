import json
import boto3
from botocore.exceptions import ClientError

def lambda_handler(event, context):
    try:
        # Initialize DynamoDB client
        dynamodb = boto3.client('dynamodb')
        
        # Extract table name from event
        if 'tableName' not in event:
            raise ValueError("Table name not provided in event")
            
        table_name = event['tableName']
        
        # Perform DynamoDB scan
        try:
            response = dynamodb.scan(TableName=table_name)
        except ClientError as e:
            raise Exception(f"DynamoDB scan failed: {str(e)}")
            
        # Convert DynamoDB items to simplified JSON
        simplified_items = []
        
        for item in response.get('Items', []):
            simplified_item = {}
            for key, value in item.items():
                # Extract the actual value from DynamoDB format
                if 'S' in value:  # String
                    simplified_item[key] = value['S']
                elif 'N' in value:  # Number
                    simplified_item[key] = float(value['N'])
                elif 'BOOL' in value:  # Boolean
                    simplified_item[key] = value['BOOL']
                elif 'L' in value:  # List
                    simplified_item[key] = [
                        list_item.get('S', list_item.get('N', list_item.get('BOOL'))) 
                        for list_item in value['L']
                    ]
                elif 'M' in value:  # Map
                    simplified_item[key] = value['M']
                elif 'NULL' in value:  # Null
                    simplified_item[key] = None
                
            simplified_items.append(simplified_item)
            
        return {
            'items': simplified_items,
            'count': len(simplified_items)
        }
        
    except ValueError as e:
        raise ValueError(str(e))
    except Exception as e:
        raise Exception(f"Error processing DynamoDB scan: {str(e)}")