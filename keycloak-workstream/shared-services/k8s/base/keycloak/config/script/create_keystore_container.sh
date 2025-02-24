#!/bin/bash
# © 2023 Amazon Web Services, Inc. or its affiliates. All Rights Reserved.

# This AWS Content is provided subject to the terms of the AWS Customer Agreement
# available at http://aws.amazon.com/agreement or other written agreement between
# Customer and either Amazon Web Services, Inc. or Amazon Web Services EMEA SARL or both.

# Only for RHEL (UBI9) images

microdnf install --assumeyes openssl wget unzip

echo "Downloading Certificates from DISA..."
# Location of bundle from DISA site
url='https://public.cyber.mil/pki-pke/pkipke-document-library/'
bundle=$(curl --silent $url | awk -F '"' 'tolower($2) ~ /dod.zip/ {print $2}')

mkdir -p tmp
pwd
ls -all

# Extract the bundle
echo "  Download file: $bundle"
wget --quiet --directory-prefix tmp $bundle
echo "  Unziping..."
unzip -qj tmp/${bundle##*/} -d tmp

# Convert the PKCS#7 bundle into individual PEM files
ls -all tmp
mkdir tmp/pems
ls -all tmp/pems

# Save certs to folder
echo "Exporting DERs..."
for file in tmp/*_der.p7b; do
  echo "Processing file: $file"
  openssl pkcs7 -print_certs -inform der -in "$file" |
    awk '
  BEGIN { FS="CN[[:space:]]?=[[:space:]]?" }
  /^subject=.*CN[[:space:]]?=[[:space:]]?/ { filename=$2 }
  /BEGIN CERTIFICATE/,/END CERTIFICATE/ { print $0 > "./tmp/pems/" filename ".crt" }
  '
done

ls -all tmp/pems

# Save to keystore
echo "Import PEMs to Keystore..."

cp tmp/pems/* /etc/pki/ca-trust/source/anchors/

echo "Cleaning Up...."
rm -fr tmp
echo "Done"
