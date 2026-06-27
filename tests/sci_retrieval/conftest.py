"""Shared fixtures and mock data for SciRetrieval tests."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from SciRetrieval.models import (
    CacheEntry,
    CachePolicy,
    EntityRelationship,
    EntityType,
    GetDataRequest,
    GetDataResponse,
    IntentDomainResult,
    ProvenanceEntry,
    RawProviderResult,
    RetrievalContext,
    SciLabResult,
    ScientificEntity,
)
from SciPhi.interfaces.model import ScientificDomain


# ======================================================================
# Model helpers
# ======================================================================


def make_entity(
    name: str = "TestEntity",
    entity_type: EntityType = EntityType.UNKNOWN,
    canonical_id: str = "",
    source: str = "",
    source_id: str = "",
    properties: dict | None = None,
    aliases: list[str] | None = None,
    confidence: float = 1.0,
    domain: ScientificDomain | None = None,
) -> ScientificEntity:
    """Factory helper to create ScientificEntity instances in tests."""
    return ScientificEntity(
        name=name,
        entity_type=entity_type,
        canonical_id=canonical_id,
        source=source,
        source_id=source_id,
        properties=properties or {},
        aliases=aliases or [],
        confidence=confidence,
        domain=domain,
    )


def make_raw_result(
    provider: str = "test_provider",
    raw_data: dict | None = None,
    metadata: dict | None = None,
) -> RawProviderResult:
    """Factory helper to create RawProviderResult instances."""
    return RawProviderResult(
        provider=provider,
        raw_data=raw_data or {"key": "value"},
        metadata=metadata or {},
    )


def make_context(
    query: str = "test query",
    domains: list[ScientificDomain] | None = None,
    conversation_id: str | None = None,
) -> RetrievalContext:
    """Factory helper to create RetrievalContext instances."""
    return RetrievalContext(
        query=query,
        domains=domains or [ScientificDomain.BIOLOGY],
        conversation_id=conversation_id,
    )


# ======================================================================
# Mock components
# ======================================================================


@pytest.fixture()
def mock_classifier() -> AsyncMock:
    """A mock IIntentDomainClassifier returning biology / generic."""
    m = AsyncMock()
    m.classify.return_value = IntentDomainResult(
        primary_domain=ScientificDomain.BIOLOGY,
        intent="generic",
        confidence=0.5,
    )
    return m


@pytest.fixture()
def mock_provider() -> MagicMock:
    """A mock IProvider for registry tests.

    Note: ``fetch`` is set as a regular attribute (not async) so that
    ``RetrievalManager._fetch_with_retry`` can call and await it.
    """
    m = MagicMock()
    m.provider_name = "mock_provider"
    m.supported_domains = frozenset({ScientificDomain.BIOLOGY})

    async def _fetch(ctx):
        return RawProviderResult(
            provider="mock_provider",
            raw_data={"result": "data"},
        )

    m.fetch = _fetch
    return m


@pytest.fixture()
def mock_provider_chem() -> MagicMock:
    """A mock chemistry provider."""
    m = MagicMock()
    m.provider_name = "chem_provider"
    m.supported_domains = frozenset({ScientificDomain.CHEMISTRY})

    async def _fetch(ctx):
        return RawProviderResult(
            provider="chem_provider",
            raw_data={"result": "data"},
        )

    m.fetch = _fetch
    return m


@pytest.fixture()
def mock_registry(mock_provider: MagicMock) -> MagicMock:
    """A mock ProviderRegistry."""
    m = MagicMock()
    m.get_providers.return_value = [mock_provider]
    m.find_by_name.return_value = mock_provider
    m.list_providers.return_value = {"mock_provider": ["BIOLOGY"]}
    return m


@pytest.fixture()
def mock_normalizer() -> AsyncMock:
    """A mock INormalizer."""
    m = AsyncMock()
    m.normalize.return_value = [
        make_entity(name="Result1", source="mock"),
        make_entity(name="Result2", source="mock"),
    ]
    return m


@pytest.fixture()
def mock_resolver() -> AsyncMock:
    """A mock IEntityResolver."""
    m = AsyncMock()
    m.resolve.side_effect = lambda entities: entities  # passthrough
    return m


@pytest.fixture()
def mock_scilab() -> AsyncMock:
    """A mock ISciLabProcessor."""
    m = AsyncMock()
    m.process.return_value = SciLabResult(
        summary="Mock scientific data.",
        entities=[],
        context="[SciRetrieval Context]\nMock data.",
        processing_time_ms=5.0,
    )
    return m


@pytest.fixture()
def mock_cache_manager() -> MagicMock:
    """A mock CacheManager with mock conversation and dataset caches."""
    m = MagicMock()
    m.conversation = AsyncMock()
    m.conversation.get.return_value = None
    m.dataset = AsyncMock()
    m.dataset.get.return_value = None
    m.persistent = AsyncMock()
    m.evict_expired_all = AsyncMock(return_value={"conversation": 0, "dataset": 0, "persistent": 0})
    m.clear_conversation = AsyncMock(return_value=3)
    return m


# ======================================================================
# Sample data
# ======================================================================


@pytest.fixture()
def sample_pubchem_json() -> dict[str, Any]:
    """Sample PubChem PC_Compounds JSON for normalizer tests."""
    return {
        "PC_Compounds": [
            {
                "id": {"id": {"CID": 2244}},
                "props": [
                    {
                        "urn": {"label": "IUPAC Name"},
                        "value": {"sval": "2-acetoxybenzoic acid"},
                    },
                    {
                        "urn": {"label": "Molecular Weight"},
                        "value": {"fval": 180.16},
                    },
                    {
                        "urn": {"label": "Molecular Formula"},
                        "value": {"sval": "C9H8O4"},
                    },
                    {
                        "urn": {"label": "Canonical SMILES"},
                        "value": {"sval": "CC(=O)OC1=CC=CC=C1C(=O)O"},
                    },
                    {
                        "urn": {"label": "InChIKey"},
                        "value": {"sval": "BSYNRYMUTXBXSQ-UHFFFAOYSA-N"},
                    },
                ],
            }
        ]
    }


@pytest.fixture()
def sample_ncbi_json() -> dict[str, Any]:
    """Sample NCBI esummary JSON for normalizer tests."""
    return {
        "result": {
            "7157": {
                "uid": "7157",
                "name": "TP53",
                "title": "tumor protein p53",
                "description": "The p53 tumor suppressor protein",
                "organism": "Homo sapiens",
                "summary": "Involved in cell cycle regulation",
                "otheraliases": "p53, tumor protein p53",
            }
        }
    }


@pytest.fixture()
def sample_nist_html() -> str:
    """Sample NIST WebBook HTML for normalizer tests."""
    return """
    <html>
    <head><title>Aspirin - NIST Chemistry WebBook</title></head>
    <body>
        <strong>Molecular Formula:</strong> C9H8O4<br>
        <strong>Molecular weight:</strong> 180.16 g/mol<br>
    </body>
    </html>
    """
