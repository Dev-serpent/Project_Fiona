"""Error hierarchy for the SciRetrieval subsystem.

All custom exceptions derive from a common base so callers can catch
SciRetrievalError at the top level if they choose.
"""


class SciRetrievalError(Exception):
    """Base exception for all SciRetrieval failures."""


class ClassificationError(SciRetrievalError):
    """Query could not be classified into a domain or intent."""


class UnknownDomainError(ClassificationError):
    """No known domain matched the query."""


class ProviderError(SciRetrievalError):
    """Base exception for provider-level failures."""


class ProviderNotFoundError(ProviderError):
    """The requested provider is not registered."""


class ProviderConnectionError(ProviderError):
    """Failed to connect to the provider endpoint."""


class ProviderTimeoutError(ProviderError):
    """The provider request exceeded the timeout."""


class ProviderDataError(ProviderError):
    """The provider returned unexpected or malformed data."""


class ProviderRateLimitedError(ProviderError):
    """The provider returned a 429 Too Many Requests response."""


class NormalizationError(SciRetrievalError):
    """Failed to normalise raw provider data into ScientificEntity objects."""


class EntityResolutionError(SciRetrievalError):
    """Failed during entity resolution or cross-provider merging."""


class SciLabError(SciRetrievalError):
    """Base exception for SciLab processing pipeline failures."""


class SciLabParseError(SciLabError):
    """Failed to parse entity properties during SciLab processing."""


class CacheError(SciRetrievalError):
    """Base exception for cache-layer failures."""


class CacheCorruptionError(CacheError):
    """A cache entry could not be deserialised or is corrupt."""


class CacheFullError(CacheError):
    """The cache backend has reached its storage limit."""


class RetrievalManagerError(SciRetrievalError):
    """Base exception for RetrievalManager orchestration failures."""


class NoProvidersAvailableError(RetrievalManagerError):
    """No providers could be found for the requested domain(s)."""
