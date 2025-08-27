import "source-map-support/register";
import "reflect-metadata";
import { Construct } from "constructs";
import * as blueprints from "@aws-quickstart/eks-blueprints";
import { dependable } from "@aws-quickstart/eks-blueprints/dist/utils";
import { aws_eks as eks } from "aws-cdk-lib";

interface ConfigMapManifest {
  kind: "ConfigMap";
  apiVersion: "v1";
  metadata: {
    name: string;
    namespace?: string;
  };
  data: {
    [key: string]: string;
  };
}

export interface VpcCniProxyPatchAddonProps {
  proxy?: {
    noProxy?: string[] | string;
    httpProxy?: string;
    httpsProxy?: string;
  };
}

const defaultProps = {};

@Reflect.metadata("ordered", true)
export class VpcCniProxyPatchAddon implements blueprints.ClusterAddOn {
  readonly vpcCniProxyPatchAddonProps: VpcCniProxyPatchAddonProps;

  constructor(props: VpcCniProxyPatchAddonProps) {
    this.vpcCniProxyPatchAddonProps = { ...defaultProps, ...props };
  }

  @dependable(blueprints.addons.VpcCniAddOn.name, blueprints.addons.KubeProxyAddOn.name)
  deploy(clusterInfo: blueprints.ClusterInfo): void | Promise<Construct> {
    const cluster = clusterInfo.cluster;

    const manifest: Record<string, any>[] = [];

    if (this.vpcCniProxyPatchAddonProps.proxy) {
      const configMapManifest: ConfigMapManifest = {
        kind: "ConfigMap",
        apiVersion: "v1",
        metadata: {
          name: "proxy-environment-variables",
          namespace: "kube-system",
        },
        data: {
          HTTP_PROXY: this.vpcCniProxyPatchAddonProps.proxy?.httpProxy ?? "",
          HTTPS_PROXY: this.vpcCniProxyPatchAddonProps.proxy?.httpsProxy ?? "",
          NO_PROXY: Array.isArray(this.vpcCniProxyPatchAddonProps.proxy?.noProxy)
            ? this.vpcCniProxyPatchAddonProps.proxy?.noProxy.join(",")
            : this.vpcCniProxyPatchAddonProps.proxy?.noProxy ?? "",
        },
      };

      manifest.push(configMapManifest);
    }

    const startManifest = new eks.KubernetesManifest(
      clusterInfo.cluster.stack,
      `${clusterInfo.cluster.stack.node.id}-vpc-cni-proxy-patch-addon`,
      {
        cluster,
        overwrite: true,
        manifest: manifest,
      }
    );

    const awsNodePatch = new eks.KubernetesPatch(cluster.stack, `${cluster.stack.stackName}-aws-node-patch`, {
      cluster,
      resourceName: "daemonset/aws-node",
      resourceNamespace: "kube-system",
      applyPatch: {
        spec: {
          template: {
            spec: {
              containers: [
                {
                  name: "aws-node",
                  envFrom: [
                    {
                      configMapRef: {
                        name: "proxy-environment-variables",
                      },
                    },
                  ],
                },
              ],
            },
          },
        },
      },
      restorePatch: {
        spec: {
          template: {
            spec: {
              containers: [
                {
                  name: "aws-node",
                  envFrom: [],
                },
              ],
            },
          },
        },
      },
      patchType: eks.PatchType.STRATEGIC,
    });

    const kubeProxyPatch = new eks.KubernetesPatch(cluster.stack, `${cluster.stack.stackName}-kube-proxy-patch`, {
      cluster,
      resourceName: "daemonset/kube-proxy",
      resourceNamespace: "kube-system",
      applyPatch: {
        spec: {
          template: {
            spec: {
              containers: [
                {
                  name: "kube-proxy",
                  envFrom: [
                    {
                      configMapRef: {
                        name: "proxy-environment-variables",
                      },
                    },
                  ],
                },
              ],
            },
          },
        },
      },
      restorePatch: {
        spec: {
          template: {
            spec: {
              containers: [
                {
                  name: "kube-proxy",
                  envFrom: [],
                },
              ],
            },
          },
        },
      },
      patchType: eks.PatchType.STRATEGIC,
    });

    awsNodePatch.node.addDependency(startManifest);
    kubeProxyPatch.node.addDependency(startManifest);

    return Promise.resolve(startManifest);
  }
}
