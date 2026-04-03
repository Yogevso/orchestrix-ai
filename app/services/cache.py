"""Simple TTL cache for incident analysis results.

Avoids redundant LLM calls for the same incident within a short window.
Production upgrade: Redis or similar distributed cache.
"""

import time
import logging
from typing import Any

logger = logging.getLogger(__name__)

_DEFAULT_TTL = 300  # 5 minutes


class TTLCache:
    def __init__(self, ttl: int = _DEFAULT_TTL) -> None:
        self._ttl = ttl
        self._store: dict[str, tuple[float, Any]] = {}

    def get(self, key: str) -> Any | None:
        entry = self._store.get(key)
        if entry is None:
            return None
        expires_at, value = entry
        if time.monotonic() > expires_at:
            del self._store[key]
            logger.debug("Cache expired: %s", key)
            return None
        logger.info("Cache hit: %s", key)
        return value

    def set(self, key: str, value: Any) -> None:
        self._store[key] = (time.monotonic() + self._ttl, value)
        logger.debug("Cache set: %s (ttl=%ds)", key, self._ttl)

    def invalidate(self, key: str) -> None:
        self._store.pop(key, None)

    def clear(self) -> None:
        self._store.clear()

    @property
    def size(self) -> int:
        # Prune expired entries on access
        now = time.monotonic()
        expired = [k for k, (exp, _) in self._store.items() if now > exp]
        for k in expired:
            del self._store[k]
        return len(self._store)


# Module-level singleton
incident_cache = TTLCache()
