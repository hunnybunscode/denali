import * as route53 from "aws-cdk-lib/aws-route53";
import { ResourceContext, ResourceProvider } from "@aws-quickstart/eks-blueprints/dist/spi";

export interface LookupHostedZoneProviderOptions {
  /**
   * The zone domain e.g. example.com
   */
  readonly domainName: string;
  /**
   * Whether the zone that is being looked up is a private hosted zone
   *
   * @default false
   */
  readonly privateZone?: boolean;
  /**
   * Specifies the ID of the VPC associated with a private hosted zone.
   *
   * If a VPC ID is provided and privateZone is false, no results will be returned
   * and an error will be raised
   *
   * @default - No VPC ID
   */
  readonly vpcId?: string;

  /**
   * Optional id for the structure (for tracking). set to host zone name by default
   */
  id?: string;
}

/**
 * Simple lookup host zone provider
 */
export class LookupHostedZoneProvider implements ResourceProvider<route53.IHostedZone> {
  /**
   * @param option Option to configure for lookup for a hosted zone
   */
  constructor(private option: LookupHostedZoneProviderOptions) {}

  provide(context: ResourceContext): route53.IHostedZone {
    const { domainName, id, privateZone, vpcId } = this.option;

    return route53.HostedZone.fromLookup(context.scope, id ?? `${domainName}-Lookup`, {
      domainName,
      privateZone,
      vpcId,
    });
  }
}
