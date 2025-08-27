#!/bin/sh

# exit when any command fails
set -e

if
  command -v microdnf &> /dev/nul; then
    alias dnf='microdnf'
fi

# Clean up
rm -rf /tmp/*
dnf clean all
rm -rf /var/cache/dnf
