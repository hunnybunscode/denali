# Rolling Back to Previous Version of ImageBuilder Image

## Overview

This procedure provides immediate rollback steps by directly updating the Auto Scaling Group's Launch Template to use a previous AMI version.

### Step 1: Identify Previous AMI

1. Log into the Validation Account
2. Go to EC2 Image Builder
3. In left navigation pane, click "Image pipelines"
4. Under Image pipeline, select your pipeline name
5. Under Output images, find previous working version
6. Note the AMI ID of the version you want to roll back to

### Step 2. Rollback Auto Scaling Group Launch Template

1. In the EC2 Console, navigate to Auto Scaling Groups using left navigation pane
2. Click on the PipelineStack-AutoScalingGroup
3. Navigate to Launch Template section
4. Under "Launch template", click dropdown for "Version"
5. Select previous working version that matches identified AMI ID from Step 1
6. Click Update

### Step 3: Start Instance Refresh

1. Still in Auto Scaling Group
2. Click "Instance refresh" tab
3. Click "Start instance refresh"
4. Click "Start"

### Step 4: Monitor Progress

1. Stay on "Instance refresh" tab
2. Watch "Status" column for progress
3. Click refresh icon to update status
4. Monitor until status shows "Successful"

### Step 5: Verification Steps

1. Click "Instance management" tab in ASG
2. Verify new instances are Healthy
3. For each new instance:
   - Select instance
   - Check "Details" tab
   - Verify AMI ID matches intended version

## License.

© 2025 Amazon Web Services, Inc. or its affiliates. All Rights Reserved.
This AWS Content is provided subject to the terms of the AWS Customer
Agreement available at http://aws.amazon.com/agreement or other written
agreement between Customer and either Amazon Web Services, Inc. or Amazon
Web Services EMEA SARL or both
