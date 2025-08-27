<!--
(c) 2025 Amazon Web Services, Inc. All Rights Reserved.
This AWS content is subject to the terms of C2E Task Order 5502/HM047623F0080
-->

# Project Denali

## Table of Contents
- [Overview](#overview)
- [Project Structure](#project-structure)
- [CI/CD Configuration](#cicd-configuration)
- [Contributing](#contributing)

## Overview
Project Denali is a comprehensive AWS infrastructure and security platform designed for government and enterprise environments. It provides secure, scalable, and compliant cloud solutions across multiple workstreams.

## Project Structure

### 🔐 [Keycloak Workstream](./keycloak-workstream/)
**Purpose**: Identity and Access Management (IAM) solutions with hardened Keycloak deployments  
**Documentation**: [Keycloak Workstream README](./keycloak-workstream/Readme.md)

**Components:**
- **[Shared Services](./keycloak-workstream/shared-services/)** - EKS-based Keycloak with hardened security ([README](./keycloak-workstream/shared-services/README.md))
- **[Shared Services Assets](./keycloak-workstream/shared-services-assets/)** - Helper to move containers and helm charts for offline deployment ([README](./keycloak-workstream/shared-services-assets/README.md))
- **[STIG EKS Image Builder](./keycloak-workstream/stig-eks-imagebuilder/)** - STIG-compliant AMI creation ([README](./keycloak-workstream/stig-eks-imagebuilder/README.md))
- **[Limited Privilege Role Emulator](./keycloak-workstream/limited-privilage-role-emulator/)** - IAM role testing framework ([README](./keycloak-workstream/limited-privilage-role-emulator/README.md))
- **[IAM Deploy Role Calculator](./keycloak-workstream/iam-deploy-role-calculator/)** - Permission analysis tool ([README](./keycloak-workstream/iam-deploy-role-calculator/README.md))
- **[CDK Bootstrap](./keycloak-workstream/cdk-bootstrap/)** - CDK Toolkit bootstrap setup for target environment. Provides enablement of CDK based projects ([README](./keycloak-workstream/cdk-bootstrap/README.md))

### 📊 [DataOps Workstream](./DataOps-Workstream/)
**Purpose**: Data operations and analytics platform components  
**Documentation**: [DataOps README](./DataOps-Workstream/Readme.md)

### 🔌 [Diode Workstream](./diode-workstream/)
**Purpose**: Cross-account data transfer and validation solutions  
**Documentation**: [Diode README](./diode-workstream/Readme.md)

### 🖥️ [HPC Workstream](./hpc-workstream/)
**Purpose**: High-Performance Computing infrastructure and solutions  
**Documentation**: [HPC README](./hpc-workstream/Readme.md)

### 🖥️ [NiceDCV Workstream](./NiceDCV-Workstream/)
**Purpose**: Remote desktop and visualization solutions  
**Documentation**: [NiceDCV README](./NiceDCV-Workstream/Readme.md)

### 🏷️ [Subnet Tagger](./subnet-tagger/)
**Purpose**: VPC subnet management and tagging utilities  
**Documentation**: [Subnet Tagger README](./subnet-tagger/README.md) | [VPC Inventory](./subnet-tagger/VPC-INVENTORY.md)

### 🔗 [VPC Endpoints](./vpc-endpoints/)
**Purpose**: VPC endpoint management and configuration  
**Documentation**: [VPC Endpoints README](./vpc-endpoints/README.md)

## CI/CD Configuration

### [.gitlab-ci.yml](./.gitlab-ci.yml)
**Purpose**: GitLab CI/CD pipeline configuration  
**Features**:
- Automated testing and validation
- CDK NAG security scanning (AWS Internal)
- Multi-environment deployment (AWS Internal)
- Code quality checks (AWS Internal)

### [.pre-commit-config.yaml](./.pre-commit-config.yaml)
**Purpose**: Pre-commit hooks for code quality enforcement  
**Features**:
- Code formatting and linting
- Security scanning
- Commit message validation
- Prevents committing sensitive data



## Architecture Overview

```
┌──────────────────────────────────────────────────────────────┐
│                     Project Denali                           │
├──────────────────────────────────────────────────────────────┤
│  Identity & Access     │  Data Operations  │  Networking     │
│  (Keycloak)            │  (DataOps)        │  (VPC/Endpoints)│
├──────────────────────────────────────────────────────────────┤
│  High Performance      │  Remote Desktop   │  Cross-Account  │
│  Computing (HPC)       │  (NiceDCV)        │  (Diode)        │
└──────────────────────────────────────────────────────────────┘
```

## Development Workflow

### Branch Strategy
- `main` - Production-ready code
- `feature/*` - Feature development
- `hotfix/*` - Critical fixes

### Code Quality
- Pre-commit hooks for linting (see `.pre-commit-config.yaml`)
- Automated testing via GitLab CI (see `.gitlab-ci.yml`)
- CDK NAG security scanning
- Infrastructure as Code (IaC) standards

## Deployment Environments

Deployment environments and AWS account configurations vary by organization and deployment requirements. Each workstream can be deployed to development, staging, or production environments as needed.

## Support & Documentation

### Getting Help
1. Check workstream-specific README files (linked above)
2. Review architecture diagrams
3. Consult deployment guides
4. Contact project maintainers

### Key Documentation
- [Hardened Deployment Guide](./keycloak-workstream/shared-services/HARDENED-DEPLOYMENT.md)
- [ECR Pull Through Cache](./keycloak-workstream/ECR-Cache-Discovery/ECR-PULLTHROUGH.md)
- Individual workstream README files (see links in Project Structure)

## Contributing

1. Install pre-commit hooks: `pre-commit install`
2. Create feature branch from `main`
3. Follow coding standards and conventions
4. Add/update documentation
5. Submit merge request with clear description
6. Ensure all CI/CD checks pass

---

**Project Denali** - Secure, Scalable, Compliant Cloud Infrastructure