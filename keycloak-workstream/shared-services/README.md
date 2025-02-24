# Welcome to Shared Services project

The CDK portion will create the necessary infrastructure needed to deploy the Shared Services Applications.

The `/lib/k8s/overlay/dev` contains the actual applications

It is possible to disable mTLS requirements if you don't want to support direct integration of smartcard authentication.

## Services
* Keycloak
* Squid Proxy

## Useful commands

* `npm run build`   compile typescript to js
* `npm run watch`   watch for changes and compile
* `npm run test`    perform the jest unit tests
* `npx cdk deploy`  deploy this stack to your default AWS account/region
* `npx cdk diff`    compare deployed stack with current state
* `npx cdk synth`   emits the synthesized CloudFormation template

## Prerequisites
* NodeJS 20.X
* OpenJDK 17 SDK
* A valid domain with management
* Able to create Domain Delegates from your primary Domain

## Notes on Update the Configuration
All configurations are stored inside the folder `env`. By default, it will use the `/env/dev/configuration.yaml` as environment **dev**.
In order use alternative `configuration.yaml` files, create a subfolder inside `/env` and export the environment variable **ENVIRONMENT** with the folder name.

## To Deploy the Stack
> Create DNS Hosted Zones and EKS Cluster(s)

1. Update or Create a new Configuration in `/env/<folder>`. The default environment if not specified environment variable `ENVIRONMENT` is **dev**, which is resolves to use the `configuration.yaml` inside `/env/dev`
   > NOTE: ENVIRONMENT variable is the name of the subfolder in `/env`. 
   ```bash
   export ENVIRONMENT=dev
   ```

2. Deploy the stack
   > NOTE: `--output`, `--debug` is **optional**
   ```bash
   cdk deploy --require-approval never --yes --all --debug --output $AWS_PROFILE.$AWS_DEFAULT_REGION.cdk.out --force
   ```
3. Execute the `aws eks update-config` command output (`clusterSharedServicesstackConfigCommand`) by the stack  
   Sample Command
   ```bash
   aws eks update-kubeconfig --name SharedServices --region us-east-1 --role-arn arn:aws:iam::992382523718:role/cluster-SharedServices-stack-cluster-admin-role
   ```

## To deploy the Pre-Deploy of the Kubernetes portion of Shared Services
> Deploy the core Shared Services k8s operator(s) and custom resource definitions

1. Build the mTLS AWS Load Balancer Service Provider Interface (SPI) Plugin for Keycloak
   ```bash
   cd plugins/java/keycloak/keycloak-spi-awsalb-mtls
   ./gradlew clean build
   cd -
   ```
2. Execute the following command once logged into the cluster
   ```bash
   kubectl apply --kustomize k8s/overlay/dev
   ```

## To deploy the Post-Deploy of the Kubernetes portion of Shared Services
> Deploy the Shared Services Deployments

1. Execute the following command once logged into the cluster
   ```bash
   kubectl apply --kustomize k8s/overlay/dev/post
   ```