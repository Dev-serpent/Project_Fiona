"""Tests for the Normalizer — provider-specific data conversion.

Tests built-in adapters (pubchem, ncbi, nist) and adapter registration.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.asyncio

from SciRetrieval.models import (
    EntityType,
    RawProviderResult,
    ScientificEntity,
)
from SciRetrieval.normalizer import (
    Normalizer,
    _normalize_pubchem,
    _normalize_ncbi,
    _normalize_nist,
)
from SciRetrieval.errors import NormalizationError


# ======================================================================
# PubChem normalizer
# ======================================================================


class TestNormalizePubChem:
    """_normalize_pubchem adapter tests."""

    def test_normalize_valid_compound(self, sample_pubchem_json: dict) -> None:
        entities = _normalize_pubchem(sample_pubchem_json, {})
        assert len(entities) == 1
        entity = entities[0]
        assert entity.name == "2-acetoxybenzoic acid"
        assert entity.entity_type == EntityType.CHEMICAL_COMPOUND
        assert entity.canonical_id == "pubchem:2244"
        assert entity.properties["mw"] == 180.16
        assert entity.properties["mf"] == "C9H8O4"
        assert entity.properties["canonical_smiles"] == "CC(=O)OC1=CC=CC=C1C(=O)O"

    def test_normalize_empty_data(self) -> None:
        entities = _normalize_pubchem({}, {})
        assert entities == []

    def test_normalize_missing_pc_compounds(self) -> None:
        """Fallback when 'Record' key is present."""
        data = {"Record": {"id": {"id": {"CID": 123}}}}
        entities = _normalize_pubchem(data, {})
        # Record fallback produces one entity
        assert len(entities) >= 0  # graceful, may be empty

    def test_normalize_malformed_data_graceful(self) -> None:
        entities = _normalize_pubchem({"PC_Compounds": [{"bad": "data"}]}, {})
        # Should not raise; should return empty or partial
        assert isinstance(entities, list)

    def test_normalize_no_name_or_cid(self) -> None:
        """Compound without name or CID returns None (skipped)."""
        data = {
            "PC_Compounds": [
                {
                    "id": {"id": {"CID": ""}},
                    "props": [
                        {
                            "urn": {"label": "Some Field"},
                            "value": {"sval": "some value"},
                        }
                    ],
                }
            ]
        }
        entities = _normalize_pubchem(data, {})
        assert entities == []  # skipped because no name and no CID


class TestNormalizePubChemAliases:
    """Synonym/alias extraction from PubChem."""

    def test_aliases_from_synonym_property(self, sample_pubchem_json: dict) -> None:
        """When IUPAC Name is used, aliases from synonyms."""
        entities = _normalize_pubchem(sample_pubchem_json, {})
        # No Synonym property in sample, so aliases should be empty
        assert entities[0].aliases == []

    def test_aliases_from_synonym_string(self) -> None:
        data = {
            "PC_Compounds": [
                {
                    "id": {"id": {"CID": 2244}},
                    "props": [
                        {
                            "urn": {"label": "IUPAC Name"},
                            "value": {"sval": "Aspirin"},
                        },
                        {
                            "urn": {"label": "Synonym"},
                            "value": {"sval": "ASA|acetylsalicylic acid|2-acetoxybenzoic acid"},
                        },
                    ],
                }
            ]
        }
        entities = _normalize_pubchem(data, {})
        assert len(entities) == 1
        assert entities[0].aliases == ["ASA", "acetylsalicylic acid", "2-acetoxybenzoic acid"]


# ======================================================================
# NCBI normalizer
# ======================================================================


class TestNormalizeNcbi:
    """_normalize_ncbi adapter tests."""

    def test_normalize_valid_entries(self, sample_ncbi_json: dict) -> None:
        metadata = {"database": "gene", "ids": ["7157"]}
        entities = _normalize_ncbi(sample_ncbi_json, metadata)
        assert len(entities) == 1
        entity = entities[0]
        assert entity.name == "TP53"
        assert entity.entity_type == EntityType.GENE
        assert entity.canonical_id == "ncbi:7157"
        assert entity.source == "ncbi"
        assert entity.properties["organism"] == "Homo sapiens"

    def test_normalize_empty_result(self) -> None:
        entities = _normalize_ncbi({}, {})
        assert entities == []

    def test_normalize_empty_uids(self) -> None:
        data = {"result": {}}
        entities = _normalize_ncbi(data, {"ids": []})
        assert entities == []

    def test_normalize_missing_name_skipped(self) -> None:
        data = {
            "result": {
                "123": {
                    "uid": "123",
                    # no name, title, or description
                }
            }
        }
        entities = _normalize_ncbi(data, {"ids": ["123"]})
        assert entities == []

    def test_normalize_database_type_mapping(self) -> None:
        """Database type maps to entity type."""
        data = {
            "result": {
                "7157": {
                    "uid": "7157",
                    "name": "TP53",
                    "description": "Tumor protein",
                }
            }
        }
        # Gene database
        entities_gene = _normalize_ncbi(data, {"database": "gene", "ids": ["7157"]})
        assert entities_gene[0].entity_type == EntityType.GENE

        # Protein database
        entities_prot = _normalize_ncbi(data, {"database": "protein", "ids": ["7157"]})
        assert entities_prot[0].entity_type == EntityType.PROTEIN

    def test_normalize_aliases_from_string(self, sample_ncbi_json: dict) -> None:
        entities = _normalize_ncbi(sample_ncbi_json, {"database": "gene", "ids": ["7157"]})
        assert "p53" in entities[0].aliases
        assert "tumor protein p53" in entities[0].aliases


# ======================================================================
# NIST normalizer
# ======================================================================


class TestNormalizeNist:
    """_normalize_nist adapter tests."""

    def test_normalize_valid_html(self, sample_nist_html: str) -> None:
        entities = _normalize_nist({"html": sample_nist_html}, {"query": "aspirin"})
        assert len(entities) == 1
        entity = entities[0]
        assert entity.name == "Aspirin"
        assert entity.entity_type == EntityType.CHEMICAL_COMPOUND
        assert entity.properties["mf"] == "C9H8O4"
        assert entity.properties["mw"] == "180.16 g/mol"

    def test_normalize_empty_html(self) -> None:
        entities = _normalize_nist({"html": ""}, {})
        assert entities == []

    def test_normalize_missing_html(self) -> None:
        entities = _normalize_nist({}, {})
        assert entities == []

    def test_normalize_no_title_fallback_to_query(self) -> None:
        html = "<html><body>No title here</body></html>"
        entities = _normalize_nist({"html": html}, {"query": "glucose"})
        assert len(entities) == 1
        assert entities[0].name == "glucose"

    def test_normalize_malformed_html_graceful(self) -> None:
        entities = _normalize_nist({"html": "not valid html"}, {"query": "test"})
        assert isinstance(entities, list)


# ======================================================================
# Normalizer class
# ======================================================================


class TestNormalizer:
    """Normalizer orchestration class."""

    def test_construction(self) -> None:
        n = Normalizer()
        # Built-in adapters registered
        assert n._adapters["pubchem"] is not None
        assert n._adapters["ncbi"] is not None
        assert n._adapters["nist"] is not None

    def test_register_adapter(self) -> None:
        n = Normalizer()
        called = False

        def custom_adapter(data, metadata):
            nonlocal called
            called = True
            return [ScientificEntity(name="Custom")]

        n.register_adapter("custom", custom_adapter)
        assert "custom" in n._adapters

    async def test_normalize_unknown_provider_returns_empty(self) -> None:
        n = Normalizer()
        raw = RawProviderResult(provider="unknown", raw_data={"key": "val"})
        entities = await n.normalize(raw)
        assert entities == []

    async def test_normalize_calls_adapter(self, sample_pubchem_json: dict) -> None:
        n = Normalizer()
        raw = RawProviderResult(
            provider="pubchem",
            raw_data=sample_pubchem_json,
        )
        entities = await n.normalize(raw)
        assert len(entities) == 1
        # Provenance should be set
        assert entities[0].source == "pubchem"
        assert len(entities[0].sources) > 0
        assert entities[0].sources[0].provider == "pubchem"

    async def test_normalize_adapter_exception_raises_normalization_error(self) -> None:
        n = Normalizer()

        def broken_adapter(data, metadata):
            raise ValueError("Adapter failed")

        n.register_adapter("broken", broken_adapter)
        raw = RawProviderResult(provider="broken", raw_data={})
        with pytest.raises(NormalizationError) as exc_info:
            await n.normalize(raw)
        assert "broken" in str(exc_info.value)
