import boto3
import logging
import os
import zipfile
import zipfile_validator
import validator
import subprocess
import clamscan

s3_client = boto3.client('s3', region_name = 'us-gov-west-1')
logging.basicConfig(format='%(message)s', filename='/var/log/messages', level=logging.INFO)
def get_file(bucket, key, receipt_handle, approved_filetypes, mime_mapping):
    logging.info('Getting File')
    file_path = '/usr/bin/files/'
    files = os.listdir(file_path)
    logging.info(f'Number of files: {len(files)}')
    if len(files) != 0:
        logging.info('emptying directory')
        for file in files:
            subprocess.run(['rm', '-r', f'{file_path}{file}'])

    # Identify file extension
    ext = key.split('.',-1)
    ext = ext[-1]
    logging.info(f'Extension: {ext}') 
    if ext == 'csv':
        logging.info(f'File {key} is a .csv file.  Proceeding to scanner.')
        clamscan.scanner(bucket, key, receipt_handle)
    elif ext in approved_filetypes:
        if ext == 'zip':
            try:
                logging.info(f'Downloading {key} to local directory')
                s3_client.download_file(
                    Bucket = bucket,
                    Key = key,
                    Filename = '/usr/bin/zipfiles/zipfile.zip'
                )
                logging.info(f'Attempting to unzip {key} from {bucket}...')
                #Unzip file
                #Exract Zip File
            except Exception as e:
                logging.error(f'Exception ocurred copying file to local storage: {e}')
            try:
                with zipfile.ZipFile('/usr/bin/zipfiles/zipfile.zip') as zip_file:
                    ## extact files from zip into tmp location
                    zip_file.extractall(path='/usr/bin/files/')

                logging.info(f'{key} successfully unzipped.')
            except zipfile.BadZipFile as bzf:
                logging.error(f'BadZipFile exception ocurred: {bzf}')

            #Validate file
            
            zipfile_validator.validator(bucket, key, receipt_handle, approved_filetypes, mime_mapping)
        else:
            logging.info(f'Attempting to copy {key} to local storage from {bucket}...')
            try:
                #Copy file to Local Storage
                
                s3_client.download_file(
                    Bucket = bucket,
                    Key = key,
                    Filename = f'/usr/bin/files/file_to_scan.{ext}'
                )
                validator.validator(bucket, key, receipt_handle, approved_filetypes, mime_mapping)
            except Exception as e:
                logging.error(f'Exception ocurred copying file to local storage: {e}')  
    else:
        logging.info(f'Extension {ext} not included in list of allowed filetypes')
        try:
            #obtain Quarantine Bucket name via Parameter Store
            ssm_client = boto3.client('ssm', region_name = 'us-gov-west-1')
            quarantine_bucket_parameter = ssm_client.get_parameter(
                Name='/pipeline/QuarantineBucketName'
            )
            quarantine_bucket = quarantine_bucket_parameter['Parameter']['Value']
            dest_bucket = quarantine_bucket
            validator.quarantine_file(bucket, key, dest_bucket, receipt_handle)
        except Exception as e:
            logging.error(f'Exception ocurred quarantining file: {e}')
            





