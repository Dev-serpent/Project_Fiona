"""SciRetrieval — Scientific Knowledge Retrieval subsystem.

Retrieves, normalises, resolves, and processes scientific data from
multiple online providers (NCBI, PubChem, NIST) into structured
:class:`ScientificEntity` objects.
"""

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
from SciRetrieval.errors import (
    CacheError,
    EntityResolutionError,
    NoProvidersAvailableError,
    NormalizationError,
    ProviderConnectionError,
    ProviderNotFoundError,
    ProviderRateLimitedError,
    ProviderTimeoutError,
    SciLabError,
    SciRetrievalError,
)
from SciRetrieval.router import Router
from SciRetrieval.provider_registry import ProviderRegistry
from SciRetrieval.normalizer import Normalizer
from SciRetrieval.entity_resolver import EntityResolver
from SciRetrieval.retrieval_manager import RetrievalManager
from SciRetrieval.cache_manager import CacheManager
from SciRetrieval.maintext_bridge import MainTextBridge

__all__ = [
    # Models
    "ScientificEntity",
    "SciLabResult",
    "EntityType",
    "EntityRelationship",
    "RetrievalContext",
    "RawProviderResult",
    "IntentDomainResult",
    "ProvenanceEntry",
    "GetDataRequest",
    "GetDataResponse",
    "CachePolicy",
    "CacheEntry",
    # Errors
    "SciRetrievalError",
    "ProviderNotFoundError",
    "NoProvidersAvailableError",
    "ProviderConnectionError",
    "ProviderTimeoutError",
    "ProviderRateLimitedError",
    "NormalizationError",
    "EntityResolutionError",
    "SciLabError",
    "CacheError",
    # Core components
    "Router",
    "ProviderRegistry",
    "Normalizer",
    "EntityResolver",
    "RetrievalManager",
    "CacheManager",
    "MainTextBridge",
]
