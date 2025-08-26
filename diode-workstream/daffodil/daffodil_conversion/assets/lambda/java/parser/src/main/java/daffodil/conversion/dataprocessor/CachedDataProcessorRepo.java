package daffodil.conversion.dataprocessor;

import java.time.Duration;
import java.util.concurrent.CompletableFuture;

import org.apache.daffodil.japi.DataProcessor;
import com.github.benmanes.caffeine.cache.Caffeine;
import com.github.benmanes.caffeine.cache.LoadingCache;

import daffodil.conversion.Utils;

/**
 * A Cached implementation of the DataProcessorRepo that will delegate calls to retrieve the 
 * DataProcessor from the provided delegate, then caches it for a default of 15 minutes.
 */
public class CachedDataProcessorRepo implements DataProcessorRepo {
    private static final int DATA_PROCESSOR_CACHE_TTL_MINUTES=Integer.valueOf(Utils.getEnv("DATA_PROCESSOR_CACHE_TTL_MINUTES", "15"));
    
    // Loading cache that refreshes after 15 minutes (which means at 15 minutes you'll git the
    // cached value, but it will refresh in the background) for data processors.
    private final LoadingCache<String, CompletableFuture<DataProcessor>> dataProcessorCache;

    public CachedDataProcessorRepo(DataProcessorRepo delegate) {
        this(
            Caffeine.newBuilder()
                .maximumSize(100)
                .refreshAfterWrite(Duration.ofMinutes(DATA_PROCESSOR_CACHE_TTL_MINUTES))
                .build(contentType -> delegate.get(contentType).thenApply(dp -> {
                    if(dp == null) {
                        throw new RuntimeException("Could not find data processor for Content-Type: " + contentType);
                    }
                    return dp;
                }))
        );
    }

    public CachedDataProcessorRepo(LoadingCache<String, CompletableFuture<DataProcessor>> dataProcessorCache) {
        this.dataProcessorCache = dataProcessorCache;
    }

    @Override
    public CompletableFuture<DataProcessor> get(String contentType) {
        return dataProcessorCache.get(contentType);
    }
}
