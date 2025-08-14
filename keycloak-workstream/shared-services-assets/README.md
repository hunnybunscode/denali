# Shared Services Asset Stack

This is a CDK Project that will create ECR Repositories and upload helm charts into their respective location

The `cdk.json` file tells the CDK Toolkit how to execute your app.

## Useful commands

* `npm run build`   compile typescript to js
* `npm run watch`   watch for changes and compile
* `npm run test`    perform the jest unit tests
* `npx cdk deploy`  deploy this stack to your default AWS account/region
* `npx cdk diff`    compare deployed stack with current state
* `npx cdk synth`   emits the synthesized CloudFormation template

## Development
### Prerequisites  
* CDK Typescript
* skopeo

1. Fetch libraries 
    ```bash
    npm ci 
    ```
    
### Fetch the helm chart and docker images
1. Update the configuration file to contain a list of fetch
2. Run the following command
  ```bash
  npm run fetch
  ```

### Deployment
1. Run the following
    ```bash
    cdk deploy --require-approval never --yes --all --debug --output $AWS_PROFILE.$AWS_DEFAULT_REGION.cdk.out
    ``
2. Upload the containers to the specified registry on account ECR
    ```bash
    WIP
    ```


### ORAS

```bash
curl -L https://github.com/oras-project/oras/releases/download/v1.2.3/oras_1.2.3_linux_amd64.tar.gz | tar --extract --gzip -C lib/lambda/oras/binary/amd64/bin oras
chmod +x lib/lambda/oras/binary/amd64/bin/oras
```