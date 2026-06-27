"""Dataclasses and enums for the SciRetrieval subsystem.

These types are the currency of the entire pipeline — every component
produces or consumes them.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from enum import Enum
from typing import Any

from SciPhi.interfaces.model import ScientificDomain


# ---------------------------------------------------------------------------
# Routing
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class IntentDomainResult:
    """Result of classifying a user query.

    Attributes:
        primary_domain: The highest-confidence scientific domain.
        secondary_domain: Optional second domain with a non-zero score.
        intent: Intent category (lookup, compare, explain, list, generic).
        confidence: Aggregate confidence score (0.0 – 1.0).
        matched_keywords: Keywords from the query that triggered matches.
    """

    primary_domain: ScientificDomain
    secondary_domain: ScientificDomain | None = None
    intent: str = "generic"
    confidence: float = 0.0
    matched_keywords: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class RetrievalContext:
    """Fully resolved context passed through the retrieval pipeline.

    Attributes:
        query: The original user query string.
        domains: Ordered list of domains to query (primary first).
        conversation_id: Optional conversation identifier for caching.
        options: Free-form options dict for extensibility.
    """

    query: str
    domains: list[ScientificDomain]
    conversation_id: str | None = None
    options: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Raw provider data
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RawProviderResult:
    """Unprocessed data returned by a single provider.

    Attributes:
        provider: Name of the provider that produced this data.
        raw_data: The raw response payload.
        metadata: Optional metadata about the request / response.
    """

    provider: str
    raw_data: dict[str, Any]
    metadata: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Entity types
# ---------------------------------------------------------------------------


class EntityType(Enum):
    """The kind of scientific entity."""

    CHEMICAL_COMPOUND = "chemical_compound"
    PROTEIN = "protein"
    GENE = "gene"
    DISEASE = "disease"
    PATHWAY = "pathway"
    REACTION = "reaction"
    PHYSICAL_PROPERTY = "physical_property"
    SPECTRUM = "spectrum"
    DATASET = "dataset"
    UNKNOWN = "unknown"


# ---------------------------------------------------------------------------
# Relationships & Provenance
# ---------------------------------------------------------------------------


@dataclass
class EntityRelationship:
    """A directed relationship between two entities.

    Attributes:
        source_id: Canonical identifier of the source entity.
        target_id: Canonical identifier of the target entity.
        relationship_type: Semantic type (e.g. "interacts_with", "catalyzes").
        confidence: Confidence in the relationship (0.0 – 1.0).
        evidence: Optional textual evidence or source citation.
    """

    source_id: str
    target_id: str
    relationship_type: str
    confidence: float = 1.0
    evidence: str | None = None


@dataclass
class ProvenanceEntry:
    """Tracks which provider contributed which fields to an entity.

    Attributes:
        provider: Name of the data provider.
        source_id: Identifier of the record in the source system.
        fields: List of property keys contributed by this provider.
        retrieved_at: ISO-format datetime of retrieval.
    """

    provider: str
    source_id: str
    fields: list[str] = field(default_factory=list)
    retrieved_at: str = ""


# ---------------------------------------------------------------------------
# Central entity type
# ---------------------------------------------------------------------------


@dataclass
class ScientificEntity:
    """Normalised, resolved scientific entity from one or more providers.

    This is the central currency type of the pipeline.  After normalisation
    and resolution every entity has a stable ``canonical_id`` and merged
    properties, aliases, relationships, and provenance.
    """

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    canonical_id: str = ""
    name: str = ""
    entity_type: EntityType = EntityType.UNKNOWN
    aliases: list[str] = field(default_factory=list)
    properties: dict[str, Any] = field(default_factory=dict)
    relationships: list[EntityRelationship] = field(default_factory=list)
    sources: list[ProvenanceEntry] = field(default_factory=list)
    confidence: float = 1.0
    domain: ScientificDomain | None = None
    # Shortcut fields (populated during normalisation):
    source: str = ""
    source_id: str = ""


# ---------------------------------------------------------------------------
# Pipeline output
# ---------------------------------------------------------------------------


@dataclass
class SciLabResult:
    """Final structured output of the retrieval + SciLab pipeline.

    Attributes:
        summary: Natural-language summary of the findings.
        entities: Processed, ranked, deduplicated entity list.
        relationships: Cross-entity relationships discovered.
        context: Structured context block suitable for LLM injection.
        processing_time_ms: Total wall-clock time for SciLab processing.
    """

    summary: str = ""
    entities: list[ScientificEntity] = field(default_factory=list)
    relationships: list[EntityRelationship] = field(default_factory=list)
    context: str = ""
    processing_time_ms: float = 0.0


# ---------------------------------------------------------------------------
# Caching
# ---------------------------------------------------------------------------


@dataclass
class CachePolicy:
    """Policy governing a single cache entry.

    Attributes:
        ttl_seconds: Time-to-live in seconds.
        persistent: If True, the entry should survive application restarts.
        max_size_bytes: Optional maximum serialised size for the value.
    """

    ttl_seconds: int = 300
    persistent: bool = False
    max_size_bytes: int | None = None


@dataclass
class CacheEntry:
    """A single entry stored in a cache backend.

    Attributes:
        key: Cache key.
        value: Arbitrary value (JSON-serialisable for persistent backends).
        policy: The policy that governs this entry.
        created_at: UTC datetime when the entry was created.
    """

    key: str
    value: Any
    policy: CachePolicy
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def is_expired(self) -> bool:
        """Check whether this entry has exceeded its TTL."""
        return datetime.now(timezone.utc) - self.created_at > timedelta(
            seconds=self.policy.ttl_seconds
        )


# ---------------------------------------------------------------------------
# Data request / response
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class GetDataRequest:
    """Request to retrieve data for a specific entity from a specific provider.

    Attributes:
        provider: Name of the target provider.
        entity: Entity identifier (name, CID, etc.).
        entity_type: Expected type hint for normalisation.
        options: Provider-specific options.
    """

    provider: str
    entity: str
    entity_type: EntityType = EntityType.UNKNOWN
    options: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class GetDataResponse:
    """Response for a single entity data request.

    Attributes:
        provider: Provider that handled the request.
        entity_key: The original entity identifier requested.
        entity: Resolved ScientificEntity if successful.
        raw_data: Unprocessed raw data from the provider.
        error: Error message if the request failed.
    """

    provider: str
    entity_key: str
    entity: ScientificEntity | None = None
    raw_data: dict[str, Any] = field(default_factory=dict)
    error: str | None = None
