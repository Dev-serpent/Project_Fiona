"""Cache backend implementations for SciRetrieval.

Provides three backends:

* :class:`MemoryBackend` — in-process dict, fast but not persistent.
* :class:`DiskBackend` — JSON files on disk, survives restarts.
* :class:`SQLiteBackend` — stub / placeholder for future use.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from SciRetrieval.interfaces import ICacheBackend
from SciRetrieval.models import CacheEntry, CachePolicy

logger = logging.getLogger(__name__)


# ======================================================================
# Memory Backend
# ======================================================================


class MemoryBackend(ICacheBackend):
    """Simple in-memory cache backend.

    Thread-safe via ``asyncio.Lock``.  Entries are stored in a plain
    ``dict`` and evicted when expired.
    """

    def __init__(self) -> None:
        self._store: dict[str, CacheEntry] = {}
        self._lock = asyncio.Lock()

    async def get(self, key: str) -> CacheEntry | None:
        async with self._lock:
            entry = self._store.get(key)
            if entry is None:
                return None
            if entry.is_expired:
                del self._store[key]
                return None
            return entry

    async def set(self, key: str, value: Any, policy: CachePolicy) -> None:
        entry = CacheEntry(key=key, value=value, policy=policy)
        async with self._lock:
            self._store[key] = entry

    async def delete(self, key: str) -> bool:
        async with self._lock:
            if key in self._store:
                del self._store[key]
                return True
            return False

    async def clear(self) -> None:
        async with self._lock:
            self._store.clear()

    async def evict_expired(self) -> int:
        count = 0
        async with self._lock:
            expired_keys = [k for k, v in self._store.items() if v.is_expired]
            for k in expired_keys:
                del self._store[k]
                count += 1
        return count


# ======================================================================
# Disk Backend
# ======================================================================


class DiskBackend(ICacheBackend):
    """Filesystem-backed cache using JSON files.

    Each cache entry is stored as an individual JSON file under the
    configured ``cache_dir``.  Keys are sanitised for filesystem safety.

    Args:
        cache_dir: Directory to store cache files.  Created if it does
            not exist.
    """

    def __init__(self, cache_dir: str | Path) -> None:
        self._cache_dir = Path(cache_dir)
        self._cache_dir.mkdir(parents=True, exist_ok=True)
        self._lock = asyncio.Lock()

    async def get(self, key: str) -> CacheEntry | None:
        sanitised = self._sanitise_key(key)
        path = self._cache_dir / sanitised
        if not path.exists():
            return None

        try:
            data = await self._read_json(path)
            entry = self._deserialise(key, data)
            if entry and entry.is_expired:
                await self.delete(key)
                return None
            return entry
        except Exception as exc:
            logger.warning("Failed to read cache entry %s: %s", key, exc)
            return None

    async def set(self, key: str, value: Any, policy: CachePolicy) -> None:
        sanitised = self._sanitise_key(key)
        path = self._cache_dir / sanitised

        data = {
            "key": key,
            "value": value,
            "ttl_seconds": policy.ttl_seconds,
            "persistent": policy.persistent,
            "max_size_bytes": policy.max_size_bytes,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

        try:
            await self._write_json(path, data)
        except Exception as exc:
            logger.warning("Failed to write cache entry %s: %s", key, exc)

    async def delete(self, key: str) -> bool:
        sanitised = self._sanitise_key(key)
        path = self._cache_dir / sanitised
        if path.exists():
            try:
                path.unlink()
                return True
            except OSError as exc:
                logger.warning("Failed to delete cache entry %s: %s", key, exc)
        return False

    async def clear(self) -> None:
        for child in self._cache_dir.iterdir():
            if child.is_file():
                try:
                    child.unlink()
                except OSError as exc:
                    logger.warning("Failed to clear cache file %s: %s", child, exc)

    async def evict_expired(self) -> int:
        count = 0
        for child in self._cache_dir.iterdir():
            if child.is_file():
                try:
                    data = await self._read_json(child)
                    entry = self._deserialise(child.name, data)
                    if entry and entry.is_expired:
                        child.unlink()
                        count += 1
                except Exception:
                    continue
        return count

    # ------------------------------------------------------------------
    # Serialisation helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _sanitise_key(key: str) -> str:
        """Sanitise a cache key for filesystem use."""
        sanitised = key.replace(":", "_").replace("/", "_").replace(" ", "_")
        # Limit length to avoid filesystem issues
        if len(sanitised) > 200:
            import hashlib
            sanitised = hashlib.sha256(sanitised.encode("utf-8")).hexdigest()[:32]
        return sanitised + ".json"

    @staticmethod
    def _deserialise(key: str, data: dict[str, Any]) -> CacheEntry | None:
        """Reconstruct a CacheEntry from a deserialised dict."""
        try:
            policy = CachePolicy(
                ttl_seconds=data.get("ttl_seconds", 300),
                persistent=data.get("persistent", False),
                max_size_bytes=data.get("max_size_bytes"),
            )
            created_at_str = data.get("created_at", "")
            if created_at_str:
                created_at = datetime.fromisoformat(created_at_str)
            else:
                created_at = datetime.now(timezone.utc)

            return CacheEntry(
                key=data.get("key", key),
                value=data.get("value"),
                policy=policy,
                created_at=created_at,
            )
        except Exception as exc:
            logger.warning("Failed to deserialise cache entry %s: %s", key, exc)
            return None

    @staticmethod
    async def _read_json(path: Path) -> dict[str, Any]:
        """Read and parse a JSON file asynchronously."""
        loop = asyncio.get_running_loop()
        try:
            return await loop.run_in_executor(None, _read_json_sync, path)
        except Exception as exc:
            return {"_error": str(exc)}

    @staticmethod
    async def _write_json(path: Path, data: dict[str, Any]) -> None:
        """Write a dict as JSON to a file asynchronously."""
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, _write_json_sync, path, data)


# ======================================================================
# SQLite Backend (stub / placeholder)
# ======================================================================


class SQLiteBackend(ICacheBackend):
    """SQLite-based cache backend — **stub** for future implementation.

    TODO: Implement with aiosqlite for proper concurrent access.
    """

    def __init__(self, db_path: str | Path = ":memory:") -> None:
        self._db_path = str(db_path)
        self._initialised = False
        logger.warning(
            "SQLiteBackend is a stub — not yet implemented. "
            "Use MemoryBackend or DiskBackend instead."
        )

    async def get(self, key: str) -> CacheEntry | None:
        raise NotImplementedError("SQLiteBackend is a stub — not implemented")

    async def set(self, key: str, value: Any, policy: CachePolicy) -> None:
        raise NotImplementedError("SQLiteBackend is a stub — not implemented")

    async def delete(self, key: str) -> bool:
        raise NotImplementedError("SQLiteBackend is a stub — not implemented")

    async def clear(self) -> None:
        raise NotImplementedError("SQLiteBackend is a stub — not implemented")

    async def evict_expired(self) -> int:
        raise NotImplementedError("SQLiteBackend is a stub — not implemented")


# ======================================================================
# Synchronous I/O helpers (run in executor)
# ======================================================================


def _read_json_sync(path: Path) -> dict[str, Any]:
    """Synchronous JSON file reader."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            return dict(json.load(f))
    except (json.JSONDecodeError, FileNotFoundError) as exc:
        return {"_error": str(exc)}


def _write_json_sync(path: Path, data: dict[str, Any]) -> None:
    """Synchronous JSON file writer."""
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, default=str)
