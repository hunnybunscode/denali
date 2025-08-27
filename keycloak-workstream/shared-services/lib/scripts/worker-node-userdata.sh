#!/bin/bash

CLUSTER_NAME={{clusterName}}

echo "Date: $(date)"

# Convert current date into pacific time
echo "Pacific Timezone: $(TZ=America/Los_Angeles date)"

# Check if nodeadm exist, otherwise run the legacy bootstrap
if ! command -v nodeadm &>/dev/null; then
  echo "Using legacy bootstrap script ..."

  /etc/eks/bootstrap.sh $CLUSTER_NAME
  exit 0
fi

echo "Using nodeadm bootstrap script ..."

# Generate the node-config.yaml file

CLUSTER_METADATA=$(aws eks describe-cluster --name $CLUSTER_NAME --output json)

# Use the AWS CLI to get the EKS cluster API endpoint
API_ENDPOINT=$(echo $CLUSTER_METADATA | jq --raw-output '.cluster.endpoint')

# Use the AWS CLI to get the EKS cluster certificate authority data
CERTIFICATE=$(echo $CLUSTER_METADATA | jq --raw-output '.cluster.certificateAuthority.data')

# Use the AWS CLI to get the EKS cluster CIDR block
CIDR=$(echo $CLUSTER_METADATA | jq --raw-output '.cluster.kubernetesNetworkConfig.serviceIpv4Cidr')

# MISC Fields
MAX_PODS={{MAX_PODS}}

cat <<EOF >/etc/eks/node-config.yaml
apiVersion: node.eks.aws/v1alpha1
kind: NodeConfig
spec:
  cluster:
    name: $CLUSTER_NAME
    apiServerEndpoint: $API_ENDPOINT
    certificateAuthority: $CERTIFICATE
    cidr: $CIDR
  kubeletConfig:
    maxPods: $MAX_PODS
    clusterDNS: 
    - 172.20.0.10
EOF

cat <<EOF >/etc/modules-load.d/istio-iptables.conf
# Enable the needed kernel modules for Istio
# See also: https://github.com/istio/istio/issues/23009

br_netfilter
nf_nat
xt_REDIRECT
xt_owner
iptable_nat
iptable_mangle
iptable_filter
EOF

echo "Confirming - $(sysctl net.ipv4.ip_forward)"

nodeadm init --config-source file:///etc/eks/node-config.yaml
systemctl enable kubelet.service
systemctl start kubelet.service

journalctl -u kubelet.service

reboot