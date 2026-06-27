"""Tests for CacheManager — orchestration of all cache types."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

pytestmark = pytest.mark.asyncio

from SciRetrieval.cache_manager import CacheManager
from SciRetrieval.interfaces import ICacheBackend
from SciRetrieval.models import CachePolicy


class TestCacheManager:
    """CacheManager lifecycle orchestration."""

    def test_construction_with_defaults(self) -> None:
        """CacheManager creates default backends."""
        mgr = CacheManager()
        assert mgr.conversation is not None
        assert mgr.dataset is not None
        assert mgr.persistent is not None

    def test_construction_with_mock_backends(self) -> None:
        """CacheManager wraps provided backends in specialised caches."""
        conv_backend = MagicMock(spec=ICacheBackend)
        dataset_backend = MagicMock(spec=ICacheBackend)
        persistent_backend = MagicMock(spec=ICacheBackend)

        mgr = CacheManager(
            conversation_backend=conv_backend,
            dataset_backend=dataset_backend,
            persistent_backend=persistent_backend,
        )
        assert mgr.conversation._backend == conv_backend
        assert mgr.dataset._backend == dataset_backend
        assert mgr.persistent._backend == persistent_backend

    async def test_evict_expired_all(self) -> None:
        """evict_expired_all returns counts per cache type."""
        conv_backend = AsyncMock(spec=ICacheBackend)
        dataset_backend = AsyncMock(spec=ICacheBackend)
        persistent_backend = AsyncMock(spec=ICacheBackend)

        conv_backend.evict_expired = AsyncMock(return_value=3)
        dataset_backend.evict_expired = AsyncMock(return_value=1)
        persistent_backend.evict_expired = AsyncMock(return_value=0)

        # We need to use real caches wrapping mock backends
        from SciRetrieval.cache.conversation_cache import ConversationCache
        from SciRetrieval.cache.dataset_cache import DatasetCache
        from SciRetrieval.cache.nist_cache import NISTCache

        class TestableCacheManager(CacheManager):
            def __init__(self):
                self.conversation = ConversationCache(backend=conv_backend)
                self.dataset = DatasetCache(backend=dataset_backend)
                self.persistent = NISTCache(backend=persistent_backend)

        mgr = TestableCacheManager()
        counts = await mgr.evict_expired_all()

        assert counts["conversation"] == 3
        assert counts["dataset"] == 1
        assert counts["persistent"] == 0

    async def test_clear_conversation_delegates(self) -> None:
        """clear_conversation delegates to conversation cache."""
        conv_backend = MagicMock(spec=ICacheBackend)
        mgr = CacheManager(conversation_backend=conv_backend)

        # Patch clear_conversation
        mgr.conversation.clear_conversation = AsyncMock(return_value=5)  # type: ignore[method-assign]

        removed = await mgr.clear_conversation("conv_123")
        assert removed == 5

    async def test_evict_expired_all_with_real_backends(self) -> None:
        """Integration test with real MemoryBackend instances."""
        from SciRetrieval.cache.cache_backend import MemoryBackend

        conv_backend = MemoryBackend()
        dataset_backend = MemoryBackend()
        persistent_backend = MemoryBackend()

        # Add some expired and valid entries to each
        await conv_backend.set("expired", "old", CachePolicy(ttl_seconds=0))
        await conv_backend.set("valid", "fresh", CachePolicy(ttl_seconds=3600))
        await dataset_backend.set("expired", "old", CachePolicy(ttl_seconds=0))
        await persistent_backend.set("expired", "old", CachePolicy(ttl_seconds=0))

        mgr = CacheManager(
            conversation_backend=conv_backend,
            dataset_backend=dataset_backend,
            persistent_backend=persistent_backend,
        )

        counts = await mgr.evict_expired_all()
        assert counts["conversation"] >= 1
        assert counts["dataset"] >= 1
        assert counts["persistent"] >= 1
