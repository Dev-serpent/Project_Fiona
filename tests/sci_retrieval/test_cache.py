"""Tests for cache backends and specialised caches.

Covers MemoryBackend, DiskBackend, ConversationCache, and NISTCache.
"""

from __future__ import annotations

import pytest

import json
from datetime import datetime, timedelta, timezone

import pytest

from SciRetrieval.models import CacheEntry, CachePolicy

pytestmark = pytest.mark.asyncio
from SciRetrieval.cache.cache_backend import MemoryBackend, DiskBackend
from SciRetrieval.cache.conversation_cache import ConversationCache
from SciRetrieval.cache.nist_cache import NISTCache
from SciRetrieval.errors import CacheCorruptionError


# ======================================================================
# MemoryBackend
# ======================================================================


class TestMemoryBackend:
    """In-memory cache backend."""

    async def test_set_and_get(self) -> None:
        cache = MemoryBackend()
        await cache.set("key1", "value1", CachePolicy(ttl_seconds=3600))
        entry = await cache.get("key1")
        assert entry is not None
        assert entry.value == "value1"

    async def test_get_nonexistent(self) -> None:
        cache = MemoryBackend()
        entry = await cache.get("nonexistent")
        assert entry is None

    async def test_delete_existing(self) -> None:
        cache = MemoryBackend()
        await cache.set("key1", "value1", CachePolicy())
        deleted = await cache.delete("key1")
        assert deleted is True
        entry = await cache.get("key1")
        assert entry is None

    async def test_delete_nonexistent(self) -> None:
        cache = MemoryBackend()
        deleted = await cache.delete("nonexistent")
        assert deleted is False

    async def test_clear(self) -> None:
        cache = MemoryBackend()
        await cache.set("key1", "v1", CachePolicy())
        await cache.set("key2", "v2", CachePolicy())
        await cache.clear()
        assert await cache.get("key1") is None
        assert await cache.get("key2") is None

    async def test_evict_expired(self) -> None:
        cache = MemoryBackend()
        await cache.set("expired", "old", CachePolicy(ttl_seconds=0))  # immediate expiry
        await cache.set("valid", "fresh", CachePolicy(ttl_seconds=3600))
        evicted = await cache.evict_expired()
        assert evicted == 1
        assert await cache.get("valid") is not None
        assert await cache.get("expired") is None

    async def test_stale_entry_not_returned(self) -> None:
        """Expired entry is not returned from get()."""
        cache = MemoryBackend()
        await cache.set("stale", "old", CachePolicy(ttl_seconds=0))
        entry = await cache.get("stale")
        assert entry is None

    async def test_set_overwrites(self) -> None:
        cache = MemoryBackend()
        await cache.set("key", "first", CachePolicy())
        await cache.set("key", "second", CachePolicy())
        entry = await cache.get("key")
        assert entry.value == "second"


# ======================================================================
# DiskBackend
# ======================================================================


class TestDiskBackend:
    """Filesystem-backed cache."""

    async def test_set_creates_file(self, tmp_path) -> None:
        cache_dir = tmp_path / "cache"
        cache = DiskBackend(cache_dir)
        await cache.set("test_key", {"data": 42}, CachePolicy(ttl_seconds=3600))
        # Check file exists
        files = list(cache_dir.iterdir())
        assert len(files) >= 1

    async def test_get_returns_value(self, tmp_path) -> None:
        cache = DiskBackend(tmp_path / "cache")
        await cache.set("key", "hello", CachePolicy(ttl_seconds=3600))
        entry = await cache.get("key")
        assert entry is not None
        assert entry.value == "hello"

    async def test_get_nonexistent(self, tmp_path) -> None:
        cache = DiskBackend(tmp_path / "cache")
        entry = await cache.get("nonexistent")
        assert entry is None

    async def test_delete_removes_file(self, tmp_path) -> None:
        cache = DiskBackend(tmp_path / "cache")
        await cache.set("key", "value", CachePolicy())
        assert await cache.delete("key") is True
        assert await cache.get("key") is None

    async def test_delete_nonexistent(self, tmp_path) -> None:
        cache = DiskBackend(tmp_path / "cache")
        assert await cache.delete("nonexistent") is False

    async def test_clear_removes_all(self, tmp_path) -> None:
        cache = DiskBackend(tmp_path / "cache")
        await cache.set("k1", "v1", CachePolicy())
        await cache.set("k2", "v2", CachePolicy())
        await cache.clear()
        assert await cache.get("k1") is None
        assert await cache.get("k2") is None

    async def test_evict_expired(self, tmp_path) -> None:
        cache = DiskBackend(tmp_path / "cache")
        await cache.set("expired", "old", CachePolicy(ttl_seconds=0))
        await cache.set("valid", "fresh", CachePolicy(ttl_seconds=3600))
        evicted = await cache.evict_expired()
        assert evicted >= 1
        assert await cache.get("expired") is None
        assert await cache.get("valid") is not None

    async def test_expired_entry_not_returned(self, tmp_path) -> None:
        cache = DiskBackend(tmp_path / "cache")
        await cache.set("stale", "old", CachePolicy(ttl_seconds=0))
        entry = await cache.get("stale")
        assert entry is None

    async def test_sanitise_key(self) -> None:
        """Key sanitisation replaces special chars."""
        sanitised = DiskBackend._sanitise_key("conv:abc123:queryhash")
        assert ":" not in sanitised
        assert sanitised.endswith(".json")

    async def test_long_key_hashed(self) -> None:
        """Very long keys are hashed."""
        long_key = "x" * 300
        sanitised = DiskBackend._sanitise_key(long_key)
        assert len(sanitised) < 100  # hashed to shorter length
        assert sanitised.endswith(".json")


