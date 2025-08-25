# Validation Account Architecture Diagrams

This folder contains architecture diagrams for the AFTAC validation account infrastructure.

## Prerequisites

1. Install Python dependencies:

   ```bash
   pip install -r requirements.txt
   ```

2. Install Graphviz (required for diagram generation):
   - **Windows**: Download from https://graphviz.org/download/ or use chocolatey: `choco install graphviz`
   - **macOS**: `brew install graphviz`
   - **Linux**: `sudo apt-get install graphviz` (Ubuntu/Debian) or `sudo yum install graphviz` (RHEL/CentOS)

## Generate Architecture Diagram

Run the Python script to generate the architecture diagram:

```bash
python validation-account-architecture.py
```

This will create `validation-account-architecture.png` showing the complete infrastructure architecture.

## Architecture Overview

The validation account includes:

- **VPC with public/private subnets**
- **EC2 instances** for validation processing and image building
- **Lambda functions** for file processing, tagging, and result handling
- **S3 buckets** for ingestion, validated data, and quarantine
- **SQS/SNS** for messaging and notifications
- **API Gateway** for external access
- **Client VPN** for secure access
- **SFTP server** for file transfers
- **CloudWatch, SSM, Secrets Manager** for monitoring and management

## Files

- `validation-account-architecture.py` - Main diagram generation script
- `requirements.txt` - Python dependencies
- `README.md` - This documentation file
