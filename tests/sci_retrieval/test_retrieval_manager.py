"""Tests for RetrievalManager — full pipeline orchestration.

Uses mocked components to verify the pipeline stages execute in
correct order, caching works, and graceful degradation on failures.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

pytestmark = pytest.mark.asyncio

from SciRetrieval.models import (
    CacheEntry,
    CachePolicy,
    GetDataRequest,
    GetDataResponse,
    IntentDomainResult,
    RawProviderResult,
    RetrievalContext,
    SciLabResult,
    ScientificEntity,
)
from SciRetrieval.retrieval_manager import RetrievalManager
from SciRetrieval.errors import (
    NoProvidersAvailableError,
    ProviderNotFoundError,
)
from SciPhi.interfaces.model import ScientificDomain


# ======================================================================
# Fixtures
# ======================================================================


@pytest.fixture()
def empty_registry() -> MagicMock:
    """Registry with no providers registered."""
    m = MagicMock()
    m.get_providers.return_value = []
    m.find_by_name.return_value = None
    return m


@pytest.fixture()
def manager(
    mock_classifier: AsyncMock,
    mock_registry: MagicMock,
    mock_normalizer: AsyncMock,
    mock_resolver: AsyncMock,
    mock_scilab: AsyncMock,
    mock_cache_manager: MagicMock,
) -> RetrievalManager:
    return RetrievalManager(
        classifier=mock_classifier,
        registry=mock_registry,
        normalizer=mock_normalizer,
        resolver=mock_resolver,
        scilab=mock_scilab,
        cache_manager=mock_cache_manager,
    )


@pytest.fixture()
def sample_provider() -> MagicMock:
    m = MagicMock()
    m.provider_name = "test_provider"
    m.supported_domains = frozenset({ScientificDomain.BIOLOGY})
    m.fetch = AsyncMock(
        return_value=RawProviderResult(
            provider="test_provider",
            raw_data={"result": "data"},
            metadata={"key": "value"},
        )
    )
    return m


# ======================================================================
# Pipeline orchestration
# ======================================================================


class TestRetrieve:
    """Full retrieve() pipeline."""

    async def test_retrieve_calls_all_stages(
        self,
        manager: RetrievalManager,
        mock_classifier: AsyncMock,
        mock_normalizer: AsyncMock,
        mock_resolver: AsyncMock,
        mock_scilab: AsyncMock,
    ) -> None:
        result = await manager.retrieve("test query")

        # Each stage should have been called
        mock_classifier.classify.assert_awaited_once_with("test query")
        mock_normalizer.normalize.assert_awaited()
        mock_resolver.resolve.assert_awaited()
        mock_scilab.process.assert_awaited()

        # Should return a SciLabResult
        assert isinstance(result, SciLabResult)

    async def test_retrieve_with_conversation_id(
        self,
        manager: RetrievalManager,
        mock_cache_manager: MagicMock,
    ) -> None:
        result = await manager.retrieve("test query", conversation_id="conv_123")

        # Cache should be checked
        mock_cache_manager.conversation.get.assert_awaited()

        # Result should be stored in cache
        mock_cache_manager.conversation.set.assert_awaited()

    async def test_cache_hit_returns_without_calling_providers(
        self,
        manager: RetrievalManager,
        mock_cache_manager: MagicMock,
        mock_classifier: AsyncMock,
        mock_normalizer: AsyncMock,
    ) -> None:
        """Cache hit returns cached SciLabResult without invoking providers."""
        cached_result = SciLabResult(
            summary="Cached result",
            entities=[ScientificEntity(name="Cached")],
        )
        mock_cache_manager.conversation.get.return_value = CacheEntry(
            key="cache_key",
            value=cached_result,
            policy=CachePolicy(ttl_seconds=300),
        )

        result = await manager.retrieve("test query", conversation_id="conv_123")

        assert result.summary == "Cached result"
        # Classifier should NOT be called (full pipeline skipped)
        mock_classifier.classify.assert_not_awaited()
        mock_normalizer.normalize.assert_not_awaited()

    async def test_cache_miss_runs_full_pipeline(
        self,
        manager: RetrievalManager,
        mock_cache_manager: MagicMock,
        mock_classifier: AsyncMock,
    ) -> None:
        mock_cache_manager.conversation.get.return_value = None  # cache miss
        await manager.retrieve("test query", conversation_id="conv_123")
        mock_classifier.classify.assert_awaited_once()

    async def test_no_providers_available_error(
        self,
        mock_classifier: AsyncMock,
        empty_registry: MagicMock,
        mock_normalizer: AsyncMock,
        mock_resolver: AsyncMock,
        mock_scilab: AsyncMock,
        mock_cache_manager: MagicMock,
    ) -> None:
        mgr = RetrievalManager(
            classifier=mock_classifier,
            registry=empty_registry,
            normalizer=mock_normalizer,
            resolver=mock_resolver,
            scilab=mock_scilab,
            cache_manager=mock_cache_manager,
        )
        with pytest.raises(NoProvidersAvailableError):
            await mgr.retrieve("test query")


class TestGracefulDegradation:
    """RetrievalManager handles partial failures gracefully."""

    async def test_one_provider_fails_partial_results(
        self,
        mock_classifier: AsyncMock,
        mock_registry: MagicMock,
        mock_normalizer: AsyncMock,
        mock_resolver: AsyncMock,
        mock_scilab: AsyncMock,
        mock_cache_manager: MagicMock,
    ) -> None:
        """One provider fails, another succeeds — partial results returned."""
        # Two providers: one fails, one succeeds
        failing_provider = MagicMock()
        failing_provider.provider_name = "failing"
        failing_provider.supported_domains = frozenset({ScientificDomain.BIOLOGY})
        failing_provider.fetch = AsyncMock(
            side_effect=RuntimeError("Provider failed")
        )

        working_provider = MagicMock()
        working_provider.provider_name = "working"
        working_provider.supported_domains = frozenset({ScientificDomain.BIOLOGY})
        working_provider.fetch = AsyncMock(
            return_value=RawProviderResult(
                provider="working",
                raw_data={"result": "data"},
            )
        )

        # Registry returns both
        mock_registry.get_providers.return_value = [failing_provider, working_provider]

        # Normalizer returns entities from working provider
        mock_normalizer.normalize.return_value = [
            ScientificEntity(name="WorkingResult", source="working")
        ]

        mgr = RetrievalManager(
            classifier=mock_classifier,
            registry=mock_registry,
            normalizer=mock_normalizer,
            resolver=mock_resolver,
            scilab=mock_scilab,
            cache_manager=mock_cache_manager,
        )

        result = await mgr.retrieve("test query")
        assert isinstance(result, SciLabResult)
        # Working provider should have been called
        working_provider.fetch.assert_awaited()

    async def test_normalization_failure_continues(
        self,
        manager: RetrievalManager,
        mock_normalizer: AsyncMock,
    ) -> None:
        """If normalizer fails for one provider, others still processed."""
        mock_normalizer.normalize.side_effect = [
            [ScientificEntity(name="Good")],  # first call succeeds
        ]
        result = await manager.retrieve("test query")
        # Should still return a result
        assert isinstance(result, SciLabResult)

    async def test_resolver_failure_falls_back(
        self,
        manager: RetrievalManager,
        mock_resolver: AsyncMock,
    ) -> None:
        """Resolver failure falls back to un-resolved entities."""
        mock_resolver.resolve.side_effect = RuntimeError("Resolver crashed")
        result = await manager.retrieve("test query")
        # Should still return a result (graceful degradation)
        assert isinstance(result, SciLabResult)


# ======================================================================
# GetData
# ======================================================================


class TestGetData:
    """get_data() method for direct provider lookups."""

    async def test_get_data_finds_provider_and_returns(
        self,
        manager: RetrievalManager,
        mock_registry: MagicMock,
        mock_provider: MagicMock,
    ) -> None:
        mock_provider.fetch = AsyncMock(
            return_value=RawProviderResult(
                provider="mock_provider",
                raw_data={"result": "data"},
            )
        )
        mock_registry.find_by_name.return_value = mock_provider
        mock_registry.get_providers.return_value = [mock_provider]

        request = GetDataRequest(provider="mock_provider", entity="test_entity")
        response = await manager.get_data(request)

        assert isinstance(response, GetDataResponse)
        assert response.provider == "mock_provider"
        assert response.error is None
        assert response.entity is not None

    async def test_get_data_unknown_provider(
        self,
        manager: RetrievalManager,
        mock_registry: MagicMock,
    ) -> None:
        mock_registry.find_by_name.return_value = None
        request = GetDataRequest(provider="unknown", entity="test")
        response = await manager.get_data(request)
        assert response.error is not None
        assert "not found" in response.error.lower() or "unknown" in response.error.lower()

    async def test_get_data_cache_hit(
        self,
        manager: RetrievalManager,
        mock_cache_manager: MagicMock,
    ) -> None:
        cached_response = GetDataResponse(
            provider="pubchem",
            entity_key="aspirin",
            entity=ScientificEntity(name="Aspirin"),
        )
        mock_cache_manager.dataset.get.return_value = CacheEntry(
            key="dataset_key",
            value=cached_response,
            policy=CachePolicy(ttl_seconds=86400),
        )

        request = GetDataRequest(provider="pubchem", entity="aspirin")
        response = await manager.get_data(request)
        assert response.entity is not None
        assert response.entity.name == "Aspirin"

    async def test_get_data_provider_returns_error(
        self,
        manager: RetrievalManager,
        mock_registry: MagicMock,
        mock_provider: MagicMock,
    ) -> None:
        mock_provider.fetch = AsyncMock(
            side_effect=RuntimeError("Provider error")
        )
        mock_registry.find_by_name.return_value = mock_provider

        request = GetDataRequest(provider="mock_provider", entity="test")
        response = await manager.get_data(request)
        assert response.error is not None

    async def test_get_data_no_data_from_provider(
        self,
        manager: RetrievalManager,
        mock_registry: MagicMock,
        mock_provider: MagicMock,
    ) -> None:
        mock_provider.fetch = AsyncMock(return_value=None)
        mock_registry.find_by_name.return_value = mock_provider

        request = GetDataRequest(provider="mock_provider", entity="test")
        response = await manager.get_data(request)
        assert response.error is not None or response.entity is None
