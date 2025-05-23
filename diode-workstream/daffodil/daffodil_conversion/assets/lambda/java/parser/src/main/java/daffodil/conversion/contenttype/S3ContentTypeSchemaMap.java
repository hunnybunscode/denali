package daffodil.conversion.contenttype;

import java.util.HashMap;
import java.util.Map;
import java.util.stream.Collectors;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.yaml.snakeyaml.Yaml;

import daffodil.conversion.Utils;
import software.amazon.awssdk.core.async.AsyncResponseTransformer;
import software.amazon.awssdk.services.s3.S3AsyncClient;

public class S3ContentTypeSchemaMap extends ContentTypeSchemaMap {
    private static final Logger logger = LoggerFactory.getLogger(S3ContentTypeSchemaMap.class);
    private final Yaml yaml = new Yaml();
    private final S3AsyncClient s3Client;

    public S3ContentTypeSchemaMap(S3AsyncClient s3Client) {
        this.s3Client = s3Client;
    }

    @Override
    @SuppressWarnings("unchecked")
    protected Map<String, String> getMap() {
        String contentTypesFile = Utils.getEnv("CONTENT_TYPES_FILE", "content-types.yaml");
        String bucket = System.getenv("SCHEMA_BUCKET");
        try {
            return this.s3Client.getObject(req -> req.bucket(bucket).key(contentTypesFile),
                        AsyncResponseTransformer.toBlockingInputStream())
                .thenApply(in -> (Map<String, Object>) yaml.load(in))
                // Convert all values to strings
                .thenApply(m -> m.entrySet().stream().collect(Collectors.toMap(Map.Entry::getKey, e -> String.valueOf(e.getValue()))))
                .join();
        } catch(Exception e) {
            logger.warn("Could not load contentTypes map in cache, returning empty map: " + e.getLocalizedMessage());
            return new HashMap<>();
        }
    }

    
}
