# PubChem API Implementation Audit

## Summary
✅ **Implementation is CORRECT and follows PubChem PUG REST best practices**

## Audit Date
November 29, 2025

## References
- Official Documentation: https://pubchem.ncbi.nlm.nih.gov/docs/pug-rest
- PubChem Usage Policy: Max 5 requests/second

## Implementation Analysis

### ✅ Correct Components

#### 1. **API Endpoint Structure** (`src/sds/external_validator.py`)
```python
BASE_URL = "https://pubchem.ncbi.nlm.nih.gov/rest/pug"
```
- Uses correct HTTPS (required by NCBI)
- Correct base path `/rest/pug`

#### 2. **Search by Name**
```python
url = f"{self.BASE_URL}/compound/name/{encoded_name}/property/MolecularFormula,MolecularWeight,IUPACName,InChI,InChIKey/JSON"
```
- ✅ Correct endpoint: `/compound/name/{identifier}/property/{properties}/JSON`
- ✅ URL encoding: `requests.utils.quote(name)`
- ✅ Multiple properties retrieved in one request (efficient)
- ✅ JSON format specified

#### 3. **Search by CAS Number**
```python
cid_url = f"{self.BASE_URL}/compound/name/{encoded_cas}/cids/JSON"
```
- ✅ Two-step process (CAS → CID → properties) is correct
- ✅ CAS numbers work via `/compound/name` endpoint
- ✅ Follows recommended pattern for xref lookups

#### 4. **Rate Limiting**
```python
MAX_REQUESTS_PER_SECOND = 5
RATE_LIMIT_DELAY = 0.21  # Slightly over 1/5 second
```
- ✅ Respects PubChem policy (5 req/s max)
- ✅ Conservative 0.21s delay (safer than exact 0.20s)
- ✅ Thread-safe implementation with `_last_request_time`

#### 5. **Caching Strategy**
```python
self._cache = SimpleCache(ttl_seconds=cache_ttl, max_size=500)
```
- ✅ Caches both positive and negative results
- ✅ TTL-based expiration (default 3600s / 1 hour)
- ✅ Reduces load on PubChem servers
- ✅ Cache key format: `f"name:{name.lower()}"` (case-insensitive)

#### 6. **Error Handling**
```python
if response.status_code == 200:
    return response.json()
elif response.status_code == 404:
    logger.debug("No match found")
elif response.status_code == 503:
    logger.warning("Service temporarily unavailable")
```
- ✅ Handles 200 (success)
- ✅ Handles 404 (not found) gracefully
- ✅ Handles 503 (server busy/maintenance)
- ✅ Handles timeouts with `timeout=10`
- ✅ Handles request exceptions

#### 7. **Response Parsing**
```python
if data and "PropertyTable" in data and "Properties" in data["PropertyTable"]:
    props = data["PropertyTable"]["Properties"]
    if props:
        result = props[0]  # First match
```
- ✅ Correct JSON structure parsing
- ✅ Safe navigation with existence checks
- ✅ Returns first match (standard behavior)

### 🔧 Fixed Issue

#### `structure_recognition.py` - Missing URL Encoding
**Before:**
```python
url = f"https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/name/{query}/property/..."
```

**After:**
```python
encoded_query = requests.utils.quote(query)
url = f"https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/name/{encoded_query}/property/..."
```

**Impact:** 
- Prevents errors with special characters in chemical names (e.g., spaces, parentheses, commas)
- Example: "2,4-D" becomes "2%2C4-D"
- Example: "Iron (III) oxide" becomes "Iron%20%28III%29%20oxide"

### 📋 Compliance Checklist

| Requirement | Status | Location |
|-------------|--------|----------|
| HTTPS required | ✅ | All API calls |
| URL encoding | ✅ | `external_validator.py` + fixed in `structure_recognition.py` |
| Rate limiting (5 req/s) | ✅ | `PubChemClient._rate_limit()` |
| Timeout handling | ✅ | `timeout=10` parameter |
| 404 handling | ✅ | Returns `None` for not found |
| 503 handling | ✅ | Logs warning, returns `None` |
| Caching | ✅ | `SimpleCache` with TTL |
| Proper JSON parsing | ✅ | Checks `PropertyTable.Properties` |
| Error logging | ✅ | Uses structured logger |

