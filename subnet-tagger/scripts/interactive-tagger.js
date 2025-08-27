#!/usr/bin/env node

const { EC2Client, DescribeVpcsCommand, DescribeSubnetsCommand, DescribeRouteTablesCommand, CreateTagsCommand } = require('@aws-sdk/client-ec2');
const readline = require('readline');
const fs = require('fs');

const rl = readline.createInterface({
  input: process.stdin,
  output: process.stdout
});

function question(prompt) {
  return new Promise((resolve) => {
    rl.question(prompt, resolve);
  });
}

async function main() {
  // Auto-detect region from AWS configuration
  const ec2 = new EC2Client({});
  
  console.log('🏷️  Subnet Tagger - CDK + Kubernetes ALB Controller Tags\n');
  
  try {
    // Get all VPCs
    console.log('Discovering VPCs...');
    const vpcsResponse = await ec2.send(new DescribeVpcsCommand({}));
    const vpcs = vpcsResponse.Vpcs || [];
    
    if (vpcs.length === 0) {
      console.log('❌ No VPCs found in this region');
      rl.close();
      return;
    }
    
    console.log(`\nFound ${vpcs.length} VPCs:\n`);
    
    // Show VPC options
    vpcs.forEach((vpc, index) => {
      const name = vpc.Tags?.find(tag => tag.Key === 'Name')?.Value || 'Unnamed';
      console.log(`${index + 1}. ${vpc.VpcId} - ${name} (${vpc.CidrBlock})`);
    });
    
    console.log(`${vpcs.length + 1}. Tag ALL VPCs\n`);
    
    // Get user choice
    const choice = await question('Select option (number): ');
    const choiceNum = parseInt(choice);
    
    if (choiceNum === vpcs.length + 1) {
      // Tag all VPCs
      console.log('\n🚀 Tagging subnets in ALL VPCs...\n');
      for (const vpc of vpcs) {
        await tagVpcSubnets(vpc, ec2);
      }
      console.log('\n✅ All VPCs processed!');
      await generateInventoryReadme(vpcs, ec2);
    } else if (choiceNum >= 1 && choiceNum <= vpcs.length) {
      // Tag specific VPC(s)
      let continueTagging = true;
      const processedVpcs = new Set();
      
      while (continueTagging) {
        const selectedVpc = vpcs[choiceNum - 1];
        
        if (!processedVpcs.has(selectedVpc.VpcId)) {
          console.log(`\n🚀 Tagging subnets in VPC ${selectedVpc.VpcId}...\n`);
          await tagVpcSubnets(selectedVpc, ec2);
          processedVpcs.add(selectedVpc.VpcId);
          console.log(`\n✅ VPC ${selectedVpc.VpcId} processed!`);
        } else {
          console.log(`\n⚠️  VPC ${selectedVpc.VpcId} already processed!`);
        }
        
        // Ask if user wants to tag another VPC
        const continueChoice = await question('\nWould you like to tag another VPC? (y/n): ');
        
        if (continueChoice.toLowerCase() === 'y' || continueChoice.toLowerCase() === 'yes') {
          // Show remaining VPCs
          console.log('\nRemaining VPCs:\n');
          vpcs.forEach((vpc, index) => {
            if (!processedVpcs.has(vpc.VpcId)) {
              const name = vpc.Tags?.find(tag => tag.Key === 'Name')?.Value || 'Unnamed';
              console.log(`${index + 1}. ${vpc.VpcId} - ${name} (${vpc.CidrBlock})`);
            }
          });
          
          const nextChoice = await question('\nSelect VPC number: ');
          const nextChoiceNum = parseInt(nextChoice);
          
          if (nextChoiceNum >= 1 && nextChoiceNum <= vpcs.length) {
            const nextVpc = vpcs[nextChoiceNum - 1];
            if (!processedVpcs.has(nextVpc.VpcId)) {
              console.log(`\n🚀 Tagging subnets in VPC ${nextVpc.VpcId}...\n`);
              await tagVpcSubnets(nextVpc, ec2);
              processedVpcs.add(nextVpc.VpcId);
              console.log(`\n✅ VPC ${nextVpc.VpcId} processed!`);
            } else {
              console.log(`\n⚠️  VPC ${nextVpc.VpcId} already processed!`);
            }
          } else {
            console.log('❌ Invalid selection');
          }
        } else {
          continueTagging = false;
          await generateInventoryReadme(vpcs, ec2);
        }
      }
    } else {
      console.log('❌ Invalid selection');
    }
    
  } catch (error) {
    console.error('❌ Error:', error.message);
  } finally {
    rl.close();
  }
}

