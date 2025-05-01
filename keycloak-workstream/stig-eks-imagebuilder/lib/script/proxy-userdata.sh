#!/bin/bash -e

# This is proxy fallback
cat <<EOF >/etc/environment
  export HTTP_PROXY={{HTTP_PROXY}}
  export HTTPS_PROXY={{HTTPS_PROXY}}
  export NO_PROXY='{{NO_PROXY}}'
EOF

cat <<EOF >/etc/systemd/environment
  HTTP_PROXY={{HTTP_PROXY}}
  HTTPS_PROXY={{HTTPS_PROXY}}
  NO_PROXY='{{NO_PROXY}}'
EOF

chmod a+r /etc/systemd/environment

# Source environment
source /etc/environment

printenv

# Override yum to use http_proxy
cat <<EOF >>/etc/yum.conf
proxy=$HTTPS_PROXY
EOF

# Configure the ssm agent with the proxy
mkdir -p /etc/systemd/system/amazon-ssm-agent.service.d
cat <<EOF >/etc/systemd/system/amazon-ssm-agent.service.d/proxy.conf
[Service]
EnvironmentFile=/etc/systemd/environment
PassEnvironment=HTTP_PROXY,HTTPS_PROXY,NO_PROXY
EOF

# Enable debug logs for aws ssm agent
if [ -f /etc/amazon/ssm/seelog.xml.template ]; then
  sed -i 's/minlevel="info"/minlevel="debug"/g' /etc/amazon/ssm/seelog.xml.template
fi

# Check if amazon-ssm-agent service exist
if systemctl list-unit-files --type service | grep amazon-ssm-agent.service; then
  systemctl daemon-reload
  systemctl restart amazon-ssm-agent
fi

# Configure the kubelet with the proxy
mkdir -p /etc/systemd/system/kubelet.service.d
cat <<EOF >/etc/systemd/system/kubelet.service.d/proxy.conf
[Service]
EnvironmentFile=/etc/environment
EOF
