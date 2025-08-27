# Keycloak Deployment Scripts

This directory contains scripts to help with Keycloak and RDS deployment.

## pre-deploy-keycloak.sh

Creates RDS resources before deployment:
- Creates DB subnet group with subnet IDs from configuration.yaml
- Creates DBCluster YAML with security group ID from CDK stack
- Creates DBInstance YAML

Usage:
```bash
./scripts/pre-deploy-keycloak.sh [cluster-name] [region]
```

## post-deploy-keycloak.sh

Updates files with actual values after RDS cluster is created:
- Gets actual RDS cluster endpoint and creates service YAML
- Gets RDS master user secret name and updates SecretProviderClass
- Updates service account with actual IAM role ARN

Usage:
```bash
./post-deploy-keycloak.sh [cluster-name] [region]
```

## Deployment Workflow

1. **Deploy CDK Infrastructure**
   ```bash
   cdk deploy --all
   ```

2. **Generate RDS Resources**
   ```bash
   ./k8s/base/keycloak/scripts/pre-deploy-keycloak.sh
   ```

3. **Deploy Infrastructure Resources**
   ```bash
   kubectl apply -k k8s/overlay/dev
   ```

4. **Wait for RDS Cluster**
   ```bash
   kubectl get dbcluster -n keycloak
   # Wait for STATUS: available
   ```

5. **Update Files with Real Values**
   ```bash
   ./k8s/base/keycloak/scripts/post-deploy-keycloak.sh
   ```

6. **Deploy Applications**
   ```bash
   kubectl apply -k k8s/overlay/dev/post
   ```

## Notes

- Scripts auto-detect region from `env/dev/configuration.yaml`
- Security group ID is dynamically found from CloudFormation stack
- Uses CSI SecretProviderClass approach for secret mounting
- RDS endpoint and secret names are automatically discovered
- Service account uses IRSA for AWS authentication
- Both scripts handle missing resources gracefully with warnings