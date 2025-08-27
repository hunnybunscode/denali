#!/usr/bin/env ts-node
import type { ConfigurationDocument, Image } from "../lib/interface.types.ts";

import * as path from "path";
import * as fs from "fs";
import * as yaml from "js-yaml";
import { execSync } from "child_process";

const DISABLE_SCHEMA_VALIDATION = true;

function fetchContainerImage(image: Image, dockerDirectory: string) {
  const { repository, tag } = image;
  console.info(`Fetching image from repository: ${repository}`);
  console.info(`Tag: ${tag}`);

  const dockerDestinationFile = path.join(dockerDirectory, `${path.basename(repository)}__${tag}.tar`);
  const command = `skopeo copy --remove-signatures --override-os linux --override-arch amd64 docker://${repository}:${tag} docker-archive:${dockerDestinationFile}`;

  try {
    if (fs.existsSync(dockerDestinationFile)) fs.unlinkSync(dockerDestinationFile);

    execSync(command);
  } catch (e) {
    console.error(e);
    console.error(`Command: \n${command}`);
    console.warn("Docker Dependency Fetch Failed");
  }
}

console.info("Fetching Container Dependencies");

const { env } = process;

let doc: ConfigurationDocument;

try {
  const environmentName = env.ENVIRONMENT ?? "dev";
  console.info(`Loading environment variables for environment: ${environmentName}`);
  doc = yaml.load(
    fs.readFileSync(path.join(__dirname, `../env/${environmentName}/configuration.yaml`), "utf8")
  ) as ConfigurationDocument;
} catch (e) {
  console.error(e);
  throw e;
}

console.info("Environment variables loaded successfully");

const externalDirectory = __dirname;

// Handle Helm
if (doc.helm) {
  console.info("Fetching Helm Dependencies");
  const { helm } = doc;
  const { charts } = helm;

  const helmDirectory = path.join(externalDirectory, "helm");

  if (!fs.existsSync(helmDirectory)) {
    fs.mkdirSync(helmDirectory);
  }

  for (const { chartName, images, repositoryUrl, version } of charts) {
    console.info(`Fetching chart from repository: ${repositoryUrl}`);

    // Add repo
    {
      const command = `helm repo add ${chartName} ${repositoryUrl}`;

      try {
        execSync(command);
      } catch (e) {
        console.error(e);
        console.error(`Command: \n${command}`);
      }
    }

    // Pull the repo
    {
      const destinationDirectory = path.join(helmDirectory, chartName);

      const command = `helm pull ${chartName}/${chartName} --version ${version} --destination ${destinationDirectory}`;

      if (!fs.existsSync(destinationDirectory)) fs.mkdirSync(destinationDirectory, { recursive: true });

      try {
        execSync(command);
      } catch (e) {
        console.error(e);
        console.error(`Command: \n${command}`);
      }

      const tarballFilePath = path.join(destinationDirectory, `${chartName}-${version}.tgz`);
      const tempFileDirPath = path.join(destinationDirectory, `${chartName}-${version}`);
      const excludeFile = "values.schema.json";

      const listContentCommand = `tar -tf "${tarballFilePath}" | grep ${excludeFile}`;
      let listContent = "";

      try {
        listContent = execSync(listContentCommand, { encoding: "utf8" });
      } catch (e) {
        //Ignore
      }

      if (DISABLE_SCHEMA_VALIDATION && listContent.includes(excludeFile)) {
        console.warn(`Cleaning up Chart: ${chartName}-${version}`);
        if (!fs.existsSync(tempFileDirPath)) fs.mkdirSync(tempFileDirPath);

        const archiveCommand = `tar -xzf ${tarballFilePath} -C "${tempFileDirPath}" --exclude "${excludeFile}" && helm package "${path.join(
          tempFileDirPath,
          chartName
        )}" --destination "${destinationDirectory}"`;

        try {
          execSync(archiveCommand);
        } catch (e) {
          console.error(e);
          console.error(`Command: \n${archiveCommand}`);
        }

        // Clean up
        fs.rmSync(tempFileDirPath, { recursive: true, force: true });
      }
    }

    // Download the container images related to chart
    {
      const dockerDirectory = path.join(externalDirectory, "docker");

      if (!fs.existsSync(dockerDirectory)) {
        fs.mkdirSync(dockerDirectory);
      }

      for (const image of images) {
        fetchContainerImage(image, dockerDirectory);
      }
    }
  }

  console.info("Helm Dependencies - Completed");
}

// Handle Docker
if (doc.docker) {
  console.info("Fetching Docker Dependencies");
  const { docker } = doc;
  const { images } = docker;

  const dockerDirectory = path.join(externalDirectory, "docker");

  if (!fs.existsSync(dockerDirectory)) {
    fs.mkdirSync(dockerDirectory);
  }

  for (const image of images) {
    fetchContainerImage(image, dockerDirectory);
  }

  console.info("Docker Dependencies - Completed");
}
