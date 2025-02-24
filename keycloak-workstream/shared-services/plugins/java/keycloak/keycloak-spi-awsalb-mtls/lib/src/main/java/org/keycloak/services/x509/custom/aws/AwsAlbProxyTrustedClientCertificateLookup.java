package org.keycloak.services.x509.custom.aws;

import org.jboss.logging.Logger;
import org.keycloak.http.HttpRequest;
import org.keycloak.services.x509.AbstractClientCertificateFromHttpHeadersLookup;
import org.keycloak.common.util.PemException;
import org.keycloak.common.util.PemUtils;

import java.io.UnsupportedEncodingException;
import java.security.GeneralSecurityException;
import java.security.cert.X509Certificate;
import java.text.MessageFormat;

public class AwsAlbProxyTrustedClientCertificateLookup extends AbstractClientCertificateFromHttpHeadersLookup {

    private static final Logger log = Logger.getLogger(AwsAlbProxyTrustedClientCertificateLookup.class);

    public AwsAlbProxyTrustedClientCertificateLookup(String sslCientCertHttpHeader,
            String sslCertChainHttpHeaderPrefix,
            int certificateChainLength) {
        super(sslCientCertHttpHeader, sslCertChainHttpHeaderPrefix, certificateChainLength);
    }

    static String getHeaderValue(HttpRequest httpRequest, String headerName) {
        var value = httpRequest.getHttpHeaders().getRequestHeaders().getFirst(headerName);
        log.warn(MessageFormat.format("Pattern Header - {0}", value));
        return value;
    }

    @Override
    protected X509Certificate getCertificateFromHttpHeader(HttpRequest request, String httpHeader)
            throws GeneralSecurityException {

        log.warn(MessageFormat.format("Header - {0}", httpHeader));
        X509Certificate certificate = super.getCertificateFromHttpHeader(request, httpHeader);
        if (certificate == null) {
            return null;
        }

        log.warn(("Got Certificate - "));
        String validCertificateResult = getHeaderValue(request, "X-Amzn-Mtls-Clientcert");
        if ("SUCCESS".equals(validCertificateResult)) {
            return certificate;
        } else {
            log.warn(MessageFormat.format("AWS ALB could not verify the certificate: {0}: {1}", httpHeader, validCertificateResult));
            return null;
        }
    }

    @Override
    protected X509Certificate decodeCertificateFromPem(String pem) throws PemException {

        if (pem == null) {
            log.warn("End user TLS Certificate is NULL! ");
            return null;
        }

        log.debug(MessageFormat.format("Pre-decode - \n{0}", pem));
        try {
            // Replace literal + with url encoded version
            // pem = pem.replaceAll("\\+", "%2b");

            pem = java.net.URLDecoder.decode(pem, "UTF-8");
        } catch (UnsupportedEncodingException e) {
            log.error("Cannot URL decode the end user TLS Certificate : " + pem, e);
        }

        log.debug(MessageFormat.format("Formatting to PEMUTIL - \n{0}", pem));

        pem = removeBeginEnd(pem);

        // Additional formatting
        pem = pem.replaceAll("\\s", "+");
        // pem = pem.replaceAll("\\+CERTIFICATE", " CERTIFICATE");
        // pem = pem.replaceAll("\\s", " CERTIFICATE");

        log.debug(MessageFormat.format("Prior to PEMUTIL - \n{0}", pem));

        return PemUtils.decodeCertificate(pem);
    }

    /**
     * Removing PEM Headers and end of lines
     *
     * @param pem
     * @return
     */
    private static String removeBeginEnd(String pem) {
        pem = pem.replace(PemUtils.BEGIN_CERT, "");
        pem = pem.replace(PemUtils.END_CERT, "");
        pem = pem.replace("\r\n", "");
        pem = pem.replace("\n", "");
        return pem.trim();
    }

}
