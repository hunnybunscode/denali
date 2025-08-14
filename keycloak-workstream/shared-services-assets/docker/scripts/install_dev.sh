#!/bin/sh

# exit when any command fails
set -e

# Target architecture: linux/x86-64

NODEJS_INSTALL_URL=https://rpm.nodesource.com/setup_20.x

AWSCLI_INSTALL_URL=https://awscli.amazonaws.com

KUBECTL_INSTALL_URL=https://dl.k8s.io/release
KUBECTL_VERSION=v1.30.12

EKSCTL_INSTALL_URL=https://github.com/eksctl-io/eksctl/releases/latest

K9S_INSTALL_URL=https://github.com/derailed/k9s/releases/latest

ARCH=$(uname --machine)
OS=$(uname --kernel-name | awk '{print tolower($0)}')

if [ "$ARCH" == "x86_64" ]; then
  arch="amd64"
elif [ "$ARCH" == "aarch64" ]; then
  arch="arm64"
else
  echo "Unsupported architecture: $ARCH"
  exit 1
fi

if [ $(command -v microdnf) &>/dev/nul ]; then
  alias dnf='microdnf'

  # Export functions to use in the script
  set -a

  yum() {
    microdnf "$@"
  }

  set +a
fi

# RHEL Repo based installs
dnf install --assumeyes \
  bsdtar \
  wget \
  shadow-utils \
  ca-certificates \
  sudo \
  zip \
  less \
  unzip \
  vim \
  jq \
  git \
  openssl \
  iputils \
  nc \
  bind-utils \
  make \
  python-pip \
  python3.12 \
  python3.12-pip

ln -s $(which python3.12) /usr/local/bin/python
ln -s $(which pip3.12) /usr/local/bin/pip

# Configure Non-RHEL related items
curl --silent --location $NODEJS_INSTALL_URL | bash -

# Non-RHEL Repo based Installs
dnf install --assumeyes \
  nodejs

# Install AWS CLI
wget --quiet --output-document - $AWSCLI_INSTALL_URL/awscli-exe-$OS-$ARCH.zip | bsdtar --extract --file - --directory /tmp
bash /tmp/aws/install
chmod a+x /usr/local/bin/aws*
rm -rf /usr/local/aws-cli/v2/current/dist/awscli/examples

# Install AWS CLI - SSM Manager Plugin
dnf install --assumeyes https://s3.amazonaws.com/session-manager-downloads/plugin/latest/linux_64bit/session-manager-plugin.rpm

# Install AWS CDK
npm install --global aws-cdk

# Install kubectl
wget --quiet --output-document /usr/local/bin/kubectl $KUBECTL_INSTALL_URL/$KUBECTL_VERSION/bin/linux/amd64/kubectl
chmod a+x /usr/local/bin/kubectl

# Install eksctl
curl --location $EKSCTL_INSTALL_URL/download/eksctl_$(uname --kernel-name)_$arch.tar.gz | tar -xz --directory /usr/local/bin
chmod a+x /usr/local/bin/eksctl

# Install K9s
dnf install --assumeyes $K9S_INSTALL_URL/download/k9s_$(uname --kernel-name)_$arch.rpm

# Install helm
curl https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3 | bash

# Install skopeo
dnf install --assumeyes skopeo

# Check for updates
if [[ ${UPDATE_OS} == "true" ]]; then
  echo "Updating OS ..."
  dnf upgrade --assumeyes
fi
