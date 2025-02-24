import "source-map-support/register";
import * as blueprints from "@aws-quickstart/eks-blueprints";
import * as eks from "aws-cdk-lib/aws-eks";
import { Construct } from "constructs";
import "reflect-metadata";

export interface NamespaceCreateAddonProps {
  namespaces: string[];
}

const defaultProps = {
  namespaces: [],
};

@Reflect.metadata("ordered", true)
export class NamespaceCreateAddon implements blueprints.ClusterAddOn {
  readonly namespaceCreateAddonProps: NamespaceCreateAddonProps;

  constructor(props: NamespaceCreateAddonProps) {
    this.namespaceCreateAddonProps = { ...defaultProps, ...props };
  }

  deploy(clusterInfo: blueprints.ClusterInfo): void | Promise<Construct> {
    const cluster = clusterInfo.cluster;

    const manifest: Record<string, any>[] = [];

    this.namespaceCreateAddonProps.namespaces.forEach(namespace => {
      manifest.push({
        apiVersion: "v1",
        kind: "Namespace",
        metadata: {
          name: namespace,
        },
      });
    });

    return Promise.resolve(
      new eks.KubernetesManifest(
        clusterInfo.cluster.stack,
        `${clusterInfo.cluster.stack.node.id}-namespace-create-addon`,
        {
          cluster,
          overwrite: true,
          manifest: manifest,
        }
      )
    );
  }
}
