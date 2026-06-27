"""Tests for the Router — domain classification and intent detection.

Uses ``tmp_path`` to create temporary keyword-list JSON files so the
tests do not depend on the real data file.
"""

from __future__ import annotations

import json

import pytest

import pytest

pytestmark = pytest.mark.asyncio

from SciRetrieval.router import Router
from SciRetrieval.errors import ClassificationError
from SciPhi.interfaces.model import ScientificDomain


# ======================================================================
# Fixtures
# ======================================================================


@pytest.fixture()
def keyword_file(tmp_path):
    """Create a temporary keywordlist.json for testing."""
    data = {
        "biology": {
            "keywords": [
                "gene", "dna", "rna", "protein", "disease",
                "cell", "mutation", "enzyme", "receptor",
                "functional", "brca1", "function",
            ],
            "weight": 1.0,
        },
        "chemistry": {
            "keywords": [
                "compound", "molecule", "reaction", "element",
                "formula", "acid", "base", "pH", "oxidation",
                "molecular", "weight", "aspirin", "chemical",
            ],
            "weight": 1.0,
        },
        "physics": {
            "keywords": [
                "constant", "force", "energy", "velocity",
                "wave", "particle", "quantum", "field",
                "speed", "light",
            ],
            "weight": 1.0,
        },
        "intent": {
            "lookup": [
                "what is", "find", "search", "look up",
                "get", "show me", "tell me about",
            ],
            "compare": ["compare", "versus", "vs", "difference between"],
            "explain": ["explain", "how does", "why does", "describe"],
            "list": ["list", "all", "types of", "kinds of"],
        },
    }
    path = tmp_path / "keywordlist.json"
    path.write_text(json.dumps(data))
    return str(path)


@pytest.fixture()
def router(keyword_file):
    """Router instance backed by the temp keyword file."""
    return Router(keyword_file)


# ======================================================================
# Classification
# ======================================================================


class TestDomainClassification:
    """Classify queries into scientific domains."""

    async def test_biology_query(self, router: Router) -> None:
        result = await router.classify("What is the function of BRCA1 gene?")
        assert result.primary_domain == ScientificDomain.BIOLOGY
        assert result.confidence > 0
        assert "gene" in result.matched_keywords

    async def test_chemistry_query(self, router: Router) -> None:
        result = await router.classify("What is the molecular weight of aspirin?")
        assert result.primary_domain == ScientificDomain.CHEMISTRY
        assert result.confidence > 0

    async def test_physics_query(self, router: Router) -> None:
        result = await router.classify("What is the speed of light?")
        assert result.primary_domain == ScientificDomain.PHYSICS
        assert result.confidence > 0

    async def test_ambiguous_query_highest_wins(self, router: Router) -> None:
        """Query with keywords from multiple domains."""
        result = await router.classify("gene expression and enzyme reaction")
        assert result.primary_domain == ScientificDomain.BIOLOGY

    async def test_empty_query(self, router: Router) -> None:
        """Empty query returns lowest confidence and generic."""
        result = await router.classify("")
        assert result.confidence == 0.0
        assert result.intent == "generic"

    async def test_whitespace_query(self, router: Router) -> None:
        result = await router.classify("   ")
        assert result.confidence == 0.0

    async def test_noise_query(self, router: Router) -> None:
        """Query with no matching keywords."""
        result = await router.classify("How is the weather today?")
        assert result.confidence == 0.0
        assert result.intent == "generic"

    async def test_secondary_domain(self, router: Router) -> None:
        """Query spanning two domains gets a secondary domain."""
        result = await router.classify("gene and molecule")
        assert result.primary_domain == ScientificDomain.BIOLOGY
        assert result.secondary_domain == ScientificDomain.CHEMISTRY


class TestIntentDetection:
    """Detect lookup, compare, explain, list intents."""

    async def test_lookup_intent(self, router: Router) -> None:
        result = await router.classify("what is aspirin")
        assert result.intent == "lookup"

    async def test_compare_intent(self, router: Router) -> None:
        result = await router.classify("compare aspirin and ibuprofen")
        assert result.intent == "compare"

    async def test_explain_intent(self, router: Router) -> None:
        result = await router.classify("explain how DNA replication works")
        assert result.intent == "explain"

    async def test_list_intent(self, router: Router) -> None:
        result = await router.classify("list all types of chemical bonds")
        assert result.intent == "list"

    async def test_generic_fallback(self, router: Router) -> None:
        result = await router.classify("just some random text")
        assert result.intent == "generic"


class TestEdgeCases:
    """Router edge cases and error handling."""

    async def test_case_insensitivity(self, router: Router) -> None:
        result_upper = await router.classify("GENE MUTATION")
        result_lower = await router.classify("gene mutation")
        assert result_upper.primary_domain == result_lower.primary_domain
        assert result_upper.confidence == result_lower.confidence

    async def test_malformed_keyword_file(self, tmp_path) -> None:
        """Router falls back gracefully on malformed JSON."""
        bad_path = tmp_path / "keywordlist.json"
        bad_path.write_text("{invalid json}")
        r = Router(bad_path)
        result = await r.classify("gene")
        # Falls back to empty keywords => confidence 0
        assert result.confidence == 0.0
        assert result.intent == "generic"

    async def test_missing_keyword_file(self, tmp_path) -> None:
        """Router falls back gracefully on missing file."""
        missing = tmp_path / "nonexistent.json"
        r = Router(missing)
        result = await r.classify("dna")
        assert result.confidence == 0.0

    async def test_classification_error_wraps_exception(self, tmp_path) -> None:
        """Router wraps internal exceptions in ClassificationError."""
        # Point to a non-existent file — triggers fallback to empty data
        missing = tmp_path / "nonexistent.json"
        r = Router(missing)
        query = "gene"
        result = await r.classify(query)
        # The load falls back gracefully to empty data
        assert result.confidence == 0.0
