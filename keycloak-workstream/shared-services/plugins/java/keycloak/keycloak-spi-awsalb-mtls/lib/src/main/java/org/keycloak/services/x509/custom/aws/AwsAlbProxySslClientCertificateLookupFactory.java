package org.keycloak.services.x509.custom.aws;

import org.jboss.logging.Logger;
import org.keycloak.Config;
import org.keycloak.models.KeycloakSession;
import org.keycloak.models.KeycloakSessionFactory;
import org.keycloak.services.x509.AbstractClientCertificateFromHttpHeadersLookupFactory;
import org.keycloak.services.x509.X509ClientCertificateLookup;
import org.keycloak.truststore.TruststoreProvider;
import org.keycloak.truststore.TruststoreProviderFactory;

import java.security.cert.X509Certificate;
import java.util.Set;
import java.util.concurrent.ConcurrentHashMap;

public class AwsAlbProxySslClientCertificateLookupFactory
        extends AbstractClientCertificateFromHttpHeadersLookupFactory {

    private static final Logger logger = Logger.getLogger(AwsAlbProxySslClientCertificateLookupFactory.class);

    private static final String PROVIDER = "awsalb";

    protected static final String TRUST_PROXY_VERIFICATION = "trust-proxy-verification";

    protected boolean trustProxyVerification;

    private volatile boolean isTruststoreLoaded;

    private Set<X509Certificate> trustedRootCerts;

    private Set<X509Certificate> intermediateCerts;

    @Override
    public void init(Config.Scope config) {
        super.init(config);
        this.trustProxyVerification = config.getBoolean(TRUST_PROXY_VERIFICATION, false);
        logger.tracev("{0}: ''{1}''", TRUST_PROXY_VERIFICATION, trustProxyVerification);
        this.isTruststoreLoaded = false;
        this.trustedRootCerts = ConcurrentHashMap.newKeySet();
        this.intermediateCerts = ConcurrentHashMap.newKeySet();
    }

    @Override
    public X509ClientCertificateLookup create(KeycloakSession session) {
        loadKeycloakTrustStore(session);
        if (trustProxyVerification) {
            logger.warn("Using trust proxy verification - Not Supported");
            return new AwsAlbProxyTrustedClientCertificateLookup(sslClientCertHttpHeader,
                    sslChainHttpHeaderPrefix, certificateChainLength);
        } else {
            logger.debug("Using non trust proxy verification");
            return new AwsAlbProxySslClientCertificateLookup(sslClientCertHttpHeader,
                    sslChainHttpHeaderPrefix, certificateChainLength, intermediateCerts, trustedRootCerts,
                    isTruststoreLoaded);
        }
    }

    @Override
    public String getId() {
        return PROVIDER;
    }

    /**
     * Loading truststore @ first login
     *
     * @param kcSession keycloak session
     */
    private void loadKeycloakTrustStore(KeycloakSession kcSession) {

        if (isTruststoreLoaded) {
            return;
        }

        synchronized (this) {
            if (isTruststoreLoaded) {
                return;
            }
            logger.debug(" Loading Keycloak truststore ...");
            KeycloakSessionFactory factory = kcSession.getKeycloakSessionFactory();

            TruststoreProviderFactory truststoreFactory = (TruststoreProviderFactory) factory
                    .getProviderFactory(TruststoreProvider.class, "file");
            TruststoreProvider provider = truststoreFactory.create(kcSession);

            if (provider != null && provider.getTruststore() != null) {
                trustedRootCerts.addAll(provider.getRootCertificates().values());
                intermediateCerts.addAll(provider.getIntermediateCertificates().values());
                logger.debug("Keycloak truststore loaded for AWS ALB x509cert-lookup provider.");

                isTruststoreLoaded = true;
            }
        }
    }
}
