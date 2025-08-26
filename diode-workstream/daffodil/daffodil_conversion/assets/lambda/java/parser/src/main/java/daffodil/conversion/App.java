package daffodil.conversion;

import java.io.OutputStream;
import java.io.UnsupportedEncodingException;
import java.net.URLDecoder;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.Base64;
import java.util.Date;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.Optional;
import java.util.Base64.Decoder;
import java.util.Base64.Encoder;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.CompletionException;
import java.util.function.Consumer;
import java.util.regex.Pattern;
import java.util.stream.Collectors;
import java.util.stream.Stream;

import org.apache.daffodil.japi.DataProcessor;
import org.apache.daffodil.japi.Diagnostic;
import org.apache.daffodil.japi.ParseResult;
import org.apache.daffodil.japi.UnparseResult;
import org.apache.daffodil.japi.infoset.XMLTextInfosetInputter;
import org.apache.daffodil.japi.infoset.XMLTextInfosetOutputter;
import org.apache.daffodil.japi.io.InputSourceDataInputStream;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import com.amazonaws.services.lambda.runtime.Context;
import com.amazonaws.services.lambda.runtime.RequestHandler;
import com.amazonaws.services.lambda.runtime.events.S3Event;
import com.amazonaws.services.lambda.runtime.events.models.s3.S3EventNotification.S3EventNotificationRecord;

import daffodil.conversion.contenttype.CachedContentTypeSchemaMap;
import daffodil.conversion.contenttype.CaseInsensitiveContentTypeSchemaMap;
import daffodil.conversion.contenttype.ContentTypeSchemaMap;
import daffodil.conversion.contenttype.S3ContentTypeSchemaMap;
import daffodil.conversion.dataprocessor.CachedDataProcessorRepo;
import daffodil.conversion.dataprocessor.DataProcessorRepo;
import daffodil.conversion.dataprocessor.S3DataProcessorRepo;
import software.amazon.awssdk.auth.credentials.EnvironmentVariableCredentialsProvider;
import software.amazon.awssdk.core.ResponseInputStream;
import software.amazon.awssdk.core.SdkSystemSetting;
import software.amazon.awssdk.core.async.AsyncResponseTransformer;
import software.amazon.awssdk.regions.Region;
import software.amazon.awssdk.services.s3.S3AsyncClient;
import software.amazon.awssdk.services.s3.model.CopyObjectRequest;
import software.amazon.awssdk.services.s3.model.CopyObjectResponse;
import software.amazon.awssdk.services.s3.model.DeleteObjectRequest;
import software.amazon.awssdk.services.s3.model.GetObjectResponse;
import software.amazon.awssdk.services.s3.model.HeadObjectRequest;
import software.amazon.awssdk.services.s3.model.Tag;
import software.amazon.awssdk.services.sns.SnsClient;
import software.amazon.awssdk.services.sns.model.PublishRequest;
import software.amazon.awssdk.services.sns.model.PublishResponse;
import software.amazon.awssdk.services.sns.model.SnsException;
import software.amazon.cloudwatchlogs.emf.logger.MetricsLogger;
import software.amazon.cloudwatchlogs.emf.model.DimensionSet;
import software.amazon.cloudwatchlogs.emf.model.Unit;

public class App implements RequestHandler<S3Event, Void> {
    private static final String INFOSET_EXTENSION = Utils.getEnv("INFOSET_EXTENSION", ".infoset.xml");
    private static final String ARCHIVE_BUCKET = System.getenv("ARCHIVE_BUCKET");
    private static final String DEAD_LETTER_BUCKET = System.getenv("DEAD_LETTER_BUCKET");
    private static final String NAMESPACE = System.getenv("NAMESPACE");
    private static final boolean ENABLE_DETAILED_METRICS = Boolean.valueOf(Utils.getEnv("ENABLE_DETAILED_METRICS", "false"));
    private static final String SNS_ERROR_TOPIC_ARN = System.getenv("SNS_ERROR_TOPIC_ARN");
    private static final Region REGION = Region.of(System.getenv(SdkSystemSetting.AWS_REGION.environmentVariable()));
    private static final Logger logger = LoggerFactory.getLogger(App.class);


    private final Pattern AMPERSAND = Pattern.compile("&");
    private final Encoder b64Encoder = Base64.getEncoder();
    private final Decoder b64Decoder = Base64.getDecoder();

    private final MetricsLogger metrics;
    private final S3AsyncClient s3Client;
    private final SnsClient snsClient;
    private final DataProcessorRepo dataProcessorRepo;
    private final ContentTypeSchemaMap contentTypeSchemaMap;

