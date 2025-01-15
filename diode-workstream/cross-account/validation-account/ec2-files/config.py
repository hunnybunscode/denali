file_handler_config = {
    "filename": "/var/log/sqs_poller.log",
    "when": "midnight",
    "backupCount": 30
}

mime_mapping = {
    "txt": ["text/plain"],
    "json": ["application/json"],
    "infoset": ["application/xml"],
    "xml": ["application/xml"],
    "flac": ["audio/flac"],
    "zip": ["application/zip"],
    "wav": ["audio/wav", "audio/wave", "audio/x-wav"]
}

# File types that puremagic cannot validate
exempt_file_types = ["csv"]

# Populated and updated in the main function
ssm_params = {
    "/pipeline/AvScanQueueUrl": "",
    "/pipeline/QuarantineBucketName": "",
    "/pipeline/DataTransferIngestBucketName": "",
    "/pipeline/LongTermStorageBucketName": "",
    "/pipeline/QuarantineTopicArn": "",
    "/pipeline/ApprovedFileTypes": "",
    "/pipeline/DfdlApprovedFileTypes": "",
    "/pipeline/InvalidFilesBucketName": "",
    "/pipeline/InvalidFilesTopicArn": "",
}

# Populated and updated in the main function
approved_filetypes = []
