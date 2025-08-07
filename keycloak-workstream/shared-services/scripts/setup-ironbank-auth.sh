#!/bin/bash

# Script to set up Ironbank registry authentication
# Gets CLI credentials from user and logs into registry1.dso.mil

set -e

echo "=== Ironbank Registry Authentication Setup ==="
echo ""
echo "To authenticate with Ironbank registry, you need your CLI credentials:"
echo ""
echo "1. Open your browser and go to: https://registry1.dso.mil"
echo "2. Log in with your CAC card"
echo "3. Click on your profile/username in the top right"
echo "4. Look for 'CLI Secret' or similar credential section"
echo "5. Copy your username and CLI secret"
echo ""
echo "Enter your Ironbank credentials below:"
echo ""

# Get username
read -p "Ironbank Username: " IRONBANK_USERNAME

# Get CLI secret (hide input)
echo -n "CLI Secret: "
read -s IRONBANK_CLI_SECRET
echo ""

echo ""
echo "Attempting to log into Ironbank registry..."

# Attempt login using password-stdin for security
if echo "$IRONBANK_CLI_SECRET" | docker login registry1.dso.mil --username "$IRONBANK_USERNAME" --password-stdin; then
    echo ""
    echo "✅ SUCCESS! You are now authenticated with Ironbank registry."
    echo "✅ Your hardening scripts (ironbank-to-ecr.sh, operator-to-ecr.sh) will now work without prompting for credentials."
    echo ""
    echo "You can now run:"
    echo "  ./scripts/ironbank-to-ecr.sh"
    echo "  ./scripts/operator-to-ecr.sh"
else
    echo ""
    echo "❌ FAILED: Could not authenticate with Ironbank registry."
    echo "Please check your username and CLI secret and try again."
    exit 1
fi