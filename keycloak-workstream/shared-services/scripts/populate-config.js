#!/usr/bin/env node

const { EC2Client, DescribeVpcsCommand, DescribeSubnetsCommand } = require('@aws-sdk/client-ec2');
const { STSClient, GetCallerIdentityCommand } = require('@aws-sdk/client-sts');
const fs = require('fs');
const yaml = require('js-yaml');
const path = require('path');

async function populateConfig() {
  const env = process.env.ENVIRONMENT || 'dev-dynamic';
  const configPath = path.join(__dirname, '..', 'env', env, 'configuration.yaml');
  
  // Auto-detect AWS configuration
  const sts = new STSClient({});
  const ec2 = new EC2Client({});
  
  console.log('🔍 Auto-detecting AWS configuration...');
  
  // Get account and region
  const identity = await sts.send(new GetCallerIdentityCommand({}));
  const account = identity.Account;
  const region = process.env.AWS_DEFAULT_REGION || 'us-east-1';
  
  console.log(`✅ Detected AWS Account: ${account}`);
  console.log(`✅ Detected AWS Region: ${region}`);
  
  // Find VPC with both public and private subnets for EKS
  console.log('🔍 Finding VPC suitable for EKS...');
  let vpc;
  
  try {
    // Try default VPC first
    const defaultVpcs = await ec2.send(new DescribeVpcsCommand({
      Filters: [{ Name: 'is-default', Values: ['true'] }]
    }));
    
    if (defaultVpcs.Vpcs && defaultVpcs.Vpcs.length > 0) {
      vpc = defaultVpcs.Vpcs[0];
      console.log(`✅ Using default VPC: ${vpc.VpcId}`);
    } else {
      // Fallback to testing all VPCs
      const allVpcs = await ec2.send(new DescribeVpcsCommand({}));
      
      for (const testVpc of allVpcs.Vpcs || []) {
      console.log(`   Testing VPC ${testVpc.VpcId}...`);
      
      const vpcSubnets = await ec2.send(new DescribeSubnetsCommand({
        Filters: [{ Name: 'vpc-id', Values: [testVpc.VpcId] }]
      }));
      
      const publicSubnets = vpcSubnets.Subnets.filter(s => s.MapPublicIpOnLaunch);
      const privateSubnets = vpcSubnets.Subnets.filter(s => !s.MapPublicIpOnLaunch);
      
      // Check if we have subnets in at least 2 AZs
      const publicAZs = new Set(publicSubnets.map(s => s.AvailabilityZone));
      const privateAZs = new Set(privateSubnets.map(s => s.AvailabilityZone));
      
      console.log(`     Public subnets: ${publicSubnets.length} (AZs: ${publicAZs.size})`);
      console.log(`     Private subnets: ${privateSubnets.length} (AZs: ${privateAZs.size})`);
      
      // EKS can work with:
      // 1. Public subnets in 2+ AZs, OR
      // 2. Both public and private subnets, OR  
      // 3. Private subnets in 2+ AZs (for private clusters)
      if ((publicAZs.size >= 2) || (publicSubnets.length > 0 && privateSubnets.length > 0) || (privateAZs.size >= 2)) {
        vpc = testVpc;
        const clusterType = publicAZs.size >= 2 ? 'public' : privateAZs.size >= 2 ? 'private' : 'mixed';
        console.log(`✅ Selected VPC ${testVpc.VpcId} (${clusterType} EKS cluster)`);
        break;
      }
    }
    }
    
    if (!vpc) {
      console.error('❌ No VPC found with suitable subnet configuration for EKS');
      console.error('   EKS requires either:');
      console.error('   - Public subnets in 2+ availability zones, OR');
      console.error('   - Both public and private subnets, OR');
      console.error('   - Private subnets in 2+ availability zones');
      process.exit(1);
    }
  } catch (error) {
    console.error('❌ Error finding VPC:', error.message);
    process.exit(1);
  }
  
  // Get subnets
  console.log('🔍 Finding subnets...');
  const subnets = await ec2.send(new DescribeSubnetsCommand({
    Filters: [{ Name: 'vpc-id', Values: [vpc.VpcId] }]
  }));
  
  const publicSubnets = subnets.Subnets.filter(s => s.MapPublicIpOnLaunch);
  const isolatedSubnets = subnets.Subnets.filter(s => !s.MapPublicIpOnLaunch);
  
  // EKS needs at least 2 subnets in different AZs
  let selectedSubnets = [];
  
  // Function to select subnets from different AZs
  const selectSubnetsFromDifferentAZs = (subnetList) => {
    const subnetsByAZ = {};
    subnetList.forEach(subnet => {
      if (!subnetsByAZ[subnet.AvailabilityZone]) {
        subnetsByAZ[subnet.AvailabilityZone] = [];
      }
      subnetsByAZ[subnet.AvailabilityZone].push(subnet);
    });
    
    const result = [];
    Object.keys(subnetsByAZ).forEach(az => {
      if (result.length < 2) {
        result.push(subnetsByAZ[az][0]); // Take first subnet from each AZ
      }
    });
    return result;
  };
  
  if (publicSubnets.length >= 2) {
    selectedSubnets = selectSubnetsFromDifferentAZs(publicSubnets);
    console.log('✅ Using public subnets for EKS');
  } else if (isolatedSubnets.length >= 2) {
    selectedSubnets = selectSubnetsFromDifferentAZs(isolatedSubnets);
    console.log('✅ Using isolated subnets for EKS');
  } else {
    // Mix public and isolated if needed
    selectedSubnets = selectSubnetsFromDifferentAZs([...publicSubnets, ...isolatedSubnets]);
  }
  
  if (selectedSubnets.length < 2) {
    console.error('❌ EKS requires at least 2 subnets in different AZs');
    process.exit(1);
  }
  
  console.log(`✅ Found ${selectedSubnets.length} suitable subnets`);
  selectedSubnets.forEach(subnet => {
    console.log(`   - ${subnet.SubnetId} (${subnet.AvailabilityZone}) - Public: ${subnet.MapPublicIpOnLaunch}`);
  });
  
  // Ensure subnets are in different AZs
  const azs = new Set(selectedSubnets.map(s => s.AvailabilityZone));
  if (azs.size < 2) {
    console.error('❌ EKS requires subnets in at least 2 different availability zones');
    console.log('Available subnets:');
    subnets.Subnets.forEach(s => {
      console.log(`   - ${s.SubnetId} (${s.AvailabilityZone}) - Public: ${s.MapPublicIpOnLaunch}`);
    });
    process.exit(1);
  }
  
  // Get all subnets and identify public ones by name
  const allVpcSubnets = await ec2.send(new DescribeSubnetsCommand({
    Filters: [{ Name: 'vpc-id', Values: [vpc.VpcId] }]
  }));
  
  // Find private subnets with NAT gateway access (PRIVATE_WITH_EGRESS)
  const { DescribeRouteTablesCommand } = require('@aws-sdk/client-ec2');
  
  const routeTables = await ec2.send(new DescribeRouteTablesCommand({
    Filters: [{ Name: 'vpc-id', Values: [vpc.VpcId] }]
  }));
  
  const privateWithEgressSubnets = [];
  
  for (const subnet of allVpcSubnets.Subnets) {
    // Skip subnets that auto-assign public IPs (those are public subnets)
    if (subnet.MapPublicIpOnLaunch) continue;
    
    // Find route table for this subnet
    const routeTable = routeTables.RouteTables.find(rt => 
      rt.Associations?.some(assoc => assoc.SubnetId === subnet.SubnetId) ||
      (rt.Associations?.some(assoc => assoc.Main) && !routeTables.RouteTables.some(other => 
        other.Associations?.some(otherAssoc => otherAssoc.SubnetId === subnet.SubnetId)
      ))
    );
    
    // Check if route table has NAT gateway route (private with egress)
    const hasNATRoute = routeTable?.Routes?.some(route => 
      route.DestinationCidrBlock === '0.0.0.0/0' && route.NatGatewayId?.startsWith('nat-')
    );
    
    // Also check for internet gateway route (could be private subnet with IGW)
    const hasIGWRoute = routeTable?.Routes?.some(route => 
      route.DestinationCidrBlock === '0.0.0.0/0' && route.GatewayId?.startsWith('igw-')
    );
    
    if (hasNATRoute || hasIGWRoute) {
      privateWithEgressSubnets.push(subnet);
    }
  }
  
  // Take first 2 private subnets with egress from different AZs
  const subnetsToUse = privateWithEgressSubnets.slice(0, 2);
  
  console.log(`✅ Found ${privateWithEgressSubnets.length} private subnets with egress, using ${subnetsToUse.length}`);
  subnetsToUse.forEach(subnet => {
    const nameTag = subnet.Tags?.find(tag => tag.Key === 'Name');
    console.log(`   - ${subnet.SubnetId} (${subnet.AvailabilityZone}) - ${nameTag?.Value}`);
  });
  
  // Create configuration with truly public subnets in the format expected by EKSClustersConstruct
  const config = {
    environment: {
      name: env.replace('-dynamic', ''),
      region: region,
      account: account
    },
    hostedZones: [],
    clusters: [{
      name: 'SharedServices',
      version: '1.30',
      vpc: {
        id: vpc.VpcId,
        isolated: false, // Not isolated - using private with egress
        subnets: subnetsToUse.map(s => ({ id: s.SubnetId, cidr: s.CidrBlock }))
      },
      nodeGroups: [{
        name: 'compute-small',
        instanceType: 't3.medium',
        subnets: subnetsToUse.map(s => ({ id: s.SubnetId })),
        minSize: 1,
        desiredCapacity: 2,
        maxSize: 3
      }]
    }]
  };
  
  // Create directory if needed
  const configDir = path.dirname(configPath);
  if (!fs.existsSync(configDir)) {
    fs.mkdirSync(configDir, { recursive: true });
  }
  
  // Write configuration
  fs.writeFileSync(configPath, yaml.dump(config, { indent: 2 }));
  
  console.log('✅ Configuration generated successfully!');
  console.log(`📁 Config file: ${configPath}`);
  console.log(`🏠 Cluster type: Public (compatible with isolated subnets)`);
  console.log(`🚀 Ready to deploy: ENVIRONMENT=${env} cdk deploy --all`);
}

populateConfig().catch(console.error);