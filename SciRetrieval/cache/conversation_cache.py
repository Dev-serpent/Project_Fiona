"""Conversation-aware cache for retrieval results.

Caches ``SciLabResult`` objects keyed by conversation ID + query hash.
Backed by a fast in-memory store by default.
"""

from __future__ import annotations

import logging
from typing import Any

from SciRetrieval.cache.cache_backend import MemoryBackend
from SciRetrieval.interfaces import ICacheBackend
from SciRetrieval.models import CachePolicy

logger = logging.getLogger(__name__)


class ConversationCache:
    """Caches retrieval results within a conversation.

    Entries expire after a configurable TTL (default 5 minutes).

    Args:
        backend: Cache backend (defaults to :class:`MemoryBackend`).
        default_ttl: Default TTL in seconds.
    """

    def __init__(
        self,
        backend: ICacheBackend | None = None,
        default_ttl: int = 300,
    ) -> None:
        self._backend = backend or MemoryBackend()
        self._default_ttl = default_ttl

    async def get(self, key: str) -> Any | None:
        """Retrieve a cached value by key.

        Args:
            key: Cache key (e.g. ``"conv:abc123:def456"``).

        Returns:
            The cached value, or *None* if not found or expired.
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
        """Store a value in the cache.

        Args:
            key: Cache key.
            value: Value to cache.
            policy: Optional policy.  Defaults to ``CachePolicy(ttl_seconds=TTL)``.
        """
        if policy is None:
            policy = CachePolicy(ttl_seconds=self._default_ttl)
        await self._backend.set(key, value, policy)

    async def clear_conversation(self, conversation_id: str) -> int:
        """Delete all entries for a conversation.

        Iterates all keys matching ``f"conv:{conversation_id}:"`` prefix
        and deletes them.

        Note: This is only efficient for backends that support iteration.
        For ``MemoryBackend`` it scans all keys.

        Returns:
            Number of entries removed.
        """
        count = 0
        # MemoryBackend: scan internal dict
        if isinstance(self._backend, MemoryBackend):
            keys_to_delete = [
                k
                for k in self._backend._store
                if k.startswith(f"conv:{conversation_id}:")
            ]
            for k in keys_to_delete:
                if await self._backend.delete(k):
                    count += 1
        return count

    async def evict_expired(self) -> int:
        """Remove all expired entries.

        Returns:
            Number of entries evicted.
        """
        return await self._backend.evict_expired()
