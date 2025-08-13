# Dynamic NGINX Ingress for High-Side mTLS Deployment

## Automatic Behavior

The dev-dynamic overlay now automatically:
- **Low-side**: Uses ALB ingress (NGINX available as backup)
- **High-side**: Uses NGINX ingress (ALB fails gracefully when unavailable)
- **mTLS**: Automatically configured with DoD certificates

## Deployment

1. **Deploy hardened Keycloak**:
   ```bash
   kubectl apply -k k8s/overlay/dev-dynamic/
   ```

2. **Certificate validation**: Handled automatically by Keycloak's internal trust store

## What This Provides

✅ **Dual ingress support** (ALB + NGINX)  
✅ **Automatic high-side detection** (ALB fails gracefully)  
✅ **Certificate pass-through** to Keycloak for validation  
✅ **Supports all gov certificates** (PIV, ECA, DoD CAC)  
✅ **No manual certificate configuration** required  

## DNS Configuration

- **Low-side**: Point domain to ALB
- **High-side**: Point domain to NGINX LoadBalancer service