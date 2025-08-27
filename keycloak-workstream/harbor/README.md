# Harbor Deployment Guide

This guide explains how to perform a basic Harbor deployment to Kubernetes using Helm with custom configuration values.
Note: For a full list of configuration options visit https://artifacthub.io/packages/helm/bitnami/harbor

## Prerequisites

- Kubernetes cluster
- Helm v3 installed
- AWS Load Balancer Controller installed in the cluster
- ACM Certificate for the hostname
- DNS access to create CNAME record pointing to alb

## Installation Steps

1. Download Harbor Helm Chart:
```bash
helm repo add harbor https://helm.goharbor.io
helm fetch harbor/harbor --untar
```
2. Install the Harbor helm chart
The harbor-values.yaml file serves as an override configuration file. By default it deploys an internet-facing application load balancer as the ingress.
```bash
kubectl create ns harbor
helm install harbor/harbor -f harbor-vaules.yaml -n harbor
```

3. Login to Harbor
Navigate to the specified hostname to login to Harbor through the Web UI. The user name will be admin and the password can be found by running the below command:
```bash
kubectl get secret --namespace harbor harbor-core-envvars -o jsonpath="{.data.HARBOR_ADMIN_PASSWORD}" | base64 --decode
```