    public App() {
        this(
            S3AsyncClient.crtBuilder()
                .credentialsProvider(EnvironmentVariableCredentialsProvider.create())
                .region(REGION)
                .build(),
            SnsClient.builder()
                .region(REGION)
                .build(),
            new MetricsLogger()
                .setNamespace((NAMESPACE != null && !NAMESPACE.isBlank() ? NAMESPACE+"/" : "") + "Daffodil")            
        );
    }

    public App(
        S3AsyncClient s3Client,
        SnsClient snsClient,
        MetricsLogger metrics
    ) {
        this(
            s3Client,
            snsClient,
            metrics,
            new CachedContentTypeSchemaMap(
                new CaseInsensitiveContentTypeSchemaMap(
                    new S3ContentTypeSchemaMap(s3Client)
                )
            )
        );
    }

    public App(
        S3AsyncClient s3Client,
        SnsClient snsClient,
        MetricsLogger metrics,
        ContentTypeSchemaMap contentTypeSchemaMap
    ) {
        this(
            s3Client,
            snsClient,
            metrics,
            contentTypeSchemaMap,
            new CachedDataProcessorRepo(
                new S3DataProcessorRepo(s3Client, contentTypeSchemaMap)
            )
        );
    }

    public App(
        S3AsyncClient s3Client,
        SnsClient snsClient,
        MetricsLogger metrics,
        ContentTypeSchemaMap contentTypeSchemaMap,
        DataProcessorRepo dataProcessorRepo
    ) {
        this.s3Client = s3Client;
        this.snsClient = snsClient;
        this.metrics = metrics;
        this.contentTypeSchemaMap = contentTypeSchemaMap;
        this.dataProcessorRepo = dataProcessorRepo;
    }
    

    @Override
    public Void handleRequest(S3Event event, Context context) {
        logger.info("Detailed metrics enabled: " + ENABLE_DETAILED_METRICS);
        CompletableFuture<Void> res;
        List<CompletableFuture<Void>> responses = new ArrayList<>();
        // Will only ever contain one record, but looping anyhow
        for(S3EventNotificationRecord record : event.getRecords()) {
            String key;
            try {
                key = URLDecoder.decode(record.getS3().getObject().getKey(), StandardCharsets.UTF_8.toString());
            } catch (UnsupportedEncodingException e) {
                logger.warn(e.getLocalizedMessage());
                key = record.getS3().getObject().getKey();
            }
            final String s3Key = key;
            final String s3Bucket = record.getS3().getBucket().getName();
            logger.info("found id: " + s3Bucket+" "+s3Key);

            metrics.resetDimensions(false)
                .putDimensions(DimensionSet.of("By ContentType", "UNKNOWN"))
                .putProperty("S3BucketName", s3Bucket)
                .putProperty("S3Key", s3Key)
                .putProperty("Action", "Parse");

            // If the filename ends with .infoset, it needs to be unparsed
            res = s3Key.endsWith(INFOSET_EXTENSION) ? unparse(s3Bucket, s3Key) : parse(s3Bucket, s3Key);
            // Success, move to archive bucket
            
            res.thenAccept(r -> {
                if(ENABLE_DETAILED_METRICS) {
                    metrics
                        .putMetric("Count", 1, Unit.COUNT)
                        .flush();
                }
                if(ARCHIVE_BUCKET != null && !ARCHIVE_BUCKET.isBlank()) {
                    logger.info("Archiving s3://{}/{} to s3://{}/{}",
                        s3Bucket, s3Key, ARCHIVE_BUCKET, s3Key);
                    moveQuietly(s3Bucket, ARCHIVE_BUCKET, s3Key);
                } else {
                    logger.info("No archive bucket defined, deleting object s3://{}/{}", s3Bucket, s3Key);
                    s3Client.deleteObject(DeleteObjectRequest.builder().bucket(s3Bucket).key(s3Key).build())
                        .thenAccept(delRes -> {
                            logger.info("Successfully deleted object s3://{}/{}", s3Bucket, s3Key);
                        })
                        .exceptionally(t -> {
                            logger.warn("Error deleting file: " + t.getMessage());
                            return null;
                        })
                        .join();
                }
            });
            res.exceptionally(e -> {
                if(ENABLE_DETAILED_METRICS) {
                    metrics
                        .putProperty("ErrorMessage", e.getLocalizedMessage())
                        .putMetric("Errors", 1, Unit.COUNT)
                        .flush();
                }
                boolean moved = false;
                if(DEAD_LETTER_BUCKET != null && !DEAD_LETTER_BUCKET.isBlank()) {
                    logger.info("Moving failed transformed file s3://{}/{} to dead-letter bucket s3://{}/{}",
                        s3Bucket, s3Key, DEAD_LETTER_BUCKET, s3Key);
                    moved = moveQuietly(s3Bucket, DEAD_LETTER_BUCKET, s3Key);
                }
                if(SNS_ERROR_TOPIC_ARN != null && !SNS_ERROR_TOPIC_ARN.isBlank()) {
                    StringBuilder message = new StringBuilder(
                        String.format(
                            "An error occured while performing daffodil parsing for file s3://%s/%s\n",
                            s3Bucket, s3Key));
                    if(moved) {
                        message.append(String.format("The file was moved to s3://%s/%s\n", DEAD_LETTER_BUCKET, s3Key));
                    }
                    message.append(String.format("Error: %s", e.getLocalizedMessage()));
                    try {
                        PublishRequest req = PublishRequest.builder()
                            .topicArn(SNS_ERROR_TOPIC_ARN)
                            .subject(String.format("Daffodil Parsing Error", s3Bucket, s3Key))
                            .message(message.toString())
                            .build();
                        PublishResponse pres = snsClient.publish(req);
                        logger.info("Sent error notification to SNS: " + pres.messageId());
                    } catch(SnsException e1) {
                        logger.warn("Could not send error notification to SNS: " + e1.getLocalizedMessage());
                    }
                }
                return null;
            });
            responses.add(res);
        }

        // Wait for all to complete
        responses.forEach(future -> {
            try {
                future.join();
            } catch (CompletionException e) {
                e.printStackTrace();
            }
        });
        // Indicates failures in this lambda for metrics
        // if (responses.stream().filter(CompletableFuture::isCompletedExceptionally).count() > 0) {
        //     throw new RuntimeException("There were Failures");
        // }

        return null;
    }

