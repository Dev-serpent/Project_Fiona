"""Persistent cache for dataset / get_data results.

Backed by :class:`DiskBackend` for survival across restarts.
Default TTL is 24 hours.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from SciRetrieval.cache.cache_backend import DiskBackend
from SciRetrieval.interfaces import ICacheBackend
from SciRetrieval.models import CachePolicy

logger = logging.getLogger(__name__)

_DEFAULT_CACHE_DIR = Path.home() / ".cache" / "fiona" / "sciretrieval" / "datasets"


class DatasetCache:
    """Persistent cache for dataset-level retrieval results.

    Args:
        backend: Disk-backed cache backend.
        default_ttl: Default TTL in seconds (24 hours).
    """

    def __init__(
        self,
        backend: ICacheBackend | None = None,
        default_ttl: int = 86400,
    ) -> None:
        self._backend = backend or DiskBackend(_DEFAULT_CACHE_DIR)
        self._default_ttl = default_ttl

    async def get(self, key: str) -> Any | None:
        """Retrieve a cached value.

        Args:
            key: Cache key.

        Returns:
            The cached value, or *None*.
        """
        entry = await self._backend.get(key)
        if entry is None:
            return None
        return entry.value

    async def set(
        self,
        key: str,
        value: Any,
        policy: CachePolicy | None = None,
    ) -> None:
        """Store a value in the dataset cache.

        Args:
            key: Cache key.
            value: Value to cache.
            policy: Optional policy.  Defaults to a 24-hour, persistent policy.
        """
        if policy is None:
            policy = CachePolicy(ttl_seconds=self._default_ttl, persistent=True)
        await self._backend.set(key, value, policy)

    async def evict_expired(self) -> int:
        """Remove all expired entries.

        Returns:
            Number of entries evicted.
        """
        return await self._backend.evict_expired()
