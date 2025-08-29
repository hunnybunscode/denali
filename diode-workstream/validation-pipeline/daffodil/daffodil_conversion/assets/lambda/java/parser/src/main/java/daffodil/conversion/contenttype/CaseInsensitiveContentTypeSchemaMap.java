package daffodil.conversion.contenttype;

import java.util.Map;
import java.util.stream.Collectors;

/**
 * Case-insensitive ContentTypeSchemaMap implementation that sets the keys of the content-type
 * to schema map as all uppercase, then uppercases the keys when accesses the Map.
 */
public class CaseInsensitiveContentTypeSchemaMap extends ContentTypeSchemaMap {
    private final ContentTypeSchemaMap delegate;

    public CaseInsensitiveContentTypeSchemaMap(ContentTypeSchemaMap delegate) {
        this.delegate = delegate;
    }

    @Override
    protected String get(String contentType, Map<String, String> map) {
        return map.get(contentType.toUpperCase());
    }

    @Override
    protected boolean containsKey(String contentType,  Map<String, String> map) {
        return map.containsKey(contentType.toUpperCase());
    }

    @Override
    protected Map<String, String> getMap() {
        Map<String, String> m = delegate.getMap();
        // Convert all keys to uppercase
        return m.keySet().stream().collect(Collectors.toMap(String::toUpperCase, m::get));
    }

}
