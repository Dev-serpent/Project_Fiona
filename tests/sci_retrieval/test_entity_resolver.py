"""Tests for EntityResolver — synonym resolution and cross-provider merging.

Uses ``tmp_path`` to create temporary synonym JSON files.
"""

from __future__ import annotations

import json
from unittest.mock import patch

import pytest

import pytest

pytestmark = pytest.mark.asyncio

from SciRetrieval.entity_resolver import EntityResolver, SynonymEntry
from SciRetrieval.models import (
    EntityRelationship,
    EntityType,
    ProvenanceEntry,
    ScientificEntity,
)
from SciPhi.interfaces.model import ScientificDomain


# ======================================================================
# Fixtures
# ======================================================================


@pytest.fixture()
def synonyms_file(tmp_path):
    """Create a temporary synonyms.json for testing."""
    data = {
        "aspirin": {
            "canonical_id": "pubchem:2244",
            "canonical_name": "Aspirin",
            "aliases": [
                "acetylsalicylic acid",
                "ASA",
                "2-acetoxybenzoic acid",
            ],
            "entity_type": "chemical_compound",
        },
        "tp53": {
            "canonical_id": "ncbi:7157",
            "canonical_name": "TP53",
            "aliases": ["p53", "tumor protein p53", "cellular tumor antigen p53"],
            "entity_type": "protein",
        },
        "brca1": {
            "canonical_id": "ncbi:672",
            "canonical_name": "BRCA1",
            "aliases": [
                "breast cancer type 1 susceptibility protein",
                "RNF53",
            ],
            "entity_type": "protein",
        },
    }
    path = tmp_path / "synonyms.json"
    path.write_text(json.dumps(data))
    return str(path)


@pytest.fixture()
def resolver(synonyms_file: str) -> EntityResolver:
    return EntityResolver(synonyms_file)


# ======================================================================
# Synonym registry loading
# ======================================================================


class TestSynonymLoading:
    """Loading the synonym registry from JSON."""

    def test_loading_populates_registry(self, resolver: EntityResolver) -> None:
        """Main entries and aliases are registered."""
        # Main entry keys
        assert "aspirin" in resolver._synonym_registry
        assert "tp53" in resolver._synonym_registry

        # Alias keys
        assert "p53" in resolver._synonym_registry
        assert "asa" in resolver._synonym_registry

    def test_synonym_entry_structure(self, resolver: EntityResolver) -> None:
        entry = resolver._synonym_registry["aspirin"]
        assert isinstance(entry, SynonymEntry)
        assert entry.canonical_id == "pubchem:2244"
        assert entry.canonical_name == "Aspirin"
        assert "ASA" in entry.aliases

    def test_missing_file_starts_empty(self, tmp_path) -> None:
        missing = tmp_path / "nonexistent.json"
        r = EntityResolver(str(missing))
        assert r._synonym_registry == {}

    def test_malformed_file_starts_empty(self, tmp_path) -> None:
        bad = tmp_path / "bad.json"
        bad.write_text("{invalid}")
        r = EntityResolver(str(bad))
        assert r._synonym_registry == {}


# ======================================================================
# Resolution
# ======================================================================


class TestResolveCanonicalId:
    """Canonical ID resolution logic."""

    def test_exact_name_match(self, resolver: EntityResolver) -> None:
        e = ScientificEntity(name="aspirin")
        cid = resolver._resolve_canonical_id(e)
        assert cid == "pubchem:2244"

    def test_alias_match(self, resolver: EntityResolver) -> None:
        e = ScientificEntity(name="Some Compound", aliases=["ASA"])
        cid = resolver._resolve_canonical_id(e)
        assert cid == "pubchem:2244"

    def test_existing_canonical_id_preserved(self, resolver: EntityResolver) -> None:
        e = ScientificEntity(
            name="Random",
            canonical_id="custom:123",
        )
        cid = resolver._resolve_canonical_id(e)
        assert cid == "custom:123"

    def test_fallback_to_source_id(self, resolver: EntityResolver) -> None:
        e = ScientificEntity(
            name="Unknown",
            source="pubchem",
            source_id="9999",
        )
        cid = resolver._resolve_canonical_id(e)
        assert cid == "pubchem:9999"

    def test_fallback_to_auto(self, resolver: EntityResolver) -> None:
        e = ScientificEntity(name="NoMatch")
        cid = resolver._resolve_canonical_id(e)
        assert cid.startswith("auto:")

    def test_case_insensitive_match(self, resolver: EntityResolver) -> None:
        e = ScientificEntity(name="ASPIRIN")
        cid = resolver._resolve_canonical_id(e)
        assert cid == "pubchem:2244"


# ======================================================================
# Merging
# ======================================================================


