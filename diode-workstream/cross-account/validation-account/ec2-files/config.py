import os


simulate_av_scan = True if os.getenv("av_scan_mode") == "Test" else False
resource_suffix = os.getenv("resource_suffix") or ""

file_handler_config = {
    "filename": "/var/log/sqs_poller.log",
    "when": "midnight",
    "backupCount": 30,
}

mime_mapping = {
    "txt": ["text/plain"],
    "json": ["application/json"],
    "infoset": ["application/xml"],
    "xml": ["application/xml"],
    "flac": ["audio/flac"],
    "zip": ["application/zip"],
    "wav": ["audio/wav", "audio/wave", "audio/x-wav"],
}

# File types that puremagic cannot validate
exempt_file_types = ["csv"]

# Populated and updated in the main function
ssm_params = {
    f"/pipeline/AvScanQueueUrl-{resource_suffix}": "",
    f"/pipeline/QuarantineBucketName-{resource_suffix}": "",
    f"/pipeline/DataTransferIngestBucketName-{resource_suffix}": "",
    f"/pipeline/LongTermStorageBucketName-{resource_suffix}": "",
    f"/pipeline/QuarantineTopicArn-{resource_suffix}": "",
    f"/pipeline/ApprovedFileTypes-{resource_suffix}": "",
    f"/pipeline/DfdlApprovedFileTypes-{resource_suffix}": "",
    f"/pipeline/InvalidFilesBucketName-{resource_suffix}": "",
    f"/pipeline/InvalidFilesTopicArn-{resource_suffix}": "",
}

# Populated and updated in the main function
approved_filetypes: list[str] = []
