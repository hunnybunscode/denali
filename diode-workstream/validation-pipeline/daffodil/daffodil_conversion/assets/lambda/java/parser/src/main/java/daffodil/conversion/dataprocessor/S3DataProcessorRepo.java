package daffodil.conversion.dataprocessor;

import java.io.File;
import java.io.IOException;
import java.io.InputStream;
import java.net.URI;
import java.nio.channels.Channels;
import java.util.List;
import java.util.concurrent.CompletableFuture;

import org.apache.daffodil.japi.Daffodil;
import org.apache.daffodil.japi.DataProcessor;
import org.apache.daffodil.japi.Diagnostic;
import org.apache.daffodil.japi.InvalidParserException;
import org.apache.daffodil.japi.ProcessorFactory;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import daffodil.conversion.contenttype.ContentTypeSchemaMap;
import software.amazon.awssdk.core.async.AsyncResponseTransformer;
import software.amazon.awssdk.services.s3.S3AsyncClient;

/**
 * DataProcessorRepo that is implemented with an s3 bucket as the schema/DataProcessor repository.
 * This will attempt to retrieve the DataProcessor from the s3 bucket (mapped from the content-
 * type schema map). If there is not DataProcessor for the given content-type, it will then attempt
 * to download and compile the schema localally (this is undesired since it is expensive).
 */
public class S3DataProcessorRepo implements DataProcessorRepo {
    private static final Logger logger = LoggerFactory.getLogger(CachedDataProcessorRepo.class);

    private final org.apache.daffodil.japi.Compiler c = Daffodil.compiler();

    private final S3AsyncClient s3Client;
    private final ContentTypeSchemaMap contentTypeSchemaMap;

    public S3DataProcessorRepo(S3AsyncClient s3Client, ContentTypeSchemaMap contentTypeSchemaMap) {
        this.s3Client = s3Client;
        this.contentTypeSchemaMap = contentTypeSchemaMap;
    }

    @Override
    public CompletableFuture<DataProcessor> get(String contentType) {
        final String schemaBucketName = System.getenv("SCHEMA_BUCKET");
        String schemaFile = contentTypeSchemaMap.get(contentType);
        if(schemaFile == null) {
            throw new RuntimeException("No schema file found for content-type " + contentType);
        }

        return s3Client.getObject(req -> req.bucket(schemaBucketName).key(schemaFile+".dp"),
            AsyncResponseTransformer.toBlockingInputStream())
        .thenApply(bis -> {
            try(InputStream in = bis) {
                return c.reload(Channels.newChannel(in));
            } catch (InvalidParserException | IOException e) {
                throw new RuntimeException(e);
            }
        }).exceptionally(e -> {
            logger.warn(String.format(
                "Couldn't get precompiled schema %s.dp, will attempt to compile schema",
                schemaFile
            ));
            try {
                File tmp = File.createTempFile(schemaFile, null);
                tmp.deleteOnExit();

                return s3Client.getObject(req -> req.bucket(schemaBucketName).key(schemaFile), tmp.toPath())
                .thenApply(r -> {
                    try {
                        return getDataProcessor(tmp.toURI());
                    } catch (IOException e1) {
                        throw new RuntimeException(e1);
                    }
                }).join();
            } catch(IOException e1) {
                throw new RuntimeException(e1);
            }
        });

    }

    /**
     * Compiles schema file from uri (most likely a temp file location). This is only done when
     * we don't have a DataProcessor already precompiled in the s3 schema bucket.
     *
     * @param schemaFileURL
     * @return
     * @throws IOException
     */
    private DataProcessor getDataProcessor(URI schemaFileURL) throws IOException {
        logger.info("compiling source");
        ProcessorFactory pf = c.compileSource(schemaFileURL);
        logger.info("compiled error: " + pf.isError());
        if (pf.isError()) {
            // didn't compile schema. Must be diagnostic of some sort.
            List<Diagnostic> diags = pf.getDiagnostics();
            for (Diagnostic d : diags) {
                logger.error(d.getSomeMessage());
            }
            return null;
        }
        logger.info("gettind data processor");
        DataProcessor dp = pf.onPath("/");
        logger.info("data processor error: " + dp.isError());
        if (dp.isError()) {
            // didn't compile schema. Must be diagnostic of some sort.
            List<Diagnostic> diags = dp.getDiagnostics();
            for (Diagnostic d : diags) {
                logger.error(d.getSomeMessage());
            }
            return null;
        }
        return dp;
    }
}
