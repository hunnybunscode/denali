import "source-map-support/register";
import "reflect-metadata";
import { Construct } from "constructs";
import * as blueprints from "@aws-quickstart/eks-blueprints";
import { readYamlDocument, loadYaml, dependable } from "@aws-quickstart/eks-blueprints/dist/utils";
import { aws_eks as eks, aws_kms as kms } from "aws-cdk-lib";

interface StorageClassManifest {
  kind: string;
  apiVersion: string;
  metadata: {
    name: string;
  };
  provisioner: string;
  parameters: {
    "csi.storage.k8s.io/fstype": string;
    type?: string;
    encrypted?: string;
    kmsKeyId?: string;
  } & { [key: string]: string };
  reclaimPolicy?: string;
  volumeBindingMode?: string;
  allowVolumeExpansion?: boolean;
}

export interface StorageClassDefaultAddonProps {
  storageClassPaths: string[];
  kmsKey?: kms.IKey;
}

const defaultProps = {
  storageClassPaths: [],
};

@Reflect.metadata("ordered", true)
export class StorageClassDefaultAddon implements blueprints.ClusterAddOn {
  readonly storageClassAddonProps: StorageClassDefaultAddonProps;

  constructor(props: StorageClassDefaultAddonProps) {
    this.storageClassAddonProps = { ...defaultProps, ...props };
  }

  @dependable(blueprints.addons.EbsCsiDriverAddOn.name)
  deploy(clusterInfo: blueprints.ClusterInfo): void | Promise<Construct> {
    const cluster = clusterInfo.cluster;

    const manifest: Record<string, any>[] = [];

    this.storageClassAddonProps.storageClassPaths.forEach(storageClassPath => {
      const storageClassManifest = loadYaml(readYamlDocument(storageClassPath)) as StorageClassManifest;

      if (this.storageClassAddonProps.kmsKey) {
        if (
          storageClassManifest.kind === "StorageClass" &&
          storageClassManifest.provisioner.includes("csi.aws.com") &&
          storageClassManifest?.parameters?.encrypted === "true"
        ) {
          storageClassManifest.parameters = {
            ...storageClassManifest.parameters,
            kmsKeyId: this.storageClassAddonProps.kmsKey.keyArn,
          };
        }
      }

      manifest.push(storageClassManifest);
    });

    return Promise.resolve(
      new eks.KubernetesManifest(
        clusterInfo.cluster.stack,
        `${clusterInfo.cluster.stack.node.id}-storage-class-default-addon`,
        {
          cluster,
          overwrite: true,
          manifest: manifest,
        }
      )
    );
  }
}
