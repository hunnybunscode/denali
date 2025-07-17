# Pre-Requisites

1. VPN Client Software
   1. AWS provided client: https://docs.aws.amazon.com/vpn/latest/clientvpn-user/connect-aws-client-vpn-connect.html or
   2. OpenVPN client: https://docs.aws.amazon.com/vpn/latest/clientvpn-user/connect.html

# Deployment Instructions

1. Create a private CA (refer to the CloudFormation parameters for descriptions)
2. With the root key and root cert, create a stack with the CloudFormation template. Leave Server Certificate ARN parameter blank for now.
3. Once the stack gets created successfully, look in the Outputs section and run the commands in HowToCreateServerKeyAndCert key in CloudShell (or another Linux machine with your credentials).
4. Get the CertificateArn value.
5. Update the stack with the value in Server Certificate ARN parameter.
6. Once the stack gets updated successfully, look in the Outputs section and run the commands in HowToCreateClientKeyAndCert key in CloudShell (or another Linux machine with your credentials).
7. Download and send to your user the resultant configuration file from CloudShell (or copy the contents to a local file). Ensure you delete the file in CloudShell (or the machine you ran the commands on), as it contains the private key.

# User

1. Connect to VPN using a VPN Client Software with the configuration file: https://aws.amazon.com/vpn/client-vpn-download/
2. Connect to NiFi instances using their IP addresses
