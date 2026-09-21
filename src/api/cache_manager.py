import json
import time
from pathlib import Path
from typing import Any, Optional
from config import CACHE_DIR, CACHE_TTL

class CacheManager:
    """Handles in-memory and local disk caching with TTL for FPL API responses."""
    def __init__(self, cache_dir: Path = CACHE_DIR, ttl: int = CACHE_TTL):
        self.cache_dir = Path(cache_dir)
        self.ttl = ttl
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._memory_cache: dict[str, tuple[float, Any]] = {}

    def get(self, key: str) -> Optional[Any]:
        current_time = time.time()
        # 1. Check in-memory cache
        if key in self._memory_cache:
            timestamp, data = self._memory_cache[key]
            if current_time - timestamp < self.ttl:
                return data

        # 2. Check disk cache
        cache_file = self.cache_dir / f"{key}.json"
        if cache_file.exists():
            try:
                with open(cache_file, "r", encoding="utf-8") as f:
                    cached_obj = json.load(f)
                    if current_time - cached_obj.get("timestamp", 0) < self.ttl:
                        data = cached_obj.get("data")
                        self._memory_cache[key] = (cached_obj["timestamp"], data)
                        return data
            except Exception:
                pass
        return None

    def set(self, key: str, data: Any) -> None:
        current_time = time.time()
        self._memory_cache[key] = (current_time, data)
        cache_file = self.cache_dir / f"{key}.json"
        try:
            with open(cache_file, "w", encoding="utf-8") as f:
                json.dump({"timestamp": current_time, "data": data}, f, indent=2)
        except Exception as e:
            print(f"Warning: Failed to write disk cache for {key}: {e}")

    def clear(self) -> None:
        self._memory_cache.clear()
        for f in self.cache_dir.glob("*.json"):
            try:
                f.unlink()
            except Exception:
                pass
