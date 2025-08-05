from boto3 import client
import json
import utils



def lambda_handler(event, context):
    # bucket = event['Records'][0]['s3']['bucket']['name']
    # key = event['Records'][0]['s3']['object']['key']
    test_bucket = "test-2890285"
    test_key = "mytestfile.txt"


    try:
        destination_map_key = utils.get_dest_tag(test_bucket, test_key)
        buckets = utils.get_key_mappings(destination_map_key)
        utils.copy_files(buckets, test_bucket, test_key)
    except Exception as e:
        print(f"Error processing file {test_key} from bucket {test_bucket}: {str(e)}")
        raise


