package daffodil.precompile;

import java.io.File;
import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;
import java.net.URI;
import java.net.URISyntaxException;
import java.nio.channels.Channels;
import java.nio.file.Files;
import java.nio.file.StandardCopyOption;
import java.util.List;

import org.apache.daffodil.japi.Daffodil;
import org.apache.daffodil.japi.DataProcessor;
import org.apache.daffodil.japi.Diagnostic;
import org.apache.daffodil.japi.ProcessorFactory;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import com.amazonaws.services.lambda.runtime.Context;
import com.amazonaws.services.lambda.runtime.RequestHandler;
import com.amazonaws.services.lambda.runtime.events.S3Event;
import com.amazonaws.services.lambda.runtime.events.models.s3.S3EventNotification.S3EventNotificationRecord;

import software.amazon.awssdk.services.s3.S3Client;
import software.amazon.awssdk.services.s3.model.GetObjectRequest;

public class App implements RequestHandler<S3Event, Void> {
    private static final Logger logger = LoggerFactory.getLogger(App.class);
    private final S3Client s3Client;
    private final org.apache.daffodil.japi.Compiler c;

    public App() throws IOException {
        s3Client = S3Client.create();
        c = Daffodil.compiler();
    }

    @Override
    public Void handleRequest(S3Event event, Context context) {
        for(S3EventNotificationRecord record : event.getRecords()) {
            String s3Key = record.getS3().getObject().getKey();
            if(!s3Key.toLowerCase().endsWith(".dfdl.xsd")) {
                continue;
            }

            try {
                File schemaFile = File.createTempFile(s3Key+"-", null);
                schemaFile.deleteOnExit();

                String s3Bucket = record.getS3().getBucket().getName();
                logger.info("found id: " + s3Bucket+" "+s3Key);

                InputStream in = s3Client.getObject(GetObjectRequest.builder().bucket(s3Bucket).key(s3Key).build());
                Files.copy(in, schemaFile.toPath(), StandardCopyOption.REPLACE_EXISTING);

                DataProcessor dp = getDataProcessor(schemaFile.toURI());

                try(OutputStream out = new S3OutputStream(s3Client, s3Bucket, s3Key+".dp")) {
                    dp.save(Channels.newChannel(out));
                }
            } catch(IOException | URISyntaxException e) {
                logger.error("Error transforming file " + s3Key, e);
            }
        }
        return null;
    }

    private DataProcessor getDataProcessor(URI schemaFileURL) throws IOException, URISyntaxException {
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