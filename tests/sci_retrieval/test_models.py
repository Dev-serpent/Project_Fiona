"""Tests for SciRetrieval model dataclasses and enums.

Covers construction, field defaults, frozen-dataclass immutability,
and edge cases for every model type.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

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


class TestEntityType:
    """EntityType enum values."""

    def test_values(self) -> None:
        assert EntityType.CHEMICAL_COMPOUND.value == "chemical_compound"
        assert EntityType.PROTEIN.value == "protein"
        assert EntityType.GENE.value == "gene"
        assert EntityType.DISEASE.value == "disease"
        assert EntityType.PATHWAY.value == "pathway"
        assert EntityType.REACTION.value == "reaction"
        assert EntityType.PHYSICAL_PROPERTY.value == "physical_property"
        assert EntityType.SPECTRUM.value == "spectrum"
        assert EntityType.DATASET.value == "dataset"
        assert EntityType.UNKNOWN.value == "unknown"

    def test_unknown_is_default_for_new_entity(self) -> None:
        e = ScientificEntity()
        assert e.entity_type == EntityType.UNKNOWN


class TestIntentDomainResult:
    """IntentDomainResult construction and defaults."""

    def test_minimal_construction(self) -> None:
        result = IntentDomainResult(primary_domain=ScientificDomain.BIOLOGY)
        assert result.primary_domain == ScientificDomain.BIOLOGY
        assert result.secondary_domain is None
        assert result.intent == "generic"
        assert result.confidence == 0.0
        assert result.matched_keywords == []

    def test_full_construction(self) -> None:
        result = IntentDomainResult(
            primary_domain=ScientificDomain.CHEMISTRY,
            secondary_domain=ScientificDomain.PHYSICS,
            intent="lookup",
            confidence=0.85,
            matched_keywords=["compound", "molecule"],
        )
        assert result.primary_domain == ScientificDomain.CHEMISTRY
        assert result.secondary_domain == ScientificDomain.PHYSICS
        assert result.intent == "lookup"
        assert result.confidence == 0.85
        assert result.matched_keywords == ["compound", "molecule"]

    def test_is_frozen(self) -> None:
        result = IntentDomainResult(primary_domain=ScientificDomain.BIOLOGY)
        with pytest.raises(AttributeError):
            result.primary_domain = ScientificDomain.CHEMISTRY  # type: ignore[misc]


class TestRetrievalContext:
    """RetrievalContext construction and defaults."""

    def test_minimal(self) -> None:
        ctx = RetrievalContext(query="test", domains=[ScientificDomain.BIOLOGY])
        assert ctx.query == "test"
        assert ctx.domains == [ScientificDomain.BIOLOGY]
        assert ctx.conversation_id is None
        assert ctx.options == {}

    def test_with_conversation_id(self) -> None:
        ctx = RetrievalContext(
            query="what is aspirin",
            domains=[ScientificDomain.CHEMISTRY],
            conversation_id="conv_123",
        )
        assert ctx.conversation_id == "conv_123"

    def test_with_options(self) -> None:
        ctx = RetrievalContext(
            query="test",
            domains=[ScientificDomain.BIOLOGY],
            options={"intent": "lookup", "confidence": 0.9},
        )
        assert ctx.options["intent"] == "lookup"

    def test_is_frozen(self) -> None:
        ctx = RetrievalContext(query="test", domains=[ScientificDomain.BIOLOGY])
        with pytest.raises(AttributeError):
            ctx.query = "changed"  # type: ignore[misc]


class TestRawProviderResult:
    """RawProviderResult construction."""

    def test_minimal(self) -> None:
        raw = RawProviderResult(provider="ncbi", raw_data={"result": {}})
        assert raw.provider == "ncbi"
        assert raw.raw_data == {"result": {}}
        assert raw.metadata == {}

    def test_with_metadata(self) -> None:
        raw = RawProviderResult(
            provider="pubchem",
            raw_data={"PC_Compounds": []},
            metadata={"database": "compound"},
        )
        assert raw.metadata["database"] == "compound"

    def test_is_frozen(self) -> None:
        raw = RawProviderResult(provider="ncbi", raw_data={})
        with pytest.raises(AttributeError):
            raw.provider = "pubchem"  # type: ignore[misc]


class TestScientificEntity:
    """ScientificEntity — the central currency type."""

    def test_minimal(self) -> None:
        e = ScientificEntity()
        assert isinstance(e.id, str)
        assert len(e.id) > 0
        assert e.name == ""
        assert e.entity_type == EntityType.UNKNOWN
        assert e.aliases == []
        assert e.properties == {}
        assert e.relationships == []
        assert e.sources == []
        assert e.confidence == 1.0
        assert e.domain is None

    def test_with_all_fields(self) -> None:
        rel = EntityRelationship(
            source_id="src1", target_id="tgt1", relationship_type="interacts_with"
        )
        prov = ProvenanceEntry(
            provider="pubchem", source_id="2244", fields=["mw", "mf"]
        )
        e = ScientificEntity(
            id="my-id",
            canonical_id="pubchem:2244",
            name="Aspirin",
            entity_type=EntityType.CHEMICAL_COMPOUND,
            aliases=["ASA", "acetylsalicylic acid"],
            properties={"mw": 180.16, "mf": "C9H8O4"},
            relationships=[rel],
            sources=[prov],
            confidence=0.95,
            domain=ScientificDomain.CHEMISTRY,
        )
        assert e.id == "my-id"
        assert e.canonical_id == "pubchem:2244"
        assert e.name == "Aspirin"
        assert e.entity_type == EntityType.CHEMICAL_COMPOUND
        assert len(e.aliases) == 2
        assert e.properties["mw"] == 180.16
        assert len(e.relationships) == 1
        assert len(e.sources) == 1
        assert e.confidence == 0.95
        assert e.domain == ScientificDomain.CHEMISTRY

    def test_empty_name(self) -> None:
        e = ScientificEntity(name="")
        assert e.name == ""

    def test_mutable_not_frozen(self) -> None:
        e = ScientificEntity()
        e.name = "Updated"
        e.properties["new_key"] = "new_value"
        assert e.name == "Updated"
        assert e.properties["new_key"] == "new_value"


class TestEntityRelationship:
    """EntityRelationship construction."""

    def test_minimal(self) -> None:
        rel = EntityRelationship(
            source_id="A", target_id="B", relationship_type="binds"
        )
        assert rel.source_id == "A"
        assert rel.target_id == "B"
        assert rel.relationship_type == "binds"
        assert rel.confidence == 1.0
        assert rel.evidence is None

    def test_full(self) -> None:
        rel = EntityRelationship(
            source_id="A",
            target_id="B",
            relationship_type="catalyzes",
            confidence=0.8,
            evidence="PMID:12345",
        )
        assert rel.evidence == "PMID:12345"
        assert rel.confidence == 0.8


class TestProvenanceEntry:
    """ProvenanceEntry construction."""

    def test_defaults(self) -> None:
        p = ProvenanceEntry(provider="ncbi", source_id="7157")
        assert p.fields == []
        assert p.retrieved_at == ""

    def test_full(self) -> None:
        p = ProvenanceEntry(
            provider="pubchem",
            source_id="2244",
            fields=["mw", "mf", "smiles"],
            retrieved_at="2024-01-01T00:00:00Z",
        )
        assert len(p.fields) == 3


class TestSciLabResult:
    """SciLabResult pipeline output."""

    def test_defaults(self) -> None:
        r = SciLabResult()
        assert r.summary == ""
        assert r.entities == []
        assert r.relationships == []
        assert r.context == ""
        assert r.processing_time_ms == 0.0

    def test_full(self) -> None:
        e = ScientificEntity(name="Result")
        r = SciLabResult(
            summary="Found results.",
            entities=[e],
            context="[SciRetrieval Context]",
            processing_time_ms=12.5,
        )
        assert r.summary == "Found results."
        assert len(r.entities) == 1
        assert r.processing_time_ms == 12.5


class TestCachePolicy:
    """CachePolicy defaults."""

    def test_defaults(self) -> None:
        p = CachePolicy()
        assert p.ttl_seconds == 300
        assert p.persistent is False
        assert p.max_size_bytes is None

    def test_custom(self) -> None:
        p = CachePolicy(ttl_seconds=86400, persistent=True, max_size_bytes=1024)
        assert p.ttl_seconds == 86400
        assert p.persistent is True
        assert p.max_size_bytes == 1024


class TestCacheEntry:
    """CacheEntry with expiration logic."""

    def test_default_created_at_is_utc(self) -> None:
        entry = CacheEntry(key="k", value="v", policy=CachePolicy())
        assert entry.created_at.tzinfo is not None

    def test_not_expired_when_fresh(self) -> None:
        policy = CachePolicy(ttl_seconds=3600)
        entry = CacheEntry(key="k", value="v", policy=policy)
        assert not entry.is_expired

    def test_expired_when_ttl_past(self) -> None:
        policy = CachePolicy(ttl_seconds=0)  # 0-second TTL = immediate expiry
        entry = CacheEntry(key="k", value="v", policy=policy)
        assert entry.is_expired

    def test_not_expired_with_future_created_at(self) -> None:
        policy = CachePolicy(ttl_seconds=300)
        future = datetime.now(timezone.utc) + timedelta(hours=1)
        entry = CacheEntry(key="k", value="v", policy=policy, created_at=future)
        assert not entry.is_expired


class TestGetDataRequest:
    """GetDataRequest construction."""

    def test_minimal(self) -> None:
        req = GetDataRequest(provider="pubchem", entity="aspirin")
        assert req.provider == "pubchem"
        assert req.entity == "aspirin"
        assert req.entity_type == EntityType.UNKNOWN
        assert req.options == {}

    def test_full(self) -> None:
        req = GetDataRequest(
            provider="ncbi",
            entity="TP53",
            entity_type=EntityType.PROTEIN,
            options={"fields": ["summary"]},
        )
        assert req.entity_type == EntityType.PROTEIN
        assert req.options["fields"] == ["summary"]

    def test_is_frozen(self) -> None:
        req = GetDataRequest(provider="pubchem", entity="aspirin")
        with pytest.raises(AttributeError):
            req.provider = "ncbi"  # type: ignore[misc]


class TestGetDataResponse:
    """GetDataResponse construction."""

    def test_minimal(self) -> None:
        resp = GetDataResponse(provider="pubchem", entity_key="aspirin")
        assert resp.provider == "pubchem"
        assert resp.entity_key == "aspirin"
        assert resp.entity is None
        assert resp.raw_data == {}
        assert resp.error is None

    def test_with_error(self) -> None:
        resp = GetDataResponse(
            provider="ncbi",
            entity_key="TP53",
            error="Provider not found",
        )
        assert resp.error == "Provider not found"
        assert resp.entity is None

    def test_with_entity(self) -> None:
        e = ScientificEntity(name="Aspirin")
        resp = GetDataResponse(
            provider="pubchem",
            entity_key="aspirin",
            entity=e,
            raw_data={"foo": "bar"},
        )
        assert resp.entity is not None
        assert resp.entity.name == "Aspirin"
        assert resp.raw_data == {"foo": "bar"}

    def test_is_frozen(self) -> None:
        resp = GetDataResponse(provider="pubchem", entity_key="aspirin")
        with pytest.raises(AttributeError):
            resp.provider = "ncbi"  # type: ignore[misc]