### 🎯 Best Practices Followed

1. **Efficient Batching**: Retrieves multiple properties in single request
2. **Negative Caching**: Caches "not found" to avoid repeated lookups
3. **Conservative Rate Limiting**: 0.21s > 0.20s (safer margin)
4. **Graceful Degradation**: Returns `None` on errors (doesn't crash)
5. **Logging Levels**: Uses `debug` for normal operations, `warning` for issues
6. **Thread Safety**: Rate limiter designed for concurrent access

### 📊 Performance Characteristics

**Cache Hit Ratio (estimated):**
- First lookup: PubChem API call (~200ms)
- Subsequent lookups (1 hour): Cache hit (~1ms)
- **~99.5% faster for repeated queries**

**Rate Limiting Impact:**
- Max throughput: ~4.76 req/s (1/0.21)
- Within PubChem limit: 5 req/s
- **Compliant and sustainable**

**Timeout Settings:**
- Connection timeout: 10s
- **Prevents hung requests**

## Recommendations

### ✅ Current Implementation
**No changes required** - implementation is production-ready and follows all PubChem guidelines.

### 💡 Optional Enhancements (Not Required)

1. **Exponential Backoff for 503**:
   ```python
   if response.status_code == 503:
       time.sleep(random.uniform(1, 5))  # Retry with backoff
   ```

2. **Batch API Support** (for future scale):
   - PubChem supports batch lookups via POST with multiple CIDs
   - Current implementation is fine for typical SDS processing volumes

3. **Circuit Breaker Pattern** (for high-volume scenarios):
   - Temporarily disable PubChem calls if error rate exceeds threshold
   - Current graceful degradation is sufficient for now

## Additional PubChem Services Reviewed

### Power User Gateway (PUG) - XML API
**Status: Not used (intentionally)**

The XML-based PUG interface (`https://pubchem.ncbi.nlm.nih.gov/pug/pug.cgi`) is designed for:
- Batch structure searches (similarity, substructure)
- Bulk downloads (thousands of compounds)
- Asynchronous queue-based operations

**Why we don't use it:**
- ✅ PUG REST is simpler and sufficient for our use case
- ✅ We don't need batch operations or complex structure searches
- ✅ Our lookups are synchronous and real-time (name/CAS → properties)
- ✅ PUG REST has better performance for simple queries

### Autocomplete API
**Status: Not used (optional enhancement)**

The autocomplete endpoint provides fuzzy matching and spell suggestions:
```
https://pubchem.ncbi.nlm.nih.gov/rest/autocomplete/compound/{term}/json?limit=10
```

**Potential use cases:**
- 💡 UI autocomplete for chemical name input
- 💡 Spell correction for misspelled chemical names
- 💡 Suggest alternative names during validation

**Example implementation:**
```python
def autocomplete(self, partial_name: str, limit: int = 10) -> List[str]:
    """Suggest chemical names based on partial input."""
    encoded = requests.utils.quote(partial_name)
    url = f"https://pubchem.ncbi.nlm.nih.gov/rest/autocomplete/compound/{encoded}/json?limit={limit}"
    data = self._make_request(url)
    if data and "dictionary_terms" in data:
        return data["dictionary_terms"].get("compound", [])
    return []
```

**Not implemented** because:
- Current implementation works for exact name matching
- Can be added later if UI enhancement is needed
- Does not affect current validation accuracy

## Conclusion

The PubChem API integration is **correctly implemented** and follows all official guidelines from https://pubchem.ncbi.nlm.nih.gov/docs/pug-rest:

- ✅ Correct endpoints and URL structure (PUG REST, not XML PUG)
- ✅ Proper URL encoding (now fixed in both files)
- ✅ Respects rate limits (5 req/s policy)
- ✅ Efficient caching strategy
- ✅ Robust error handling
- ✅ Appropriate API choice (REST vs XML PUG)
- ✅ Production-ready implementation

**Single fix applied:** Added URL encoding to `structure_recognition.py` to match the already-correct implementation in `external_validator.py`.

**Optional enhancements identified:**
- Autocomplete API for UI fuzzy matching (not required for core functionality)
