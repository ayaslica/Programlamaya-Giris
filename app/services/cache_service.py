from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from threading import Lock
from typing import Any


@dataclass
class CacheEntry:
    value: Any
    expires_at: float


class TTLCache:
    def __init__(self) -> None:
        self._store: dict[str, CacheEntry] = {}
        self._lock = Lock()

    def set(self, key: str, value: Any, ttl_sec: int) -> None:
        with self._lock:
            self._store[key] = CacheEntry(value=value, expires_at=datetime.now(tz=timezone.utc).timestamp() + ttl_sec)

    def get(self, key: str) -> Any | None:
        now = datetime.now(tz=timezone.utc).timestamp()
        with self._lock:
            entry = self._store.get(key)
            if not entry:
                return None
            if entry.expires_at <= now:
                self._store.pop(key, None)
                return None
            return entry.value

    def invalidate_prefix(self, prefix: str) -> None:
        with self._lock:
            keys = [key for key in self._store.keys() if key.startswith(prefix)]
            for key in keys:
                self._store.pop(key, None)


layer_ohlcv_cache = TTLCache()
layer_indicator_cache = TTLCache()
layer_backtest_cache = TTLCache()
layer_scan_cache = TTLCache()