async function tagVpcSubnets(vpc, ec2) {
  // Get subnets for this VPC
  const subnetsResponse = await ec2.send(new DescribeSubnetsCommand({
    Filters: [{ Name: 'vpc-id', Values: [vpc.VpcId] }]
  }));
  
  // Get route tables for this VPC
  const routeTablesResponse = await ec2.send(new DescribeRouteTablesCommand({
    Filters: [{ Name: 'vpc-id', Values: [vpc.VpcId] }]
  }));
  
  const subnets = subnetsResponse.Subnets || [];
  const routeTables = routeTablesResponse.RouteTables || [];
  
  console.log(`  Found ${subnets.length} subnets in VPC ${vpc.VpcId}`);
  
  for (const subnet of subnets) {
    let tags = [];
    let subnetType = '';
    
    if (subnet.MapPublicIpOnLaunch) {
      // Public subnet
      subnetType = 'Public';
      tags = [
        { Key: 'aws-cdk:subnet-type', Value: 'Public' },
        { Key: 'kubernetes.io/role/elb', Value: '1' }
      ];
    } else {
      // Check if isolated
      const isIsolated = checkIfIsolated(subnet.SubnetId, routeTables);
      
      if (isIsolated) {
        // Isolated subnet
        subnetType = 'Isolated';
        tags = [
          { Key: 'aws-cdk:subnet-type', Value: 'Isolated' },
          { Key: 'kubernetes.io/role/internal-elb', Value: '1' },
          { Key: 'kubernetes.io/role/cni', Value: '1' }
        ];
      } else {
        // Private subnet
        subnetType = 'Private';
        tags = [
          { Key: 'aws-cdk:subnet-type', Value: 'Private' },
          { Key: 'kubernetes.io/role/internal-elb', Value: '1' },
          { Key: 'kubernetes.io/role/cni', Value: '1' }
        ];
      }
    }
    
    // Apply tags
    await ec2.send(new CreateTagsCommand({
      Resources: [subnet.SubnetId],
      Tags: tags
    }));
    
    console.log(`    ✅ Tagged ${subnet.SubnetId} as ${subnetType}`);
  }
}

function checkIfIsolated(subnetId, routeTables) {
  const routeTable = routeTables.find(rt => 
    rt.Associations?.some(assoc => assoc.SubnetId === subnetId)
  );
  
  if (!routeTable) return true;
  
  const hasInternetRoute = routeTable.Routes?.some(route => 
    route.GatewayId?.startsWith('igw-') || route.NatGatewayId
  );
  
  return !hasInternetRoute;
}

async function generateInventoryReadme(vpcs, ec2) {
  console.log('\n📄 Generating VPC inventory...');
  
  let readme = `# AWS VPC & Subnet Inventory\n\n`;
  readme += `*Last updated: ${new Date().toISOString()}*\n\n`;
  readme += `## Summary\n\n`;
  readme += `- **Total VPCs:** ${vpcs.length}\n`;
  
  let totalSubnets = 0;
  for (const vpc of vpcs) {
    const subnetsResponse = await ec2.send(new DescribeSubnetsCommand({
      Filters: [{ Name: 'vpc-id', Values: [vpc.VpcId] }]
    }));
    totalSubnets += (subnetsResponse.Subnets || []).length;
  }
  
  readme += `- **Total Subnets:** ${totalSubnets}\n\n`;
  readme += `---\n\n`;
  
  for (const vpc of vpcs) {
    const name = vpc.Tags?.find(tag => tag.Key === 'Name')?.Value || 'Unnamed';
    readme += `## 🌐 ${vpc.VpcId} - ${name}\n\n`;
    readme += `**CIDR:** ${vpc.CidrBlock}  \n`;
    readme += `**State:** ${vpc.State}\n\n`;
    
    const subnetsResponse = await ec2.send(new DescribeSubnetsCommand({
      Filters: [{ Name: 'vpc-id', Values: [vpc.VpcId] }]
    }));
    
    const subnets = subnetsResponse.Subnets || [];
    
    if (subnets.length === 0) {
      readme += `*No subnets found*\n\n`;
      continue;
    }
    
    readme += `### Subnets (${subnets.length} total)\n\n`;
    readme += `| Subnet ID | Name | Type | AZ | CIDR | K8s Tags |\n`;
    readme += `|-----------|------|------|----|----- |----------|\n`;
    
    for (const subnet of subnets) {
      const subnetName = subnet.Tags?.find(tag => tag.Key === 'Name')?.Value || 'Unnamed';
      const subnetType = subnet.Tags?.find(tag => tag.Key === 'aws-cdk:subnet-type')?.Value || '❓ Unknown';
      const k8sTags = subnet.Tags?.filter(tag => tag.Key.startsWith('kubernetes.io')).map(t => `\`${t.Key}\``).join(', ') || 'None';
      
      const typeIcon = subnetType === 'Public' ? '🌍' : subnetType === 'Private' ? '🔒' : subnetType === 'Isolated' ? '🚫' : '❓';
      
      readme += `| ${subnet.SubnetId} | ${subnetName} | ${typeIcon} ${subnetType} | ${subnet.AvailabilityZone} | ${subnet.CidrBlock} | ${k8sTags} |\n`;
    }
    readme += `\n`;
  }
  
  readme += `---\n\n`;
  readme += `## Tag Legend\n\n`;
  readme += `### CDK Tags\n`;
  readme += `- \`aws-cdk:subnet-type\`: Public/Private/Isolated\n\n`;
  readme += `### Kubernetes ALB Controller Tags\n`;
  readme += `- \`kubernetes.io/role/elb\`: Public subnets for internet-facing load balancers\n`;
  readme += `- \`kubernetes.io/role/internal-elb\`: Private/Isolated subnets for internal load balancers\n`;
  readme += `- \`kubernetes.io/role/cni\`: Subnets available for Kubernetes CNI\n`;
  
  fs.writeFileSync('VPC-INVENTORY.md', readme);
  console.log('✅ Generated VPC-INVENTORY.md');
}

main();