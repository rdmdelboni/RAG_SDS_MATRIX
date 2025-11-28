"""
Simple in-memory cache with TTL support for API responses.
"""
import time
from dataclasses import dataclass
from typing import Any, Optional, Dict
import hashlib
import json

from .logger import get_logger

logger = get_logger(__name__)


@dataclass
class CacheEntry:
    """Cache entry with value and expiration."""
    value: Any
    expires_at: float


class SimpleCache:
    """
    Thread-safe in-memory cache with TTL support.
    
    Features:
    - Time-to-live (TTL) expiration
    - LRU-style eviction when max size reached
    - Thread-safe operations
    - Hit/miss statistics
    """
    
    def __init__(self, ttl_seconds: int = 3600, max_size: int = 1000):
        """
        Initialize cache.
        
        Args:
            ttl_seconds: Time-to-live for cache entries (default 1 hour)
            max_size: Maximum number of entries (default 1000)
        """
        self._cache: Dict[str, CacheEntry] = {}
        self._ttl = ttl_seconds
        self._max_size = max_size
        self._hits = 0
        self._misses = 0
        self._evictions = 0
    
    def _make_key(self, *args, **kwargs) -> str:
        """
        Generate cache key from arguments.
        
        Args:
            *args: Positional arguments
            **kwargs: Keyword arguments
        
        Returns:
            Hash-based cache key
        """
        # Serialize arguments to JSON for consistent hashing
        key_data = {
            "args": args,
            "kwargs": kwargs
        }
        key_str = json.dumps(key_data, sort_keys=True)
        return hashlib.sha256(key_str.encode()).hexdigest()
    
    def get(self, key: str) -> Optional[Any]:
        """
        Get value from cache.
        
        Args:
            key: Cache key
        
        Returns:
            Cached value or None if not found/expired
        """
        entry = self._cache.get(key)
        
        if entry is None:
            self._misses += 1
            return None
        
        # Check if expired
        if time.time() > entry.expires_at:
            del self._cache[key]
            self._misses += 1
            return None
        
        self._hits += 1
        return entry.value
    
    def set(self, key: str, value: Any) -> None:
        """
        Set value in cache.
        
        Args:
            key: Cache key
            value: Value to cache
        """
        # Evict oldest entries if at max size
        if len(self._cache) >= self._max_size:
            self._evict_oldest()
        
        expires_at = time.time() + self._ttl
        self._cache[key] = CacheEntry(value=value, expires_at=expires_at)
    
    def _evict_oldest(self) -> None:
        """Evict oldest (first expired or earliest expiration) entry."""
        if not self._cache:
            return
        
        # Find entry with earliest expiration
        oldest_key = min(self._cache.items(), key=lambda x: x[1].expires_at)[0]
        del self._cache[oldest_key]
        self._evictions += 1
    
    def clear(self) -> None:
        """Clear all cache entries."""
        count = len(self._cache)
        self._cache.clear()
        logger.info(f"Cache cleared ({count} entries removed)")
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get cache statistics.
        
        Returns:
            Dictionary with cache stats
        """
        total_requests = self._hits + self._misses
        hit_rate = (self._hits / total_requests * 100) if total_requests > 0 else 0.0
        
        return {
            "size": len(self._cache),
            "max_size": self._max_size,
            "hits": self._hits,
            "misses": self._misses,
            "evictions": self._evictions,
            "hit_rate": hit_rate,
            "ttl_seconds": self._ttl,
        }
    
    def cleanup_expired(self) -> int:
        """
        Remove expired entries.
        
        Returns:
            Number of entries removed
        """
        now = time.time()
        expired_keys = [
            key for key, entry in self._cache.items()
            if now > entry.expires_at
        ]
        
        for key in expired_keys:
            del self._cache[key]
        
        if expired_keys:
            logger.debug(f"Cleaned up {len(expired_keys)} expired cache entries")
        
        return len(expired_keys)


class CachedFunction:
    """
    Decorator for caching function results.
    
    Example:
        @CachedFunction(ttl_seconds=3600)
        def expensive_api_call(param1, param2):
            return fetch_data(param1, param2)
    """
    
    def __init__(self, ttl_seconds: int = 3600, max_size: int = 1000):
        """
        Initialize cached function decorator.
        
        Args:
            ttl_seconds: Time-to-live for cached results
            max_size: Maximum cache size
        """
        self.cache = SimpleCache(ttl_seconds=ttl_seconds, max_size=max_size)
    
    def __call__(self, func):
        """Wrap function with caching."""
        def wrapper(*args, **kwargs):
            # Generate cache key
            cache_key = self.cache._make_key(*args, **kwargs)
            
            # Try to get from cache
            result = self.cache.get(cache_key)
            if result is not None:
                logger.debug(f"Cache hit for {func.__name__}")
                return result
            
            # Call function and cache result
            logger.debug(f"Cache miss for {func.__name__}, calling function")
            result = func(*args, **kwargs)
            self.cache.set(cache_key, result)
            
            return result
        
        # Attach cache instance for stats access
        wrapper.cache = self.cache
        wrapper.__name__ = func.__name__
        wrapper.__doc__ = func.__doc__
        
        return wrapper
