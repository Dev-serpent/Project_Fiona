"""Cache lifecycle manager — owns all specialised cache instances.

Provides a single entry point for cache operations across
conversation, dataset, and persistent caches.
"""

from __future__ import annotations

import logging
from typing import Any

from SciRetrieval.cache.conversation_cache import ConversationCache
from SciRetrieval.cache.dataset_cache import DatasetCache
from SciRetrieval.cache.nist_cache import NISTCache
from SciRetrieval.interfaces import ICacheBackend

logger = logging.getLogger(__name__)


class CacheManager:
    """Manages the lifecycle of all SciRetrieval caches.

    Args:
        conversation_backend: Backend for conversation cache
            (defaults to in-memory).
        dataset_backend: Backend for dataset cache
            (defaults to disk-backed).
        persistent_backend: Backend for persistent / NIST cache
            (defaults to disk-backed).
    """

    def __init__(
        self,
        conversation_backend: ICacheBackend | None = None,
        dataset_backend: ICacheBackend | None = None,
        persistent_backend: ICacheBackend | None = None,
    ) -> None:
        self.conversation = ConversationCache(backend=conversation_backend)
        self.dataset = DatasetCache(backend=dataset_backend)
        self.persistent = NISTCache(backend=persistent_backend)

    async def evict_expired_all(self) -> dict[str, int]:
        """Evict expired entries from all caches.

        Returns:
            A dict mapping cache names to number of entries evicted.
        """
        return {
            "conversation": await self.conversation.evict_expired(),
            "dataset": await self.dataset.evict_expired(),
            "persistent": await self.persistent.evict_expired(),
        }

    async def clear_conversation(self, conversation_id: str) -> int:
        """Clear all cached entries for a specific conversation.

        Args:
            conversation_id: The conversation identifier.

        Returns:
            Number of entries removed.
        """
        return await self.conversation.clear_conversation(conversation_id)
