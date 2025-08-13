import boto3
import json
import os
from botocore.exceptions import ClientError

def main():
    existing_para_mappings = get_existing_parameter()
    diode_mappings = get_mappings()
    new_mappings = put_parameter(existing_para_mappings, diode_mappings)
    return new_mappings

def get_existing_parameter():
    ssm_client = boto3.client('ssm')
    try:
        response = ssm_client.get_parameter(
            Name='diode_account_mappings'
        )
        values = response['Parameter']['Value'].replace('[', '').replace(']', '').replace('"','').replace(' ', '').split(',')

        return values
    except ssm_client.exceptions.ParameterNotFound as e:
        print(f'Parameter not found.  Creating New Parameter')
        return []

def put_parameter(existing_para_mappings, diode_mappings):
    for mapping in diode_mappings:
        print(f"Checking {mapping}")
        if mapping not in existing_para_mappings:
            print(f"Adding {mapping} to parameter")
            existing_para_mappings.append(mapping)
    for mapping in existing_para_mappings:
        print(f"Checking {mapping}")
        if mapping not in diode_mappings:
            print(f"Removing {mapping} from parameter")
            existing_para_mappings.remove(mapping)

    ssm_client = boto3.client('ssm')
    response = ssm_client.put_parameter(
        Name='diode_account_mappings',
        Description='List of Diode account mappings',
        Value=json.dumps(existing_para_mappings),
        Type='StringList',
        Overwrite=True
    )
    print(response)
    return existing_para_mappings

def get_mappings():

    os.environ['AWS_DATA_PATH'] = 'models/'
    mappings = []
    session = boto3.Session()
    diode_client = session.client('diode', endpoint_url='https://diode.us-gov-west-1.amazonaws.com')

    response = diode_client.list_account_mappings()
    for mapping in response['accountMappingList']:
        mappings.append(mapping['mappingId'])
    print(mappings)
    return mappings
if __name__ == "__main__":
    main()
