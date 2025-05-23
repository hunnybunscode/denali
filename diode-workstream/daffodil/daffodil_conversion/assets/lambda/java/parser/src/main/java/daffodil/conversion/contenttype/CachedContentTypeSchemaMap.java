package daffodil.conversion.contenttype;

import java.time.Duration;
import java.util.Map;

import com.github.benmanes.caffeine.cache.Caffeine;
import com.github.benmanes.caffeine.cache.LoadingCache;

import daffodil.conversion.Utils;

/**
 * ContentTypeSchemaMap implementation that caches the retrieval of the map from the delegate
 * ContentTypeSchemaMap for a default of 1 minute
 */
public class CachedContentTypeSchemaMap extends ContentTypeSchemaMap {
    private final LoadingCache<String, Map<String, String>> contentTypeMapCache;
    private final ContentTypeSchemaMap delegate;


    public CachedContentTypeSchemaMap(ContentTypeSchemaMap delegate) {
        this(delegate, Integer.valueOf(Utils.getEnv("CONTENT_TYPE_CACHE_TTL_MINUTES", "1")));
    }

    public CachedContentTypeSchemaMap(ContentTypeSchemaMap delegate, int cache_ttl_minutes) {
        this(
            delegate,
            Caffeine.newBuilder()
                .maximumSize(1)
                .expireAfterWrite(Duration.ofMinutes(cache_ttl_minutes))
                .build(key -> delegate.getMap())
        );
    }

    public CachedContentTypeSchemaMap(ContentTypeSchemaMap delegate, LoadingCache<String, Map<String, String>> contentTypeMapCache) {
        this.delegate = delegate;
        this.contentTypeMapCache = contentTypeMapCache;
    }

    @Override
    public String get(String contentType) {
        return delegate.get(contentType, getMap());
    }

    @Override
    public boolean containsKey(String contentType) {
        return delegate.containsKey(contentType, getMap());
    }

    @Override
    protected Map<String, String> getMap() {
        return contentTypeMapCache.get("SINGLETON");
    }
    
}
