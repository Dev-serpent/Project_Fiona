"""Tests for data providers — NCBI, PubChem, NIST.

Uses ``unittest.mock.patch`` to mock HTTP calls at the ``_get`` /
``_get_text`` method level so no network access is needed.
If ``aiohttp`` is not installed these tests will be skipped.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from SciRetrieval.models import RawProviderResult, RetrievalContext
from SciPhi.interfaces.model import ScientificDomain

# ======================================================================
# Conditional import — skip all tests if aiohttp is missing
# ======================================================================

try:
    from SciRetrieval.providers.ncbi import NCBIProvider
    from SciRetrieval.providers.pubchem import PubChemProvider
    from SciRetrieval.providers.nist import NISTProvider
    from SciRetrieval.providers.base import BaseProvider
    from SciRetrieval.errors import (
        ProviderConnectionError,
        ProviderTimeoutError,
        ProviderRateLimitedError,
        ProviderDataError,
    )

    HAS_AIOHTTP = True
except ImportError:
    HAS_AIOHTTP = False


pytestmark = [
    pytest.mark.skipif(not HAS_AIOHTTP, reason="aiohttp not installed"),
    pytest.mark.asyncio,
]


# ======================================================================
# Helpers
# ======================================================================


@pytest.fixture()
def ctx_biology() -> RetrievalContext:
    return RetrievalContext(
        query="BRCA1 gene",
        domains=[ScientificDomain.BIOLOGY],
    )


@pytest.fixture()
def ctx_chemistry() -> RetrievalContext:
    return RetrievalContext(
        query="aspirin",
        domains=[ScientificDomain.CHEMISTRY],
    )


@pytest.fixture()
def ctx_physics() -> RetrievalContext:
    return RetrievalContext(
        query="speed of light",
        domains=[ScientificDomain.PHYSICS],
    )


# ======================================================================
# NCBIProvider tests
# ======================================================================


class TestNCBIProvider:
    """NCBI E-utilities provider with mocked _get."""

    async def test_fetch_returns_raw_result(self, ctx_biology: RetrievalContext) -> None:
        provider = NCBIProvider()
        provider._get = AsyncMock(  # type: ignore[method-assign]
            side_effect=[
                # First call: esearch
                {"esearchresult": {"idlist": ["7157", "672"], "count": "2"}},
                # Second call: esummary
                {
                    "result": {
                        "7157": {"uid": "7157", "name": "TP53", "description": "Tumor protein p53"},
                        "672": {"uid": "672", "name": "BRCA1", "description": "Breast cancer type 1"},
                    }
                },
            ]
        )
        result = await provider.fetch(ctx_biology)
        assert isinstance(result, RawProviderResult)
        assert result.provider == "ncbi"
        assert "result" in result.raw_data
        assert "database" in result.metadata
        assert len(result.metadata["ids"]) == 2

    async def test_empty_search_results(self, ctx_biology: RetrievalContext) -> None:
        provider = NCBIProvider()
        provider._get = AsyncMock(  # type: ignore[method-assign]
            return_value={"esearchresult": {"idlist": [], "count": "0"}}
        )
        result = await provider.fetch(ctx_biology)
        assert result.provider == "ncbi"
        assert result.metadata["ids"] == []

    async def test_http_429_raises_rate_limited(self, ctx_biology: RetrievalContext) -> None:
        provider = NCBIProvider()
        provider._get = AsyncMock(  # type: ignore[method-assign]
            side_effect=ProviderRateLimitedError("Rate limited by ncbi (429)")
        )
        with pytest.raises(ProviderRateLimitedError):
            await provider.fetch(ctx_biology)

    async def test_provider_name(self) -> None:
        provider = NCBIProvider()
        assert provider.provider_name == "ncbi"

    async def test_supported_domains(self) -> None:
        provider = NCBIProvider()
        assert ScientificDomain.BIOLOGY in provider.supported_domains
        assert ScientificDomain.CHEMISTRY in provider.supported_domains
        assert ScientificDomain.PHYSICS not in provider.supported_domains


# ======================================================================
# PubChemProvider tests
# ======================================================================


class TestPubChemProvider:
    """PubChem PUG REST provider with mocked _get."""

    async def test_fetch_by_name(self, ctx_chemistry: RetrievalContext) -> None:
        provider = PubChemProvider()
        provider._get = AsyncMock(  # type: ignore[method-assign]
            return_value={
                "PC_Compounds": [
                    {
                        "id": {"id": {"CID": 2244}},
                        "props": [{"urn": {"label": "Molecular Weight"}, "value": {"fval": 180.16}}],
                    }
                ]
            }
        )
        result = await provider.fetch(ctx_chemistry)
        assert result.provider == "pubchem"
        assert "PC_Compounds" in result.raw_data

    async def test_fetch_by_cid(self) -> None:
        ctx = RetrievalContext(query="2244", domains=[ScientificDomain.CHEMISTRY])
        provider = PubChemProvider()
        provider._get = AsyncMock(  # type: ignore[method-assign]
            return_value={"PC_Compounds": [{"id": {"id": {"CID": 2244}}}]}
        )
        result = await provider.fetch(ctx)
        assert result.metadata["id_type"] == "cid"
        assert result.metadata["identifier"] == "2244"

    async def test_fallback_on_first_failure(self, ctx_chemistry: RetrievalContext) -> None:
        """When first call fails, fallback to name search is attempted."""
        provider = PubChemProvider()
        # First call raises, second succeeds
        provider._get = AsyncMock(  # type: ignore[method-assign]
            side_effect=[
                ProviderConnectionError("First call failed"),
                {"PC_Compounds": [{"id": {"id": {"CID": 2244}}}]},
            ]
        )
        result = await provider.fetch(ctx_chemistry)
        assert result.provider == "pubchem"
        assert "PC_Compounds" in result.raw_data

    async def test_http_429_raises_rate_limited(self, ctx_chemistry: RetrievalContext) -> None:
        provider = PubChemProvider()
        provider._get = AsyncMock(  # type: ignore[method-assign]
            side_effect=ProviderRateLimitedError("Rate limited by pubchem (429)")
        )
        with pytest.raises(ProviderRateLimitedError):
            await provider.fetch(ctx_chemistry)

    async def test_supported_domains(self) -> None:
        provider = PubChemProvider()
        assert ScientificDomain.CHEMISTRY in provider.supported_domains
        assert ScientificDomain.BIOLOGY in provider.supported_domains

    def test_parse_identifier_cid(self) -> None:
        """CID detection."""
        provider = PubChemProvider()
        assert provider._parse_identifier("2244") == ("cid", "2244")
        assert provider._parse_identifier("CID:2244") == ("cid", "2244")
        assert provider._parse_identifier("pubchem:2244") == ("cid", "2244")

    def test_parse_identifier_smiles(self) -> None:
        """SMILES heuristic."""
        provider = PubChemProvider()
        id_type, ident = provider._parse_identifier("C1=CC=CC=C1")
        assert id_type == "smiles"
        assert ident == "C1=CC=CC=C1"

    def test_parse_identifier_name(self) -> None:
        """Names with spaces or special chars are not SMILES."""
        provider = PubChemProvider()
        # Multi-word query with spaces is always a name
        assert provider._parse_identifier("acetylsalicylic acid") == ("name", "acetylsalicylic acid")
        # Contains a number break
        assert provider._parse_identifier("BRCA1 gene") == ("name", "BRCA1 gene")


# ======================================================================
# NISTProvider tests
# ======================================================================


class TestNISTProvider:
    """NIST Chemistry WebBook provider with mocked _get_text."""

    async def test_fetch_returns_html(self, ctx_chemistry: RetrievalContext) -> None:
        provider = NISTProvider()
        provider._get_text = AsyncMock(  # type: ignore[method-assign]
            return_value="<html><title>Aspirin - NIST</title><body>Data</body></html>"
        )
        result = await provider.fetch(ctx_chemistry)
        assert result.provider == "nist"
        assert "html" in result.raw_data
        assert "Aspirin" in result.raw_data["html"]
        assert result.metadata["content_type"] == "text/html"

    async def test_http_429_raises_rate_limited(self, ctx_physics: RetrievalContext) -> None:
        provider = NISTProvider()
        provider._get_text = AsyncMock(  # type: ignore[method-assign]
            side_effect=ProviderRateLimitedError("Rate limited by nist (429)")
        )
        with pytest.raises(ProviderRateLimitedError):
            await provider.fetch(ctx_physics)

    async def test_supported_domains(self) -> None:
        provider = NISTProvider()
        assert ScientificDomain.CHEMISTRY in provider.supported_domains
        assert ScientificDomain.PHYSICS in provider.supported_domains
        assert ScientificDomain.ENGINEERING in provider.supported_domains


# ======================================================================
# BaseProvider error mapping tests
# ======================================================================


class TestBaseProviderErrors:
    """BaseProvider error handling (timeout, connection, rate-limit)."""

    async def test_provider_timeout_error(self) -> None:
        """Timeout raises ProviderTimeoutError."""
        provider = NCBIProvider()
        provider._get = AsyncMock(  # type: ignore[method-assign]
            side_effect=ProviderTimeoutError("ncbi request timed out")
        )
        ctx = RetrievalContext(query="test", domains=[ScientificDomain.BIOLOGY])
        with pytest.raises(ProviderTimeoutError):
            await provider.fetch(ctx)

    async def test_provider_connection_error(self) -> None:
        """Connection failure raises ProviderConnectionError."""
        provider = NCBIProvider()
        provider._get = AsyncMock(  # type: ignore[method-assign]
            side_effect=ProviderConnectionError("ncbi connection error")
        )
        ctx = RetrievalContext(query="test", domains=[ScientificDomain.BIOLOGY])
        with pytest.raises(ProviderConnectionError):
            await provider.fetch(ctx)

    async def test_non_json_response_raises_provider_data_error(self) -> None:
        """Non-JSON response raises ProviderDataError."""
        provider = NCBIProvider()
        provider._get = AsyncMock(  # type: ignore[method-assign]
            side_effect=ProviderDataError("ncbi returned non-JSON data")
        )
        ctx = RetrievalContext(query="test", domains=[ScientificDomain.BIOLOGY])
        with pytest.raises(ProviderDataError):
            await provider.fetch(ctx)
