#!/usr/bin/env ts-node

import * as path from "path";
import * as util from "util";
import { globSync } from "glob";
import { execSync } from "child_process";

namespace AWS {
  export namespace STS {
    export interface Identity {
      UserId: string;
      Account: string;
      Arn: string;
    }
  }

  export namespace ECR {
    export interface Repository {
      repositories: {
        repositoryArn: string;
        registryId: string;
        repositoryName: string;
        repositoryUri: string;
        createdAt: string;
        imageTagMutability: string;
        imageScanningConfiguration: {
          scanOnPush: boolean;
        };
        encryptionConfiguration: {
          encryptionType: string;
        };
      }[];
    }
  }
}

const dockerDirectory = path.resolve(__dirname, "docker");

// For each folders in docker directory, get the tarball files
const dockerTarballs = globSync("**/*.tar", {
  cwd: dockerDirectory,
  absolute: true,
});

// Get the current sts caller-identity
const currentIdentity = JSON.parse(
  execSync("aws sts get-caller-identity --output json", { encoding: "utf8" })
) as AWS.STS.Identity;

const currentRegion =
  process.env["AWS_DEFAULT_REGION"] ?? execSync("aws configure get region --output text", { encoding: "utf8" });

console.info(`Using Identity: \n  ${util.format(currentIdentity)}`);
console.info(`Using Region: \n  ${currentRegion}`);

const ecrRepositories = (
  JSON.parse(execSync(`aws ecr describe-repositories --output json`, { encoding: "utf8" })) as AWS.ECR.Repository
).repositories;

const ecrTokenPassword = execSync(`aws ecr get-login-password`, { encoding: "utf8" });

dockerTarballs.forEach((tarballAsset) => {
  console.info(`Processing image: ${tarballAsset}`);
  const imageFilename = path.basename(tarballAsset);

  const imageName = path.basename(imageFilename, path.extname(imageFilename));
  const [containerName, containerTag] = imageName.split("__");

  // Use the container name to find the ECR repository
  const ecrRepository = ecrRepositories.find((repository) => repository.repositoryName === containerName);

  if (!ecrRepository) {
    console.error(`ECR repository not found for ${containerName}`);
    return;
  }
  const ecrRepositoryUri = ecrRepository.repositoryUri;
  const repositoryTarget = `${ecrRepositoryUri}:${containerTag}`;
  console.info(`Pushing to repository as: ${repositoryTarget}`);

  const command = `skopeo copy --dest-username AWS --dest-password '${ecrTokenPassword}' docker-archive:${tarballAsset} docker://${repositoryTarget}`;
  execSync(command, { stdio: "inherit" });
});
