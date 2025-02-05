#!/bin/bash

# Ensure security group allows TCP traffic out 3128
# Update these variables and put ec2-files into a bucket with a prefix of ec2-files

export region="us-gov-west-1"
export av_scan_mode="Test" # Test | Live
export resource_suffix="test2"
export ec2_files_bucket="test-ec2-files-bucket" # Use existing one or create one
export proxy_server="10.162.216.148" # http://proxy.tr.pri.vi2e.io

export http_proxy=$proxy_server:3128
export https_proxy=$proxy_server:3128
export NO_PROXY="169.254.169.254,vi2e.io,s3.$region.amazonaws.com"

# Install SSM Agent
ARCH=$(arch)
if [ "$ARCH" = "arm64" ]; then
    yum install -y https://s3.$region.amazonaws.com/amazon-ssm-$region/latest/linux_arm64/amazon-ssm-agent.rpm
else # x86_64
    yum install -y https://s3.$region.amazonaws.com/amazon-ssm-$region/latest/linux_amd64/amazon-ssm-agent.rpm
fi

cat << EOF > /etc/profile.d/proxy.sh
#!/bin/bash
export http_proxy=$proxy_server:3128
export https_proxy=$proxy_server:3128
export NO_PROXY="169.254.169.254,vi2e.io,s3.$region.amazonaws.com"
EOF
chmod 755 /etc/profile.d/proxy.sh
/etc/profile.d/proxy.sh

# For troubleshooting, if necessary
cat << EOF > /etc/profile.d/set_env.sh
#!/bin/bash
export av_scan_mode=$av_scan_mode
export resource_suffix=$resource_suffix
EOF
chmod 755 /etc/profile.d/set_env.sh
/etc/profile.d/set_env.sh

# Install python3.11, pip, and other libraries
yum install -y python3.11 python3.11-pip curl unzip
python3.11 -m pip install pip --upgrade
python3.11 -m pip install boto3 puremagic pyjwt

# Update all packages
yum update -y

# Install awscli
ARCH=$(uname -m)
curl "https://awscli.amazonaws.com/awscli-exe-linux-$ARCH.zip" -o /tmp/awscliv2.zip
echo Unzipping awscliv2.zip
unzip -q -o /tmp/awscliv2.zip
BINARY=/usr/local/aws-cli/v2/current/bin/aws

# If the binary exists, update it
if [ -x $BINARY ]; then
    echo Updating awscli v2
    ./aws/install --update
else
    echo Installing awscli v2
    ./aws/install
fi

# Download all files from S3 bucket
aws s3 cp s3://$ec2_files_bucket/ec2-files/ /usr/bin/validation-pipeline/ --recursive

# Install CloudWatch Agent
ARCH=$(arch)
if [ "$ARCH" = "arm64" ]; then
    curl https://amazoncloudwatch-agent-$region.s3.$region.amazonaws.com/redhat/arm64/latest/amazon-cloudwatch-agent.rpm -o /tmp/amazon-cloudwatch-agent.rpm
else # x86_64
    curl https://amazoncloudwatch-agent-$region.s3.$region.amazonaws.com/redhat/amd64/latest/amazon-cloudwatch-agent.rpm -o /tmp/amazon-cloudwatch-agent.rpm
fi
rpm -U /tmp/amazon-cloudwatch-agent.rpm

# Enable CloudWatch Agent
mv /usr/bin/validation-pipeline/amazon-cloudwatch-agent.json /opt/aws/amazon-cloudwatch-agent/etc/amazon-cloudwatch-agent.json
systemctl enable amazon-cloudwatch-agent

# Enable SQS Poller Service
# Replaces the placeholder ("") with actual environment variables
sed -i "s/\"\"/av_scan_mode=$av_scan_mode resource_suffix=$resource_suffix/g" /usr/bin/validation-pipeline/sqs_poller.service
mv /usr/bin/validation-pipeline/sqs_poller.service /etc/systemd/system/sqs_poller.service
systemctl enable sqs_poller.service
systemctl start sqs_poller.service