package daffodil.conversion.dataprocessor;

import java.util.concurrent.CompletableFuture;

import org.apache.daffodil.japi.DataProcessor;

/**
 * Repository for retrieving a data processor for a given content type
 */
public interface DataProcessorRepo {

    /**
     * Retrieves the data processor for the given content type
     *
     * @param contentType The content type to map to the data processor
     * @return the data processor
     */
    CompletableFuture<DataProcessor> get(String contentType);

}