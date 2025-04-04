#!bin/bash

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

echo "Convert existing java cacerts truststore to FIPS compliant ..."
echo "JAVA HOME: $JAVA_HOME"

curl --silent --output /opt/bc-fips.jar https://repo1.maven.org/maven2/org/bouncycastle/bc-fips/2.1.0/bc-fips-2.1.0.jar

mv $JAVA_HOME/lib/security/cacerts $JAVA_HOME/lib/security/cacerts.pkcs12

keytool -importkeystore \
  -srckeystore $JAVA_HOME/lib/security/cacerts.pkcs12 \
  -srcstoretype PKCS12 \
  -destkeystore $JAVA_HOME/lib/security/cacerts \
  -deststoretype BCFKS \
  -providername BCFIPS \
  -providerclass org.bouncycastle.jcajce.provider.BouncyCastleFipsProvider \
  -providerpath /opt/bc-fips.jar \
  -srcstorepass changeit \
  -deststorepass changeit

# Update java.security file for securerandom.strongAlgorithms with PKCS11:SunPKCS11-NSS-FIPS
echo "Updating java.security file ..."

sed -i 's/^securerandom\.strongAlgorithms=.*/securerandom.strongAlgorithms=PKCS11:SunPKCS11-NSS-FIPS/' $JAVA_HOME/conf/security/java.security
