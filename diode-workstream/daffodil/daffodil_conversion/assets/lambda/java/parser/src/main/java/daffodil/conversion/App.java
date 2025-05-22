package daffodil.conversion;

import java.io.File;
import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;
import java.io.UnsupportedEncodingException;
import java.net.URI;
import java.net.URLDecoder;
import java.nio.channels.Channels;
import java.nio.charset.StandardCharsets;
import java.time.Duration;
import java.util.ArrayList;
import java.util.Base64;
import java.util.Date;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.Base64.Decoder;
import java.util.Base64.Encoder;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.CompletionException;
import java.util.function.Consumer;
import java.util.regex.Matcher;
import java.util.regex.Pattern;
import java.util.stream.Collectors;
import java.util.stream.Stream;

import org.apache.daffodil.japi.Daffodil;
import org.apache.daffodil.japi.DataProcessor;
import org.apache.daffodil.japi.Diagnostic;
import org.apache.daffodil.japi.InvalidParserException;
import org.apache.daffodil.japi.ParseResult;
import org.apache.daffodil.japi.ProcessorFactory;
import org.apache.daffodil.japi.UnparseResult;
import org.apache.daffodil.japi.infoset.XMLTextInfosetInputter;
import org.apache.daffodil.japi.infoset.XMLTextInfosetOutputter;
import org.apache.daffodil.japi.io.InputSourceDataInputStream;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.yaml.snakeyaml.Yaml;

