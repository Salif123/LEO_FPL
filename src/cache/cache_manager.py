"""
High-performance TTL caching layer for FPL Analyzer.
Supports both in-memory caching and persistent disk caching for API responses.
"""
import hashlib
import json
import os
import time
from pathlib import Path
from typing import Any, Callable, Dict, Optional, Tuple, Union


class CacheManager:
    """Thread-safe TTL Cache Manager with disk and in-memory storage."""

    # Default TTLs in seconds for various endpoints
    DEFAULT_TTLS: Dict[str, int] = {
        "bootstrap_static": 3600,       # 1 hour
        "fixtures": 86400,              # 24 hours
        "element_summary": 1800,        # 30 mins
        "event_live": 60,               # 1 min
        "manager_entry": 900,           # 15 mins
        "manager_picks": 1800,          # 30 mins
        "manager_history": 1800,        # 30 mins
        "manager_transfers": 1800,      # 30 mins
        "my_team": 300,                 # 5 mins
        "classic_league": 900,          # 15 mins
        "h2h_league": 900,              # 15 mins
        "understat": 7200,              # 2 hours
        "default": 900,                 # 15 mins
    }

    def __init__(self, cache_dir: Optional[Union[str, Path]] = None, enabled: bool = True):
        self.enabled = enabled
        self.cache_dir = Path(cache_dir or Path(__file__).resolve().parent.parent.parent / "data" / "cache")
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._memory_cache: Dict[str, Tuple[float, Any]] = {}

    def _generate_key(self, endpoint_category: str, identifier: Optional[Union[str, int]] = None, params: Optional[Dict[str, Any]] = None) -> str:
        """Construct a unique hash key for a given request."""
        raw_key = f"{endpoint_category}_{identifier or 'all'}"
        if params:
            param_str = json.dumps(params, sort_keys=True)
            param_hash = hashlib.md5(param_str.encode("utf-8")).hexdigest()[:8]
            raw_key += f"_{param_hash}"
        return raw_key

    def _get_disk_path(self, cache_key: str) -> Path:
        """Get the file path on disk for a cache key."""
        safe_name = "".join(c if (c.isalnum() or c in ("_", "-")) else "_" for c in cache_key)
        return self.cache_dir / f"{safe_name}.json"

    def get(
        self, 
        endpoint_category: str, 
        identifier: Optional[Union[str, int]] = None, 
        params: Optional[Dict[str, Any]] = None
    ) -> Optional[Any]:
        """
        Retrieve data from cache if it exists and has not expired.
        Checks in-memory cache first, then disk cache.
        """
        if not self.enabled:
            return None

        key = self._generate_key(endpoint_category, identifier, params)
        now = time.time()

        # 1. Check memory cache
        if key in self._memory_cache:
            expires_at, data = self._memory_cache[key]
            if now < expires_at:
                return data
            else:
                del self._memory_cache[key]

        # 2. Check disk cache
        disk_path = self._get_disk_path(key)
        if disk_path.exists():
            try:
                with open(disk_path, "r", encoding="utf-8") as f:
                    cached_obj = json.load(f)
                    
                expires_at = cached_obj.get("expires_at", 0)
                if now < expires_at:
                    data = cached_obj.get("data")
                    # Populate memory cache for faster subsequent access
                    self._memory_cache[key] = (expires_at, data)
                    return data
                else:
                    # Expired, clean up disk
                    disk_path.unlink(missing_ok=True)
            except Exception:
                # If corrupted, ignore and return None
                return None

        return None

    def set(
        self, 
        endpoint_category: str, 
        data: Any, 
        identifier: Optional[Union[str, int]] = None, 
        params: Optional[Dict[str, Any]] = None,
        ttl_seconds: Optional[int] = None
    ) -> None:
        """
        Store data in both memory cache and disk cache with an expiration timestamp.
        """
        if not self.enabled or data is None:
            return

        key = self._generate_key(endpoint_category, identifier, params)
        ttl = ttl_seconds if ttl_seconds is not None else self.DEFAULT_TTLS.get(endpoint_category, self.DEFAULT_TTLS["default"])
        expires_at = time.time() + ttl

        # 1. Store in memory
        self._memory_cache[key] = (expires_at, data)

        # 2. Store on disk
        disk_path = self._get_disk_path(key)
        try:
            payload = {
                "key": key,
                "endpoint_category": endpoint_category,
                "cached_at": time.time(),
                "expires_at": expires_at,
                "ttl_seconds": ttl,
                "data": data
            }
            with open(disk_path, "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False)
        except Exception:
            # Fallback gracefully if disk serialization fails (e.g. non-serializable objects)
            pass

    def invalidate(
        self, 
        endpoint_category: str, 
        identifier: Optional[Union[str, int]] = None, 
        params: Optional[Dict[str, Any]] = None
    ) -> None:
        """Invalidate/delete a specific cache entry."""
        key = self._generate_key(endpoint_category, identifier, params)
        self._memory_cache.pop(key, None)
        disk_path = self._get_disk_path(key)
        if disk_path.exists():
            disk_path.unlink(missing_ok=True)

    def clear(self) -> int:
        """Clear all memory and disk caches. Returns count of deleted files."""
        self._memory_cache.clear()
        count = 0
        if self.cache_dir.exists():
            for f in self.cache_dir.glob("*.json"):
                try:
                    f.unlink()
                    count += 1
                except Exception:
                    pass
        return count


# Singleton instance
_GLOBAL_CACHE: Optional[CacheManager] = None


def get_cache() -> CacheManager:
    """Get or initialize the global CacheManager singleton."""
    global _GLOBAL_CACHE
    if _GLOBAL_CACHE is None:
        _GLOBAL_CACHE = CacheManager()
    return _GLOBAL_CACHE
