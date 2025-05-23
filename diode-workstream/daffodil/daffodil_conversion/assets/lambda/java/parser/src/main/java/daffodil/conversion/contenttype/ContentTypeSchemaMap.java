package daffodil.conversion.contenttype;

import java.util.Map;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

/**
 * Abstract class that provides the interface for getting the content-type to schema mapping.
 */
public abstract class ContentTypeSchemaMap {
    protected static final Logger logger = LoggerFactory.getLogger(ContentTypeSchemaMap.class);
    /**
     * Retrieves the schema file path for a given content-type
     * 
     * @param contentType The content-type to use as the key
     * @return the schema file path for the given content-type
     */
    public String get(String contentType) {
        return get(contentType, getMap());
    }
    protected String get(String contentType, Map<String, String> map) {
        return map.get(contentType);
    }

    /**
     * Returns if the map contains a content-type as a key
     * 
     * @param contentType the content-type to check if is a key in the map
     * @return if the map contains the content-type as a key
     */
    public boolean containsKey(String contentType) {
        return containsKey(contentType, getMap());
    }
    protected boolean containsKey(String contentType, Map<String, String> map) {
        return map.containsKey(contentType);
    }

    /**
     * @return the Map that contains the content-type to schema mapping
     */
    protected abstract Map<String, String> getMap();


    /**
     * Derives the content-type from the provided S3 key.
     * 
     * @param path The path to derive the content type from
     * @return the content type
     */
    public String getContentTypeFromPath(String path) {
        String[] prefixParts = path.split("/");
        boolean fileName = true;
        // Work backwards on the prefix parts, starting with the filename first
        for(int i = prefixParts.length-1; i >= 0; i--) {
            if(fileName) {
                fileName = false;
                for(String part: prefixParts[i].split("\\.")) {
                    if(containsKey(part)) {
                        return part;
                    }
                }
            } else if(containsKey(prefixParts[i])) {
                return prefixParts[i];
            }
        }
        
        return null;
    }
}
