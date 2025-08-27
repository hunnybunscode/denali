#!/usr/bin/env ts-node

import * as path from "path";
import { globSync } from "glob";
import { execSync } from "child_process";

const helmDirectory = path.resolve(__dirname, "helm");

// For each folders in helm directory, extract the tarball files
const helmChartTarballs = globSync("**/*/*.tgz", {
  cwd: helmDirectory,
  absolute: true,
});

helmChartTarballs.forEach(tarballAsset => {
  console.info(`Extracting ${tarballAsset}`);
  const chartFolder = path.dirname(tarballAsset);

  const extractCommand = `tar -xzf ${tarballAsset} -C ${chartFolder}`;
  console.info("  " + extractCommand);
  execSync(extractCommand, { stdio: "inherit" });
});