# ======================================================================
# ConversationCache
# ======================================================================


class TestConversationCache:
    """Conversation-aware caching."""

    async def test_set_and_get(self) -> None:
        cache = ConversationCache()
        await cache.set("key", "value")
        result = await cache.get("key")
        assert result == "value"

    async def test_get_nonexistent(self) -> None:
        cache = ConversationCache()
        result = await cache.get("nonexistent")
        assert result is None

    async def test_ttl_expiry(self) -> None:
        cache = ConversationCache(default_ttl=0)  # immediate expiry
        await cache.set("key", "value")
        result = await cache.get("key")
        assert result is None

    async def test_clear_conversation(self) -> None:
        cache = ConversationCache()
        await cache.set("conv:abc123:hash1", "data1")
        await cache.set("conv:abc123:hash2", "data2")
        await cache.set("conv:xyz789:hash3", "data3")

        removed = await cache.clear_conversation("abc123")
        assert removed == 2
        assert await cache.get("conv:abc123:hash1") is None
        assert await cache.get("conv:abc123:hash2") is None
        assert await cache.get("conv:xyz789:hash3") == "data3"

    async def test_clear_conversation_no_matches(self) -> None:
        cache = ConversationCache()
        await cache.set("conv:abc:hash1", "data")
        removed = await cache.clear_conversation("nonexistent")
        assert removed == 0

    async def test_evict_expired(self) -> None:
        cache = ConversationCache()
        await cache.set("expired", "old", CachePolicy(ttl_seconds=0))
        await cache.set("valid", "fresh", CachePolicy(ttl_seconds=3600))
        evicted = await cache.evict_expired()
        assert evicted >= 1
        assert await cache.get("expired") is None
        assert await cache.get("valid") == "fresh"


# ======================================================================
# NISTCache
# ======================================================================


class TestNISTCache:
    """NIST-specific cache."""

    async def test_has_downloaded_unknown(self, tmp_path) -> None:
        from SciRetrieval.cache.cache_backend import DiskBackend
        cache = NISTCache(backend=DiskBackend(tmp_path / "nist_cache"))
        result = await cache.has_downloaded("dataset_123")
        assert result is False

    async def test_mark_downloaded(self, tmp_path) -> None:
        from SciRetrieval.cache.cache_backend import DiskBackend
        cache = NISTCache(backend=DiskBackend(tmp_path / "nist_cache"))
        await cache.mark_downloaded("dataset_123", {"name": "Test"})
        result = await cache.has_downloaded("dataset_123")
        assert result is True

    async def test_set_and_get(self, tmp_path) -> None:
        from SciRetrieval.cache.cache_backend import DiskBackend
        cache = NISTCache(backend=DiskBackend(tmp_path / "nist_cache"))
        await cache.set("compound_aspirin", {"data": "value"})
        result = await cache.get("compound_aspirin")
        assert result == {"data": "value"}

    async def test_default_ttl_is_7_days(self) -> None:
        cache = NISTCache()
        assert cache._default_ttl == 604800  # 7 days in seconds

    async def test_evict_expired(self, tmp_path) -> None:
        from SciRetrieval.cache.cache_backend import DiskBackend
        cache = NISTCache(backend=DiskBackend(tmp_path / "nist_cache"))
        await cache.set("expired", "old", CachePolicy(ttl_seconds=0))
        await cache.set("valid", "fresh", CachePolicy(ttl_seconds=3600))
        evicted = await cache.evict_expired()
        assert evicted >= 1
        assert await cache.get("expired") is None
        assert await cache.get("valid") == "fresh"
