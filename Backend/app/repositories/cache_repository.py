import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Optional

from diskcache import Cache

from app.config import get_settings

logger = logging.getLogger(__name__)


class CacheRepository:
    """Repository for caching expensive API responses."""
    
    def __init__(self):
        settings = get_settings()
        cache_dir = Path(settings.cache_dir)
        cache_dir.mkdir(parents=True, exist_ok=True)
        self._cache = Cache(str(cache_dir))
        self._ttl_seconds = settings.cache_ttl_hours * 3600
    
    def get(self, key: str) -> Optional[Any]:
        """Get a value from cache."""
        try:
            value = self._cache.get(key)
            if value is not None:
                logger.debug(f"Cache hit for key: {key}")
                return json.loads(value) if isinstance(value, str) else value
            logger.debug(f"Cache miss for key: {key}")
            return None
        except Exception as e:
            logger.error(f"Cache get error for key {key}: {e}")
            return None
    
    def set(self, key: str, value: Any, ttl_seconds: Optional[int] = None) -> bool:
        """Set a value in cache with optional custom TTL."""
        try:
            ttl = ttl_seconds if ttl_seconds is not None else self._ttl_seconds
            serialized = json.dumps(value) if not isinstance(value, str) else value
            self._cache.set(key, serialized, expire=ttl)
            logger.debug(f"Cached key: {key} with TTL: {ttl}s")
            return True
        except Exception as e:
            logger.error(f"Cache set error for key {key}: {e}")
            return False
    
    def delete(self, key: str) -> bool:
        """Delete a key from cache."""
        try:
            self._cache.delete(key)
            logger.debug(f"Deleted cache key: {key}")
            return True
        except Exception as e:
            logger.error(f"Cache delete error for key {key}: {e}")
            return False
    
    def clear(self) -> bool:
        """Clear all cached data."""
        try:
            self._cache.clear()
            logger.info("Cache cleared")
            return True
        except Exception as e:
            logger.error(f"Cache clear error: {e}")
            return False
    
    def get_stats(self) -> dict:
        """Get cache statistics."""
        return {
            "size": len(self._cache),
            "volume": self._cache.volume(),
        }
    
    def close(self):
        """Close the cache connection."""
        self._cache.close()


_cache_instance: Optional[CacheRepository] = None


def get_cache_repository() -> CacheRepository:
    """Get singleton cache repository instance."""
    global _cache_instance
    if _cache_instance is None:
        _cache_instance = CacheRepository()
    return _cache_instance
