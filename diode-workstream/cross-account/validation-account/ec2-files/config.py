mime_mapping = {
    "txt": ["text/plain"],
    "json": ["application/json"],
    "infoset": ["application/xml"],
    "xml": ["application/xml"],
    "flac": ["audio/flac"],
    "zip": ["application/zip"],
    "wav": ["audio/wav", "audio/wave", "audio/x-wav"]
}

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