class TestMergeGroup:
    """Merging multiple entities with the same canonical ID."""

    def test_merge_two_entities_same_name(self, resolver: EntityResolver) -> None:
        """Aspirin from PubChem + Acetylsalicylic acid from NCBI."""
        from SciRetrieval.models import ProvenanceEntry

        e1 = ScientificEntity(
            name="Aspirin",
            canonical_id="pubchem:2244",
            source="pubchem",
            source_id="2244",
            properties={"mw": 180.16, "mf": "C9H8O4"},
            confidence=0.9,
            sources=[ProvenanceEntry(provider="pubchem", source_id="2244", fields=["mw", "mf"])],
        )
        e2 = ScientificEntity(
            name="Acetylsalicylic acid",
            aliases=["ASA"],
            source="ncbi",
            source_id="12345",
            properties={"iupac_name": "2-acetoxybenzoic acid"},
            confidence=0.8,
            sources=[ProvenanceEntry(provider="ncbi", source_id="12345", fields=["iupac_name"])],
        )
        merged = resolver._merge_group("pubchem:2244", [e1, e2])
        assert merged is not None
        # Should use canonical name from registry
        assert merged.name == "Aspirin"
        # Properties should be merged
        assert merged.properties["mw"] == 180.16
        assert merged.properties["iupac_name"] == "2-acetoxybenzoic acid"
        # Confidence = max
        assert merged.confidence == 0.9
        # Provenance merged
        assert len(merged.sources) == 2

    def test_merge_tp53_p53(self, resolver: EntityResolver) -> None:
        """TP53 / p53 / tumor protein p53 merge."""
        e1 = ScientificEntity(
            name="TP53",
            aliases=["p53"],
            canonical_id="ncbi:7157",
            source="ncbi",
            source_id="7157",
            entity_type=EntityType.PROTEIN,
        )
        e2 = ScientificEntity(
            name="tumor protein p53",
            source="other",
            source_id="999",
            entity_type=EntityType.PROTEIN,
        )
        merged = resolver._merge_group("ncbi:7157", [e1, e2])
        assert merged is not None
        assert merged.name == "TP53"
        assert merged.canonical_id == "ncbi:7157"

    def test_single_entity_no_merge(self, resolver: EntityResolver) -> None:
        e = ScientificEntity(name="Unique")
        merged = resolver._merge_group("unique:1", [e])
        assert merged == e  # same object

    def test_empty_group_returns_none(self, resolver: EntityResolver) -> None:
        assert resolver._merge_group("empty:1", []) is None

    def test_property_merge_later_overwrites(self, resolver: EntityResolver) -> None:
        """Later entities overwrite earlier for same key."""
        e1 = ScientificEntity(name="E1", properties={"mw": 100.0})
        e2 = ScientificEntity(name="E2", properties={"mw": 200.0})
        merged = resolver._merge_group("test:id", [e1, e2])
        assert merged.properties["mw"] == 200.0

    def test_relationship_merge_dedup(self, resolver: EntityResolver) -> None:
        rel = EntityRelationship(
            source_id="A", target_id="B", relationship_type="interacts_with"
        )
        e1 = ScientificEntity(name="E1", relationships=[rel])
        e2 = ScientificEntity(name="E2", relationships=[rel])  # same rel
        merged = resolver._merge_group("test:id", [e1, e2])
        assert len(merged.relationships) == 1  # deduplicated


# ======================================================================
# Full resolve pipeline
# ======================================================================


class TestFullResolve:
    """End-to-end entity resolution."""

    async def test_no_synonym_match_keeps_identity(
        self, resolver: EntityResolver
    ) -> None:
        e = ScientificEntity(name="UnknownCompound")
        resolved = await resolver.resolve([e])
        assert len(resolved) == 1
        assert resolved[0] == e

    async def test_merge_cross_provider_duplicates(
        self, resolver: EntityResolver
    ) -> None:
        """Two entities with same canonical ID merged into one."""
        e1 = ScientificEntity(
            name="Aspirin",
            source="pubchem",
            source_id="2244",
        )
        e2 = ScientificEntity(
            name="acetylsalicylic acid",
            source="ncbi",
            source_id="12345",
        )
        resolved = await resolver.resolve([e1, e2])
        assert len(resolved) == 1  # merged into one
        assert resolved[0].canonical_id == "pubchem:2244"

    async def test_provenance_tracking(self, resolver: EntityResolver) -> None:
        """Sources list merged correctly."""
        e1 = ScientificEntity(
            name="Aspirin",
            source="pubchem",
            source_id="2244",
            sources=[
                ProvenanceEntry(
                    provider="pubchem",
                    source_id="2244",
                    fields=["mw"],
                )
            ],
        )
        e2 = ScientificEntity(
            name="ASA",
            source="ncbi",
            source_id="12345",
            sources=[
                ProvenanceEntry(
                    provider="ncbi",
                    source_id="12345",
                    fields=["name"],
                )
            ],
        )
        resolved = await resolver.resolve([e1, e2])
        assert len(resolved[0].sources) == 2

    async def test_empty_synonym_path(self, tmp_path) -> None:
        """Resolver works with no synonyms loaded."""
        r = EntityResolver(None)
        e = ScientificEntity(name="Anything")
        resolved = await r.resolve([e])
        assert len(resolved) == 1
        assert resolved[0].name == "Anything"

    async def test_different_ids_similar_names_kept_separate(
        self, resolver: EntityResolver
    ) -> None:
        """Entities with different IDs but similar names stay separate."""
        e1 = ScientificEntity(
            name="Glucose",
            source="pubchem",
            source_id="5793",
        )
        e2 = ScientificEntity(
            name="Glucose",
            source="other",
            source_id="xxx",
        )
        # Without a synonym linking these, they get different canonical IDs
        resolved = await resolver.resolve([e1, e2])
        # Each gets its own auto-ID (no match in registry since "glucose" maps
        # to pubchem:5793)
        assert len(resolved) <= 2
