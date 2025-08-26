# Shared Services Asset Stack

This is a CDK TypeScript Project that will create ECR Repositories and upload helm charts into their respective location based on your environment configuration.

The default environment deployment: `dev` for internal development The suggested environment deployment: `standard-dev` to provide a sample set of configurations needed for a successful deployment.

This is project is especially helpful for deploying containers and helm charts in disconnected or isolated network AWS accounts.

## Prerequisites  
* NodeJS 20.X
* CDK Typescript
* skopeo

## Useful commands

* `npm run build`   compile typescript to js
* `npm run watch`   watch for changes and compile
* `npm run test`    perform the jest unit tests
* `npx cdk deploy`  deploy this stack to your default AWS account/region
* `npx cdk diff`    compare deployed stack with current state
* `npx cdk synth`   emits the synthesized CloudFormation template

## Deployment
To see the full possible configuration refer to `/lib/interfaces.d.ts`

1. Update or Create a new Configuration in `/env/<folder>`. The default environment if not specified environment variable `ENVIRONMENT` is **dev**, which resolves to use the configuration.yaml `configuration.yaml` inside `/env/dev`
   > NOTE: ENVIRONMENT variable is the name of the subfolder in `/env`. 
   ```bash
   export ENVIRONMENT=dev
   ```

2. Login to any docker registry using `skopeo login`
   Sample login 
   ```bash
   skopeo login registry1.dso.mil -u firstname.lastname.ctr 
   ```

3. Set the AWS Default Region if it is not `us-east-1`
   ```bash
   export AWS_DEFAULT_REGION=<region>
   ```

4. Get all dependencies
   ```bash
   npm ci
    ```

5. Run the following command to fetch the helm charts and docker container images
   ```bash
   npm run fetch
   ```

6. Run the following to deploy the stack
   > Make sure the terminal session has IAM credentials entered prior before executing
   > NOTE: `--output`, `--debug` is **optional**

    ```bash
    cdk context --clear; cdk deploy --require-approval never --yes --all --debug --output $AWS_PROFILE.$AWS_DEFAULT_REGION.cdk.out
    ```
7. Upload the containers to the specified registry on account ECR
    ```bash
    npm run push
    ```
