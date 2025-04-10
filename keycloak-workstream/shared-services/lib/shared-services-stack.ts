import {
  CfnOutput,
  Fn,
  Stack,
  StackProps,
  aws_route53 as route53,
  aws_certificatemanager as acm,
  aws_ec2 as ec2,
} from "aws-cdk-lib";
import { Construct } from "constructs";
import { EksBlueprint } from "@aws-quickstart/eks-blueprints";
import { EKSClustersConstruct } from "./EKSClustersConstruct";
import EKSUpdateNodeGroupVersion from "./EKSUpdateNodeGroupVersion";

export interface SharedServicesStackProps extends StackProps, ConfigurationDocument {}

export class SharedServicesStack extends Stack {
  constructor(scope: Construct, id: string, props: SharedServicesStackProps) {
    super(scope, id, props);

    const zones = this.createDomains(props);

    const clustersBuilderConstruct = new EKSClustersConstruct(this, "CreateEKSClusters", {
      ...props,
      ...{
        extended: {
          parentStack: this,
          hostedZones: zones,
        },
      },
    });

    // new EKSUpdateNodeGroupVersion(this, {
    //   stacks: Object.values(clustersBuilderConstruct.ClusterStacks) as EksBlueprint[],
    // });
  }

  private createCertificate(zone: { zoneName: string; zone: route53.IHostedZone; private: boolean }) {
    const { zoneName: domainName, zone: hostedZone } = zone;

    if (this.node.tryFindChild(`${domainName}-Certificate`) !== undefined) return;

    new acm.Certificate(this, `${domainName}-Certificate`, {
      domainName,
      validation: acm.CertificateValidation.fromDns(hostedZone),
      subjectAlternativeNames: [domainName, `*.${domainName}`],
      keyAlgorithm: acm.KeyAlgorithm.RSA_2048,
    });
  }

  private createDomains(props: SharedServicesStackProps): {
    zoneName: string;
    zone: route53.IHostedZone;
    private: boolean;
  }[] {
    const { hostedZones } = props;

    if (hostedZones == undefined) return [];

    const results = hostedZones.map(
      ({ zoneName: domainName, private: isPrivateHostedZone, vpc, createCertificate }) => {
        let hostedZone: route53.IHostedZone;

        if (isPrivateHostedZone) {
          if (vpc === undefined) return;

          hostedZone = new route53.PrivateHostedZone(this, `${this.node.id}-${domainName}-PrivateHostedZone`, {
            zoneName: domainName,
            vpc: ec2.Vpc.fromLookup(this, `${this.node.id}-${domainName}-vpc`, { vpcId: vpc.id }),
          });

          new CfnOutput(this, `${domainName}-Output-Private`, {
            value: domainName,
          });

          new CfnOutput(this, `${domainName}-Output-Private-hostedZoneId`, {
            value: hostedZone.hostedZoneId,
          });
        } else {
          hostedZone = new route53.PublicHostedZone(this, `${this.node.id}-${domainName}-PublicHostedZone`, {
            zoneName: domainName,
          });

          new CfnOutput(this, `${domainName}-Output-Public`, {
            value: domainName,
          });

          new CfnOutput(this, `${domainName}-Output-Public-hostedZoneId`, {
            value: hostedZone.hostedZoneId,
          });

          new CfnOutput(this, `${domainName}-Output-Public-HostedNameServers`, {
            value: Fn.join(",", hostedZone.hostedZoneNameServers ?? []),
          });
        }

        if (createCertificate)
          this.createCertificate({ zoneName: domainName, zone: hostedZone, private: isPrivateHostedZone });

        return {
          zoneName: domainName,
          zone: hostedZone,
          private: isPrivateHostedZone,
        };
      }
    );

    return results.filter(zone => zone !== undefined);
  }
}