    protected boolean moveQuietly(final String srcBucket, final String destBucket, final String key) {
        CopyObjectRequest copyObjectRequest = CopyObjectRequest.builder()
            .sourceBucket(srcBucket)
            .sourceKey(key)
            .destinationBucket(destBucket)
            .destinationKey(key)
            .build();

        try {
            CopyObjectResponse res = s3Client.copyObject(copyObjectRequest).join();
            if(res != null) {
                s3Client.deleteObject(DeleteObjectRequest.builder().bucket(srcBucket).key(key).build())
                .thenAccept(deleteRes -> {
                    System.out.println("File moved successfully from s3://" + srcBucket + "/" + key +
                            " to s3://" + destBucket + "/" + key);
                })
                .exceptionally(throwable -> {
                    logger.warn("Error deleting file: " + throwable.getMessage());
                    return null;
                })
                .join();
                return true;
            } else {
                logger.warn("CopyRequest response was null for s3://{}/{} to s3://{}/{}", srcBucket, key, destBucket, key);
            }
        } catch(Exception e) {
            logger.warn("Error occured while moving s3://{}/{} to s3://{}/{}", srcBucket, key, destBucket, key, e.getMessage());
        }
        return false;
    }

    /**
     * Parses a file into an infoset using DFDL DataProcessor, mapped by the S3 key.
     * 
     * Uses multi-threading to maximize performance
     * 
     * @param s3Bucket The s3 Bucket of the dfdl infoset to unparse
     * @param s3Key The s3 Key of the dfdl infoset to unparse
     * @return CompletableFuture of Void, indicating only when this has finished or if there was
     * an error
     */
    protected CompletableFuture<Void> parse(String s3Bucket, String s3Key) {
        final String contentType = contentTypeSchemaMap.getContentTypeFromPath(s3Key);
        if(contentType == null) {
            metrics.putProperty("ErrorType", "ContentType Mapping");
            return CompletableFuture.failedFuture(new RuntimeException("S3 key " + s3Key + " does not contain a valid content type"));
        }
       
        // DataProcessor future
        CompletableFuture<DataProcessor> dpFuture = dataProcessorRepo.get(contentType);

        // retrieve s3 object head to create tags
        CompletableFuture<Tag> tagFuture = s3Client.headObject(HeadObjectRequest.builder().bucket(s3Bucket).key(s3Key).build())
        .thenApply(objHead -> Tag.builder().key("OriginalContentTypeAndETag").value(
            b64Encoder.encodeToString(String.join("&", "ETag="+objHead.eTag(), "ContentType="+contentType).getBytes())
        ).build());

        CompletableFuture<List<Tag>>  tagsFuture =
            s3Client.getObjectTagging(r -> r.bucket(s3Bucket).key(s3Key))
                .thenApply(tags -> tags.tagSet());

        // Retrieve s3 Object as stream
        CompletableFuture<ResponseInputStream<GetObjectResponse>> inFuture = s3Client.getObject(req -> req.bucket(s3Bucket).key(s3Key), 
                AsyncResponseTransformer.toBlockingInputStream());

        CompletableFuture<?>[] allFutures = new CompletableFuture[]{
            dpFuture, tagFuture, inFuture, tagsFuture
        };

        // Wait for all to complete then do parsing
        CompletableFuture<Void> allWithFailFast =  CompletableFuture.allOf(allFutures)
        .thenAccept(ignoreVoid -> {
            logger.trace("Parsing...");
            String outputKey = s3Key + INFOSET_EXTENSION;
            List<Tag> tags = new ArrayList<>(tagsFuture.join());
            tags.add(tagFuture.join());
            try (ResponseInputStream<GetObjectResponse> in = inFuture.join(); OutputStream out = new S3OutputStream(s3Client, System.getenv("OUTPUT_BUCKET"), outputKey, null, tags, null)) {
                DataProcessor dp = dpFuture.get();
                long initialized = new Date().getTime();
                ParseResult res = dp.parse(new InputSourceDataInputStream(in), new XMLTextInfosetOutputter(out, false));
                if(res.isError()) {
                    List<Diagnostic> diags = res.getDiagnostics();
                    for(Diagnostic diag : diags) {
                        logger.error(diag.getMessage());
                    }
                    throw new Exception(String.format("There was an error with parser for %s", contentType), diags.get(0).getSomeCause());
                }
                long finished = new Date().getTime();
                metrics
                    .putProperty("Action", "Parse")
                    .putMetric("Latency", finished - initialized, Unit.MILLISECONDS);
            } catch(Exception e) {
                s3Client.deleteObject(DeleteObjectRequest.builder().bucket(System.getenv("OUTPUT_BUCKET")).key(outputKey).build());
                metrics.putProperty("ErrorType", "Parsing");
                throw new RuntimeException(e.getLocalizedMessage(), e);
            }
            logger.trace("Completed Parsing");
        });
        Stream.of(allFutures)
            .forEach(f -> f.exceptionally(e -> {
                logger.error("Exception in setting up parse", e);
                allWithFailFast.completeExceptionally(e);
                return null;
            }));
        return allWithFailFast;
    }

