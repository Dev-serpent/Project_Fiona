"""Specialised cache for NIST dataset downloads.

NIST data changes infrequently, so the default TTL is 7 days.
The cache is backed by :class:`DiskBackend` in a dedicated directory.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from SciRetrieval.cache.cache_backend import DiskBackend
from SciRetrieval.interfaces import ICacheBackend
from SciRetrieval.models import CachePolicy, CacheEntry

logger = logging.getLogger(__name__)

_DEFAULT_NIST_CACHE_DIR = (
    Path(__file__).resolve().parent.parent / "data" / "nist_cache"
)


class NISTCache:
    """Cache for NIST WebBook data (HTML responses).

    Backed by :class:`DiskBackend` in ``SciRetrieval/data/nist_cache/``.
    Default TTL is 7 days.
    """

    def __init__(
        self,
        backend: ICacheBackend | None = None,
        default_ttl: int = 604800,
    ) -> None:
        self._backend = backend or DiskBackend(_DEFAULT_NIST_CACHE_DIR)
        self._default_ttl = default_ttl

    async def get(self, key: str) -> Any | None:
        """Retrieve a cached NIST response.

        Args:
            key: Cache key (e.g. compound name or query hash).

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
        """Store a value in the NIST cache.

        Args:
            key: Cache key.
            value: Value to cache.
            policy: Optional policy.  Defaults to 7-day persistent.
        """
        if policy is None:
            policy = CachePolicy(ttl_seconds=self._default_ttl, persistent=True)
        await self._backend.set(key, value, policy)

    async def has_downloaded(self, dataset_id: str) -> bool:
        """Check whether a specific dataset has been cached.

        Args:
            dataset_id: Identifier for the dataset.

        Returns:
            True if a cache entry exists for this ID.
        """
        key = f"dataset_marker:{dataset_id}"
        entry = await self._backend.get(key)
        return entry is not None

    async def mark_downloaded(self, dataset_id: str, metadata: dict[str, Any]) -> None:
        """Mark a dataset as downloaded.

        Args:
            dataset_id: Identifier for the dataset.
            metadata: Descriptive metadata about the download.
        """
        key = f"dataset_marker:{dataset_id}"
        policy = CachePolicy(ttl_seconds=self._default_ttl, persistent=True)
        await self._backend.set(key, metadata, policy)

    async def evict_expired(self) -> int:
        """Remove all expired entries.

        Returns:
            Number of entries evicted.
        """
        return await self._backend.evict_expired()
