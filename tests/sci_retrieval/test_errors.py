"""Tests for the SciRetrieval error hierarchy.

Verifies that all 16 exception classes can be raised, caught, and
that the inheritance hierarchy is correct.
"""

from __future__ import annotations

import pytest

from SciRetrieval.errors import (
    CacheCorruptionError,
    CacheError,
    CacheFullError,
    ClassificationError,
    EntityResolutionError,
    NoProvidersAvailableError,
    NormalizationError,
    ProviderConnectionError,
    ProviderDataError,
    ProviderError,
    ProviderNotFoundError,
    ProviderRateLimitedError,
    ProviderTimeoutError,
    RetrievalManagerError,
    SciLabError,
    SciLabParseError,
    SciRetrievalError,
)


def test_sci_retrieval_error_is_base() -> None:
    """SciRetrievalError is the root of the hierarchy."""
    assert issubclass(ClassificationError, SciRetrievalError)
    assert issubclass(ProviderError, SciRetrievalError)
    assert issubclass(NormalizationError, SciRetrievalError)
    assert issubclass(EntityResolutionError, SciRetrievalError)
    assert issubclass(SciLabError, SciRetrievalError)
    assert issubclass(CacheError, SciRetrievalError)
    assert issubclass(RetrievalManagerError, SciRetrievalError)


class TestClassificationErrors:
    """ClassificationError and UnknownDomainError."""

    def test_classification_error(self) -> None:
        with pytest.raises(ClassificationError):
            raise ClassificationError("Could not classify")

    def test_classification_error_message(self) -> None:
        try:
            raise ClassificationError("custom message")
        except ClassificationError as e:
            assert "custom message" in str(e)


class TestProviderErrors:
    """ProviderError hierarchy — all 6 classes."""

    def test_provider_error_base(self) -> None:
        with pytest.raises(ProviderError):
            raise ProviderError("Provider failure")

    def test_provider_not_found(self) -> None:
        with pytest.raises(ProviderNotFoundError):
            raise ProviderNotFoundError("Provider 'foo' not registered")
        assert issubclass(ProviderNotFoundError, ProviderError)

    def test_provider_connection_error(self) -> None:
        with pytest.raises(ProviderConnectionError):
            raise ProviderConnectionError("Failed to connect")
        assert issubclass(ProviderConnectionError, ProviderError)

    def test_provider_timeout_error(self) -> None:
        with pytest.raises(ProviderTimeoutError):
            raise ProviderTimeoutError("Request timed out")
        assert issubclass(ProviderTimeoutError, ProviderError)

    def test_provider_data_error(self) -> None:
        with pytest.raises(ProviderDataError):
            raise ProviderDataError("Unexpected data format")
        assert issubclass(ProviderDataError, ProviderError)

    def test_provider_rate_limited_error(self) -> None:
        with pytest.raises(ProviderRateLimitedError):
            raise ProviderRateLimitedError("Rate limited (429)")
        assert issubclass(ProviderRateLimitedError, ProviderError)

    def test_hierarchy_chaining(self) -> None:
        """ProviderConnectionError is a ProviderError is a SciRetrievalError."""
        try:
            raise ProviderConnectionError("Connection lost")
        except SciRetrievalError:
            pass  # caught at top level
        except Exception:
            pytest.fail("ProviderConnectionError should be catchable as SciRetrievalError")


class TestNormalizationError:
    """NormalizationError."""

    def test_normalization_error(self) -> None:
        with pytest.raises(NormalizationError):
            raise NormalizationError("Failed to parse")
        assert issubclass(NormalizationError, SciRetrievalError)


class TestEntityResolutionError:
    """EntityResolutionError."""

    def test_entity_resolution_error(self) -> None:
        with pytest.raises(EntityResolutionError):
            raise EntityResolutionError("Synonym merge failed")
        assert issubclass(EntityResolutionError, SciRetrievalError)


class TestSciLabErrors:
    """SciLabError and SciLabParseError."""

    def test_scilab_error(self) -> None:
        with pytest.raises(SciLabError):
            raise SciLabError("SciLab processing failed")
        assert issubclass(SciLabError, SciRetrievalError)

    def test_scilab_parse_error(self) -> None:
        with pytest.raises(SciLabParseError):
            raise SciLabParseError("Failed to parse entity")
        assert issubclass(SciLabParseError, SciLabError)

    def test_scilab_parse_is_scilab(self) -> None:
        try:
            raise SciLabParseError("Parse failure")
        except SciLabError:
            pass  # caught as SciLabError


class TestCacheErrors:
    """CacheError, CacheCorruptionError, CacheFullError."""

    def test_cache_error(self) -> None:
        with pytest.raises(CacheError):
            raise CacheError("Cache failure")
        assert issubclass(CacheError, SciRetrievalError)

    def test_cache_corruption_error(self) -> None:
        with pytest.raises(CacheCorruptionError):
            raise CacheCorruptionError("Corrupt entry")
        assert issubclass(CacheCorruptionError, CacheError)

    def test_cache_full_error(self) -> None:
        with pytest.raises(CacheFullError):
            raise CacheFullError("Cache is full")
        assert issubclass(CacheFullError, CacheError)


class TestRetrievalManagerErrors:
    """RetrievalManagerError and NoProvidersAvailableError."""

    def test_retrieval_manager_error(self) -> None:
        with pytest.raises(RetrievalManagerError):
            raise RetrievalManagerError("Orchestration failure")
        assert issubclass(RetrievalManagerError, SciRetrievalError)

    def test_no_providers_available_error(self) -> None:
        with pytest.raises(NoProvidersAvailableError):
            raise NoProvidersAvailableError("No providers found")
        assert issubclass(NoProvidersAvailableError, RetrievalManagerError)


class TestExceptionMessage:
    """All exception classes propagate messages correctly."""

    @pytest.mark.parametrize(
        "exc_class, message",
        [
            (SciRetrievalError, "base error"),
            (ClassificationError, "classification failed"),
            (ProviderError, "provider error"),
            (ProviderNotFoundError, "not found"),
            (ProviderConnectionError, "connection failed"),
            (ProviderTimeoutError, "timeout"),
            (ProviderDataError, "bad data"),
            (ProviderRateLimitedError, "rate limited"),
            (NormalizationError, "normalization failed"),
            (EntityResolutionError, "resolution failed"),
            (SciLabError, "scilab error"),
            (SciLabParseError, "parse error"),
            (CacheError, "cache error"),
            (CacheCorruptionError, "corruption"),
            (CacheFullError, "full"),
            (RetrievalManagerError, "manager error"),
            (NoProvidersAvailableError, "no providers"),
        ],
    )
    def test_message_propagation(self, exc_class: type, message: str) -> None:
        try:
            raise exc_class(message)
        except exc_class as e:
            assert message in str(e)


class TestExceptionChaining:
    """Exceptions can be chained with 'from'."""

    def test_chaining(self) -> None:
        try:
            try:
                raise ValueError("original cause")
            except ValueError as cause:
                raise ProviderConnectionError("wrapped") from cause
        except ProviderConnectionError as e:
            assert e.__cause__ is not None
            assert isinstance(e.__cause__, ValueError)
