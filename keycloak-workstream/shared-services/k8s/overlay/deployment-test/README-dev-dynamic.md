# NGINX Ingress for High-Side Deployment

## Overview
NGINX ingress provides backup ingress capability when ALB is unavailable (high-side/isolated environments).

## ⚠️ IMPORTANT: Customize Before Deployment

**Before deploying, you MUST customize the placeholder file:**

1. **Edit `keycloak-nginx-ingress.yaml`**
2. **Replace ALL PLACEHOLDER values** with environment-specific configuration:
   - Domain names (replace `keycloak.example.com`)
   - TLS certificate secret name
   - Keycloak service name and port
3. **Add to kustomization.yaml** resources list

## Deployment Flow

1. **Automatic**: NGINX controller deploys via CDK (isolated clusters only)
2. **Manual**: Customize and deploy NGINX ingress YAML
3. **Result**: Dual ingress support (ALB + NGINX) with automatic failover

## DNS Configuration

- **Low-side**: Point domain to ALB
- **High-side**: Point domain to NGINX LoadBalancer service (`kubectl get svc -n kube-system`)