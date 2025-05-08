#!/bin/bash

mkdir -p /etc/eks/

TOKEN=$(curl -X PUT "http://169.254.169.254/latest/api/token" -H "X-aws-ec2-metadata-token-ttl-seconds: 21600")
MAC=$(curl -H "X-aws-ec2-metadata-token: $TOKEN" -s http://169.254.169.254/latest/meta-data/mac/)
VPC_CIDR=$(curl -H "X-aws-ec2-metadata-token: $TOKEN" -s http://169.254.169.254/latest/meta-data/network/interfaces/macs/$MAC/vpc-ipv4-cidr-blocks | xargs | tr ' ' ',')

CLUSTER_METADATA=$(aws eks describe-cluster --name $CLUSTER_NAME --output json)
CLUSTER_SERVICE_CIDR=$(echo $CLUSTER_METADATA | jq --raw-output '.cluster.kubernetesNetworkConfig.serviceIpv4Cidr')

printenv

# Configure the kubelet with the proxy
mkdir -p /etc/systemd/system/kubelet.service.d
cat <<EOF >/etc/systemd/system/kubelet.service.d/proxy.conf
[Service]
EnvironmentFile=/etc/systemd/environment
EOF

# Configure the containerd with the proxy
mkdir -p /etc/systemd/system/containerd.service.d
cat <<EOF >/etc/systemd/system/containerd.service.d/proxy.conf
[Service]
EnvironmentFile=/etc/systemd/environment
EOF

# Configure Docker with the proxy
mkdir -p /etc/systemd/system/docker.service.d
cat <<EOF >/etc/systemd/system/docker.service.d/proxy.conf
[Service]
EnvironmentFile=/etc/systemd/environment
EOF

systemctl daemon-reload

if systemctl list-unit-files --type service | grep containerd.service; then
  systemctl restart containerd
fi

if systemctl list-unit-files --type service | grep docker.service; then
  systemctl restart docker
fi
