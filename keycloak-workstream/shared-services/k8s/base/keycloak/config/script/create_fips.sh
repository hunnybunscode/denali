#!bin/bash

### Reference from https://www.keycloak.org/server/fips#_bouncycastle_fips_bits

if [ -f /proc/sys/crypto/fips_enabled ]; then
  fips_status=$(cat /proc/sys/crypto/fips_enabled)
  if [ "$fips_status" -eq 1 ]; then
    echo "FIPS mode is enabled."
  else
    echo "FIPS mode is disabled."
    echo "Exiting"
    exit 0
  fi
else
  echo "FIPS mode is not supported on this system."
  exit 0
fi

echo "Downloading FIPS plugins - BouncyCastle library ..."
echo "Current working directory: $(pwd)"

# Download All jars from BouncyCastle library to current working directory

curl --silent --output bc-fips.jar https://repo1.maven.org/maven2/org/bouncycastle/bc-fips/2.1.0/bc-fips-2.1.0.jar
curl --silent --output bctls-fips.jar https://repo1.maven.org/maven2/org/bouncycastle/bctls-fips/2.1.20/bctls-fips-2.1.20.jar
curl --silent --output bcpkix-fips.jar https://repo1.maven.org/maven2/org/bouncycastle/bcpkix-fips/2.1.9/bcpkix-fips-2.1.9.jar
curl --silent --output bcutil-fips.jar https://repo1.maven.org/maven2/org/bouncycastle/bcutil-fips/2.1.4/bcutil-fips-2.1.4.jar

ls -all