import com.amazonaws.services.lambda.runtime.Context;
import com.amazonaws.services.lambda.runtime.RequestHandler;
import com.amazonaws.services.lambda.runtime.events.S3Event;
import com.amazonaws.services.lambda.runtime.events.models.s3.S3EventNotification.S3EventNotificationRecord;
import com.github.benmanes.caffeine.cache.Caffeine;
import com.github.benmanes.caffeine.cache.LoadingCache;

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
    private final Pattern CONTENT_TYPE = Pattern.compile("^\\w+\\.\\w+\\.(\\w+).*$");
    private static final String INFOSET_EXTENSION = getEnv("INFOSET_EXTENSION", ".infoset.xml");
    private static final String ARCHIVE_BUCKET = System.getenv("ARCHIVE_BUCKET");
    private static final String DEAD_LETTER_BUCKET = System.getenv("DEAD_LETTER_BUCKET");
    private static final String NAMESPACE = System.getenv("NAMESPACE");
    private static final boolean ENABLE_DETAILED_METRICS = Boolean.valueOf(getEnv("ENABLE_DETAILED_METRICS", "false"));
    private static final String SNS_ERROR_TOPIC_ARN = System.getenv("SNS_ERROR_TOPIC_ARN");
    private static final Region REGION = Region.of(System.getenv(SdkSystemSetting.AWS_REGION.environmentVariable()));
    private static final Logger logger = LoggerFactory.getLogger(App.class);

    private static final int CONTENT_TYPE_CACHE_TTL_MINUTES=Integer.valueOf(getEnv("CONTENT_TYPE_CACHE_TTL_MINUTES", "1"));
    private static final int DATA_PROCESSOR_CACHE_TTL_MINUTES=Integer.valueOf(getEnv("DATA_PROCESSOR_CACHE_TTL_MINUTES", "15"));

    private final MetricsLogger metrics = new MetricsLogger()
        .setNamespace((NAMESPACE != null && !NAMESPACE.isBlank() ? NAMESPACE+"/" : "") + "Daffodil");

    private final S3AsyncClient s3Client= S3AsyncClient.crtBuilder()
        .credentialsProvider(EnvironmentVariableCredentialsProvider.create())
        .region(REGION)
        .build();

    private final SnsClient snsClient = SnsClient.builder()
        .region(REGION)
        .build();

    private final org.apache.daffodil.japi.Compiler c = Daffodil.compiler();
    private final Pattern AMPERSAND = Pattern.compile("&");
    private final Yaml yaml = new Yaml();
    private final Encoder b64Encoder = Base64.getEncoder();
    private final Decoder b64Decoder = Base64.getDecoder();
    
    // Loading cache that evicts after a minute to retrieve the content-type mapping from s3
    @SuppressWarnings("unchecked")
    private final LoadingCache<String, Map<String, Object> > contentTypeMapCache = Caffeine.newBuilder()
        .maximumSize(1)
        .expireAfterWrite(Duration.ofMinutes(CONTENT_TYPE_CACHE_TTL_MINUTES))
        .build(bucket -> {
            String contentTypesFile = getEnv("CONTENT_TYPES_FILE", "content-types.yaml");
            try {
                return s3Client.getObject(req -> req.bucket(bucket).key(contentTypesFile),
                            AsyncResponseTransformer.toBlockingInputStream())
                    .thenApply(in -> (Map<String, Object>) yaml.load(in)).join();
            } catch(Exception e) {
                logger.warn("Could not load contentTypes map in cache, returning empty map: " + e.getLocalizedMessage());
                return new HashMap<>();
            }
        });
    // Loading cache that refreshes after 15 minutes (which means at 15 minutes you'll git the
    // cached value, but it will refresh in the background) for data processors.
    private final LoadingCache<String, CompletableFuture<DataProcessor>> dataProcessorCache = Caffeine.newBuilder()
        .maximumSize(100)
        .refreshAfterWrite(Duration.ofMinutes(DATA_PROCESSOR_CACHE_TTL_MINUTES))
        .build(contentType -> getDataProcessor(contentType).thenApply(dp -> {
            if(dp == null) {
                throw new RuntimeException("Could not find data processor for Content-Type: " + contentType);
            }
            return dp;
        }));

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
     * 
     * @param s3Bucket
     * @param s3Key
     * @return
     */
    protected CompletableFuture<Void> parse(String s3Bucket, String s3Key) {
        Matcher m = CONTENT_TYPE.matcher(s3Key);
        if(!m.matches()) {
            metrics.putProperty("ErrorType", "ContentType Mapping");
            return CompletableFuture.failedFuture(new RuntimeException("S3 key " + s3Key + " does not match the content type pattern"));
        }
        final String contentType = m.group(1);
        metrics.putDimensions(DimensionSet.of("By ContentType", contentType));

        // DataProcessor future
        CompletableFuture<DataProcessor> dpFuture = dataProcessorCache.get(contentType);

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
     * 
     * @param s3Bucket
     * @param s3Key
     * @return
     */
    protected CompletableFuture<Void> unparse(String s3Bucket, String s3Key) {
        CompletableFuture<List<Tag>>  tagSetFuture =
            s3Client.getObjectTagging(r -> r.bucket(s3Bucket).key(s3Key))
            .thenApply(tags -> tags.tagSet());
        
        CompletableFuture<Map<String, String>> originalContentTypeAndETag =
            tagSetFuture.thenApply(tagSet -> {
                String originalValues = tagSet.stream()
                    .filter(t -> t.key().equalsIgnoreCase("OriginalContentTypeAndETag"))
                    .map(t -> new String(b64Decoder.decode(t.value())))
                    .findFirst()
                    .get();
        
                Map<String, String> values = AMPERSAND.splitAsStream(originalValues)
                    .map(s -> s.split("="))
                    .collect(Collectors.toMap(e -> e[0], e-> e[1]));
                if(values.containsKey("ContentType")) {
                    metrics.putDimensions(DimensionSet.of("ContentType", values.get("ContentType")));
                }
                return values;
            });
        
        CompletableFuture<DataProcessor> dpFuture = originalContentTypeAndETag.thenCompose(tagMap -> {
            String contentType = tagMap.get("ContentType");
            if(contentType == null) {
                Matcher m = CONTENT_TYPE.matcher(s3Key);
                if(!m.matches()) {
                    metrics.putProperty("ErrorType", "ContentType Matching");
                    throw new RuntimeException(s3Key + " neither contain ContentType in OriginalContentTypeAndETag tag nor does the key match content type pattern");
                }
                contentType = m.group(1);
            }
            logger.info("content-type: " + contentType);
            metrics.putDimensions(DimensionSet.of("ContentType", contentType));

            return dataProcessorCache.get(contentType);
        });

        CompletableFuture<ResponseInputStream<GetObjectResponse>> inFuture = s3Client.getObject(req -> req.bucket(s3Bucket).key(s3Key), 
            AsyncResponseTransformer.toBlockingInputStream());

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

            try (ResponseInputStream<GetObjectResponse> in = inFuture.join(); OutputStream out = new S3OutputStream(s3Client, System.getenv("OUTPUT_BUCKET"), outputKey, null, tags, validator)) {
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
                s3Client.deleteObject(DeleteObjectRequest.builder().bucket(System.getenv("OUTPUT_BUCKET")).key(outputKey).build());
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

    private CompletableFuture<DataProcessor> getDataProcessor(String contentType) {
        final String schemaBucketName = System.getenv("SCHEMA_BUCKET");
        Object schemaFileObject = contentTypeMapCache.get(schemaBucketName).get(contentType);
        if(schemaFileObject == null) {
            throw new RuntimeException("No schema file found for content-type " + contentType);
        }
        String schemaFile = String.valueOf(schemaFileObject);

        return s3Client.getObject(req -> req.bucket(schemaBucketName).key(schemaFile+".dp"), 
            AsyncResponseTransformer.toBlockingInputStream())
        .thenApply(bis -> {
            try(InputStream in = bis) {
                return c.reload(Channels.newChannel(in));
            } catch (InvalidParserException | IOException e) {
                throw new RuntimeException(e);
            }
        }).exceptionally(e -> {
            logger.warn("Couldn't get precompiled schema " + schemaFile+".dp, will attempt to compile schema");
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

    private static final String getEnv(String key, String defaultValue) {
        String value = System.getenv(key);
        return value != null && !value.isEmpty() ? value : defaultValue;
    }
}