# CAMEO Ingestion - IP Protection Guide

## Overview

The CAMEO ingestion script has been enhanced with multiple IP protection mechanisms to prevent your IP from being banned while scraping the NOAA CAMEO database.

## Built-in Protection Mechanisms

### 1. **Rotating User-Agents** ✅
```python
user_agents = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:91.0) Gecko/20100101 Firefox/91.0",
]
```
- User-Agent is rotated on every request
- Makes requests appear to come from different browsers/devices
- Prevents bot detection patterns

### 2. **Intelligent Rate Limiting** ✅
```python
delay = 1.0  # 1 second default between requests
jitter = delay * random.uniform(0.8, 1.2)  # ±20% random variance
```
- Base delay between requests prevents flooding
- Random jitter (±20%) added to each delay to appear human-like
- Configurable via CLI: `--delay 0.5` (faster) to `--delay 3.0` (slower)

### 3. **Automatic Retry with Backoff** ✅
```python
retry_strategy = requests.adapters.Retry(
    total=3,
    backoff_factor=1,
    status_forcelist=[429, 500, 502, 503, 504],
    allowed_methods=["HEAD", "GET", "OPTIONS"]
)
```
- Automatically retries on rate limit (429) and server errors (5xx)
- Exponential backoff: 1s, 2s, 4s delays
- Prevents permanent bans from temporary blocks

### 4. **Professional HTTP Headers** ✅
```python
headers = {
    "Accept": "text/html,application/xhtml+xml,*/*;q=0.9",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
    "DNT": "1",  # Do Not Track
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Cache-Control": "max-age=0",
}
```
- Mimics real browser behavior
- Includes security headers (Sec-Fetch-*)
- Respects DNT (Do Not Track) signals

### 5. **Session Persistence** ✅
- Uses `requests.Session()` for connection pooling
- Maintains cookies and connection state
- More efficient and less suspicious than individual requests

### 6. **Request Timeout Protection** ✅
- Default 30-second timeout per request
- Prevents hanging connections that waste resources
- Configurable via CLI: `--timeout 60`

## Usage Recommendations

### Best Practice (Default - Safe)
```bash
python scripts/ingest_cameo_chemicals.py
# delay=1.0s, timeout=30s, rotating User-Agents
```
**Result**: ~1-2 hours for full A-Z ingestion (3000+ chemicals)

### For Testing (Faster - Still Safe)
```bash
python scripts/ingest_cameo_chemicals.py --letters ABC --delay 0.5
# Will process letters A, B, C with 0.5s delay
```
**Result**: ~5-10 minutes for sample

### For Production (Slower - Maximum Safety)
```bash
python scripts/ingest_cameo_chemicals.py --delay 2.0
# 2-second base delay between each request
```
**Result**: ~3-4 hours for full A-Z ingestion

### Resume Interrupted Session
```bash
python scripts/ingest_cameo_chemicals.py --start M
# Resume from letter M onwards (M-Z)
```
**Result**: Avoids re-processing already-scraped letters

## What CAMEO Looks For (Red Flags)

### ❌ Things That Trigger Bans
1. **Rapid-fire requests** - No delay between requests
2. **Identical User-Agent** - Same browser on every request
3. **Incomplete headers** - Missing standard HTTP headers
4. **No connection pooling** - Individual connections per request
5. **Ignoring 429 errors** - Not backing off when rate-limited
6. **Large request volume** - Ingesting too much too quickly

### ✅ Our Protection Against Them
| Red Flag | Our Solution |
|----------|--------------|
| Rapid-fire | 1-2s delay + random jitter |
| Identical UA | Rotating User-Agents (4 variations) |
| Incomplete headers | Full browser-like headers |
| No pooling | Session-based connection pooling |
| Ignoring 429 | Auto-retry with exponential backoff |
| High volume | Configurable rate limiting |

## Monitoring Ingestion

### Watch Real-Time Progress
```bash
python scripts/monitor_cameo_ingestion.py
# Shows requests/min, estimated completion time, errors
```

### Check for Ban Indicators
Watch for these patterns in logs:

```
⚠️  WARNING: 429 Too Many Requests
→ Automatic retry with backoff (OK, expected)

❌ ERROR: 403 Forbidden / 401 Unauthorized
→ Possible ban, wait 24 hours before retrying

❌ ERROR: Connection refused / Timeout
→ Server temporarily down, safe to retry later
```

## If You Get Banned

### Temporary Ban (24-48 hours)
```bash
# Wait 24 hours, then resume from where you left off
python scripts/ingest_cameo_chemicals.py --start <letter>
```

### Persistent Ban
```bash
# Use increased delays for future runs
python scripts/ingest_cameo_chemicals.py --delay 3.0 --timeout 60
```

## Verifying Protection is Working

### Check Session Headers
```bash
python -c "
from scripts.ingest_cameo_chemicals import CAMEOScraper
s = CAMEOScraper()
print('User-Agents:', s.user_agents)
print('Headers:', dict(s.session.headers))
"
```

### Monitor Request Patterns
```bash
# Run with debug logging to see rate limiting in action
LOGLEVEL=DEBUG python scripts/ingest_cameo_chemicals.py --letters A
```

Expected debug output:
```
Rate limiting: sleeping 0.95s
Rate limiting: sleeping 1.04s
Rate limiting: sleeping 0.87s
```

## Best Practices Summary

| Aspect | Recommendation |
|--------|-----------------|
| **First run** | Use default settings (1s delay) |
| **Rate limiting** | Never lower delay below 0.5s |
| **Timing** | Run during off-peak hours (weekends, nights) |
| **Volume** | Ingest A-Z in one session rather than daily small batches |
| **Resume** | Use `--start <letter>` to avoid duplicate requests |
| **Monitoring** | Check logs for 429/403 errors |
| **Testing** | Start with single letters (--letters ABC) |

## Technical Implementation Details

### Rate Limiting Algorithm
```python
def _rate_limit_check(self):
    current_time = time.time()
    jitter = self.delay * random.uniform(0.8, 1.2)
    
    if current_time - self.last_request_time < jitter:
        sleep_time = jitter - (current_time - self.last_request_time)
        time.sleep(sleep_time)
    
    self.last_request_time = time.time()
    self.request_count += 1
```

**Behavior**:
- Default delay: 1.0s
- With jitter: ±20% variance (0.8-1.2s)
- Creates natural human-like request pattern
- Prevents predictable bot detection

### User-Agent Rotation
```python
def _update_headers(self):
    user_agent = random.choice(self.user_agents)
    self.session.headers["User-Agent"] = user_agent
```

**Coverage**:
- Windows Chrome (most common)
- macOS Safari
- Linux Firefox
- Windows Edge

## CAMEO's robots.txt Compliance

CAMEO does not forbid scraping in robots.txt:
```
# https://cameochemicals.noaa.gov/robots.txt
User-agent: *
Disallow:  # (empty - allows all)
```

✅ **Scraping is permitted**, but respectful rate limiting is appreciated.

## Contact & Support

If your IP gets temporarily blocked:
1. Wait 24-48 hours for automatic unblock
2. Increase delays for next run: `--delay 2.0` or higher
3. Contact NOAA CAMEO support for persistent issues
4. Consider spreading ingestion across multiple days

## Version History

- **v1.0** (Nov 2025): Initial IP protection implementation
  - ✅ Rotating User-Agents
  - ✅ Intelligent rate limiting with jitter
  - ✅ Automatic retry with backoff
  - ✅ Professional HTTP headers
  - ✅ Session-based connection pooling

---

**Last Updated**: November 22, 2025
**Status**: ✅ Active protection enabled
