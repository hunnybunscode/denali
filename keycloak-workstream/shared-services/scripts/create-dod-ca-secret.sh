#!/bin/bash
# Script to create DoD CA bundle secret for NGINX mTLS from hardened Keycloak pod

set -e

echo "Extracting DoD CA bundle from hardened Keycloak pod..."

# Get the first running Keycloak pod
POD_NAME=$(kubectl get pods -n keycloak -l app=keycloak -o jsonpath='{.items[0].metadata.name}')

if [ -z "$POD_NAME" ]; then
    echo "Error: No Keycloak pods found"
    exit 1
fi

echo "Using pod: $POD_NAME"

# Extract the DoD CA bundle from the hardened pod
kubectl exec -n keycloak "$POD_NAME" -- cat /etc/pki/ca-trust/extracted/pem/tls-ca-bundle.pem > /tmp/dod-ca-bundle.pem

# Create the secret for NGINX ingress
kubectl create secret generic dod-ca-bundle \
    --from-file=ca.crt=/tmp/dod-ca-bundle.pem \
    --namespace=keycloak \
    --dry-run=client -o yaml | kubectl apply -f -

echo "DoD CA bundle secret created successfully"
rm /tmp/dod-ca-bundle.pem