    /**
     * Unparses an infoset back to the original file by retrieving the s3 object tag
     * "OriginalContentTypeAndETag" and using the content type to map to which dfdl data parser to
     * use.
     * 
     * Uses multi-threading (CompletableFutures) to maximize performance.
     * 
     * @param s3Bucket The s3 Bucket of the dfdl infoset to unparse
     * @param s3Key The s3 Key of the dfdl infoset to unparse
     * @return CompletableFuture of Void, indicating only when this has finished or if there was
     * an error
     */
    protected CompletableFuture<Void> unparse(String s3Bucket, String s3Key) {
        // Retrieves the s3 object tags
        CompletableFuture<List<Tag>>  tagSetFuture =
            s3Client.getObjectTagging(r -> r.bucket(s3Bucket).key(s3Key))
            .thenApply(tags -> tags.tagSet());

        // When the s3 object tags have been retrieved from s3, base64 decodes the
        // OriginalContentTypeAndETag and create a Map from that.
        CompletableFuture<Map<String, String>> originalContentTypeAndETag =
            tagSetFuture.thenApply(tagSet -> {
                Optional<String> originalValuesOptional = tagSet.stream()
                    .filter(t -> t.key().equalsIgnoreCase("OriginalContentTypeAndETag"))
                    .map(t -> new String(b64Decoder.decode(t.value())))
                    .findFirst();

                if(!originalValuesOptional.isPresent()) {
                    logger.warn(String.format(
                        "No 'OriginalContentTypeAndETag' tag found for object %s, " +
                        "attempting to map unparser from key",
                        s3Key));
                    return new HashMap<>();
                }

                String originalValues = originalValuesOptional.get();
        
                Map<String, String> values = AMPERSAND.splitAsStream(originalValues)
                    .map(s -> s.split("="))
                    .collect(Collectors.toMap(e -> e[0], e-> e[1]));
                if(values.containsKey("ContentType")) {
                    metrics.putDimensions(DimensionSet.of("ContentType", values.get("ContentType")));
                }
                return values;
            });
        
        // After the OriginalContentTypeAndETag has been converted to a Map, get the original
        // ContentType. If the ContentType doesn't exist in the tag, then attempt to derive the
        // ContentType mapping from the object's key.
        CompletableFuture<DataProcessor> dpFuture = originalContentTypeAndETag.thenCompose(tagMap -> {
            String contentType = tagMap.get("ContentType");
            if(contentType == null) {
                contentType = contentTypeSchemaMap.getContentTypeFromPath(s3Key);
                if(contentType == null) {
                    metrics.putProperty("ErrorType", "ContentType Matching");
                    throw new RuntimeException(s3Key + " neither contains ContentType in OriginalContentTypeAndETag tag nor does the s3 key contain a valid content type");
                }
            }
            logger.info("content-type: " + contentType);
            metrics.putDimensions(DimensionSet.of("ContentType", contentType));

            return dataProcessorRepo.get(contentType);
        });

        // Retrieves the DFDL infoset from S3 as an InputStream
        CompletableFuture<ResponseInputStream<GetObjectResponse>> inFuture = s3Client.getObject(req -> req.bucket(s3Bucket).key(s3Key), 
            AsyncResponseTransformer.toBlockingInputStream());

        // Waits for all the above completable futures to finish, then creates an OutputStream
        // for the out file, and while stream-reading the input file, unparses the object and
        // stream-writes to the output file. This keeps memory overhead to a minimum for large files.
        CompletableFuture<?>[] allFutures = new CompletableFuture[]{
            dpFuture, tagSetFuture, inFuture, originalContentTypeAndETag
        };
        CompletableFuture<Void> allWithFailFast =  CompletableFuture.allOf(allFutures)
        .thenAccept(ignoreVoid -> {
            logger.info("Unparsing...");
            String outputKey = s3Key.substring(0, s3Key.length() - INFOSET_EXTENSION.length());

            DataProcessor dp = dpFuture.join();

            // Filter out the OriginalContentTypeAndETag tag
            List<Tag> tags = tagSetFuture.join().stream()
                .filter(t -> !t.key().equalsIgnoreCase("OriginalContentTypeAndETag"))
                .collect(Collectors.toList());

            Map<String, String> tagMap = originalContentTypeAndETag.join();
            String contentType = tagMap.get("ContentType");
            Consumer<String> validator = tagMap.containsKey("ETag") ? s -> {
                logger.trace("Validating eTags...");
                if(!s.equals(tagMap.get("ETag"))) {
                    metrics.putMetric("CheckSum Success Rate", 0.0, Unit.PERCENT);
                    logger.warn(s3Key + " eTag ["+s+"] did not validate with md5 checksum ["+tagMap.get("ETag")+"]");
                } else {
                    metrics.putMetric("CheckSum Success Rate", 100.0, Unit.PERCENT);
                    logger.debug("Etag values match");
                }
            } : null;

            String outputBucket = System.getenv("OUTPUT_BUCKET");
            // Try-with-resource, will automatically close these streams after the try/catch has
            // completed
            try (ResponseInputStream<GetObjectResponse> in = inFuture.join(); OutputStream out = new S3OutputStream(s3Client, outputBucket, outputKey, null, tags, validator)) {
                long initialized = new Date().getTime();
                UnparseResult res = dp.unparse(new XMLTextInfosetInputter(in), java.nio.channels.Channels.newChannel(out));
                if(res.isError()) {
                    List<Diagnostic> diags = res.getDiagnostics();
                    for(Diagnostic diag : diags) {
                        logger.error(diag.getMessage());
                    }
                    throw new Exception(String.format("There was an error with unparser for %s", contentType), diags.get(0).getSomeCause());
                }
                long finished = new Date().getTime();
                metrics
                    .putProperty("Action", "Unparse")
                    .putMetric("Latency", finished - initialized, Unit.MILLISECONDS);
            } catch(Exception e) {
                s3Client.deleteObject(DeleteObjectRequest.builder().bucket(outputBucket).key(outputKey).build());
                metrics.putProperty("ErrorType", "Unparsing");
                throw new RuntimeException(e);
            }
        });
        Stream.of(allFutures)
            .forEach(f -> f.exceptionally(e -> {
                logger.error("Exception in setting up unparse", e);
                allWithFailFast.completeExceptionally(e);
                return null;
            }));
        return allWithFailFast;
    }
}