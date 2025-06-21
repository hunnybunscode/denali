import os

instance_info = {"instance_id": ""}

resource_suffix = os.getenv("resource_suffix") or ""

file_handler_config = {
    "filename": "/var/log/sqs_poller.log",
    "when": "midnight",
    "backupCount": 7,
}

# Populated and updated in the main function
ssm_params = {
    f"/pipeline/DataTransferIngestBucketName-{resource_suffix}": "",
    f"/pipeline/QuarantineBucketName-{resource_suffix}": "",
    f"/pipeline/InvalidFilesBucketName-{resource_suffix}": "",
    f"/pipeline/DfdlInputBucketName-{resource_suffix}": "",
    f"/pipeline/AvScanQueueUrl-{resource_suffix}": "",
    f"/pipeline/ApprovedFileTypes-{resource_suffix}": "",
    f"/pipeline/DfdlApprovedFileTypes-{resource_suffix}": "",
    f"/pipeline/ExemptFileTypes-{resource_suffix}": "",
    f"/pipeline/MimeMapping-{resource_suffix}": "",
    f"/pipeline/QuarantineTopicArn-{resource_suffix}": "",
    f"/pipeline/InvalidFilesTopicArn-{resource_suffix}": "",
}
