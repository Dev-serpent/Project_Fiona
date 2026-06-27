"""Tests for the SciLab processing pipeline.

Covers Parser, Ranker, Deduplicator, Summarizer, ContextGenerator,
and the SciLabEngine orchestrator.
"""

from __future__ import annotations

import pytest

from SciRetrieval.models import (
    EntityRelationship,
    EntityType,
    RetrievalContext,
    SciLabResult,
    ScientificEntity,
)
from SciRetrieval.scilab.parser import SciLabParser
from SciRetrieval.scilab.ranker import Ranker
from SciRetrieval.scilab.deduplicator import Deduplicator
from SciRetrieval.scilab.summarizer import Summarizer
from SciRetrieval.scilab.context_generator import ContextGenerator
import pytest

pytestmark = pytest.mark.asyncio

from SciRetrieval.scilab.engine import SciLabEngine
from SciPhi.interfaces.model import ScientificDomain


# ======================================================================
# Helpers
# ======================================================================


def make_entity(
    name: str = "Test",
    entity_type: EntityType = EntityType.UNKNOWN,
    canonical_id: str = "",
    properties: dict | None = None,
    aliases: list[str] | None = None,
    source: str = "",
    source_id: str = "",
    confidence: float = 1.0,
    relationships: list | None = None,
) -> ScientificEntity:
    return ScientificEntity(
        name=name,
        entity_type=entity_type,
        canonical_id=canonical_id,
        properties=properties or {},
        aliases=aliases or [],
        source=source,
        source_id=source_id,
        confidence=confidence,
        relationships=relationships or [],
    )


# ======================================================================
# Parser
# ======================================================================


class TestSciLabParser:
    """Entity property parsing."""

    def test_parse_chemical_compound(self) -> None:
        entity = make_entity(
            name="Aspirin",
            entity_type=EntityType.CHEMICAL_COMPOUND,
            properties={
                "mw": "180.16 g/mol",
                "mf": "C9H8O4",
                "canonical_smiles": "CC(=O)OC1=CC=CC=C1C(=O)O",
                "inchikey": "BSYNRYMUTXBXSQ-UHFFFAOYSA-N",
                "logp": "1.2",
            },
        )
        parser = SciLabParser()
        parsed = parser.parse([entity])
        assert len(parsed) == 1
        # mw should be parsed to float
        assert parsed[0].properties["mw"] == 180.16
        assert parsed[0].properties["mf"] == "C9H8O4"
        assert parsed[0].properties["canonical_smiles"] == "CC(=O)OC1=CC=CC=C1C(=O)O"

    def test_parse_protein(self) -> None:
        entity = make_entity(
            name="TP53",
            entity_type=EntityType.PROTEIN,
            properties={
                "organism": "Homo sapiens",
                "gene_symbol": "TP53",
                "summary": "Tumor suppressor protein",
            },
        )
        parser = SciLabParser()
        parsed = parser.parse([entity])
        assert parsed[0].properties["organism"] == "Homo sapiens"
        assert parsed[0].properties["gene_symbol"] == "TP53"
        assert parsed[0].properties["function"] == "Tumor suppressor protein"

    def test_parse_gene(self) -> None:
        entity = make_entity(
            name="BRCA1",
            entity_type=EntityType.GENE,
            properties={
                "organism": "Homo sapiens",
                "gene_symbol": "BRCA1",
            },
        )
        parser = SciLabParser()
        parsed = parser.parse([entity])
        assert parsed[0].properties["organism"] == "Homo sapiens"
        assert parsed[0].properties["gene_symbol"] == "BRCA1"

    def test_parse_unknown_type_passthrough(self) -> None:
        entity = make_entity(
            name="Unknown",
            entity_type=EntityType.UNKNOWN,
            properties={"foo": "bar"},
        )
        parser = SciLabParser()
        parsed = parser.parse([entity])
        assert parsed[0].properties["foo"] == "bar"

    def test_parse_empty_list(self) -> None:
        parser = SciLabParser()
        parsed = parser.parse([])
        assert parsed == []

    def test_parse_malformed_properties_graceful(self) -> None:
        """Parser handles exceptions gracefully per entity."""
        entity = make_entity(
            name="Test",
            entity_type=EntityType.CHEMICAL_COMPOUND,
            properties={"mw": "not a number"},
        )
        parser = SciLabParser()
        parsed = parser.parse([entity])
        # Should not crash; mw stays as-is if parsing fails
        assert parsed[0].properties["mw"] == "not a number"


# ======================================================================
# Ranker
# ======================================================================


class TestRanker:
    """Relevance ranking."""

    def test_exact_name_match_highest(self) -> None:
        exact = make_entity(name="Aspirin", canonical_id="1")
        partial = make_entity(name="Aspirin Derivatives", canonical_id="2")
        unrelated = make_entity(name="Ibuprofen", canonical_id="3")

        ranker = Ranker()
        ranked = ranker.rank([unrelated, partial, exact], "Aspirin")

        # Exact match should be first
        assert ranked[0].name == "Aspirin"

    def test_partial_match_scores_lower(self) -> None:
        exact = make_entity(name="TP53", canonical_id="1")
        partial = make_entity(name="TP53 Binding Protein", canonical_id="2")

        ranker = Ranker()
        ranked = ranker.rank([partial, exact], "TP53")
        assert ranked[0].name == "TP53"

    def test_alias_match(self) -> None:
        entity = make_entity(
            name="Tumor Protein",
            aliases=["p53"],
            canonical_id="1",
        )
        ranker = Ranker()
        ranked = ranker.rank([entity], "p53")
        assert ranked[0].name == "Tumor Protein"

    def test_unknown_type_penalty(self) -> None:
        known = make_entity(
            name="Something",
            entity_type=EntityType.PROTEIN,
            canonical_id="1",
        )
        unknown = make_entity(
            name="Something",
            entity_type=EntityType.UNKNOWN,
            canonical_id="2",
        )
        ranker = Ranker()
        ranked = ranker.rank([unknown, known], "Something")
        # Known type should be ranked higher (unknown has -2 penalty)
        assert ranked[0].entity_type == EntityType.PROTEIN

    def test_ties_preserve_original_order(self) -> None:
        e1 = make_entity(name="First", canonical_id="1")
        e2 = make_entity(name="Second", canonical_id="2")
        e3 = make_entity(name="Third", canonical_id="3")

        ranker = Ranker()
        ranked = ranker.rank([e1, e2, e3], "unrelated")
        # All have same score (0), so original order is preserved
        assert [e.name for e in ranked] == ["First", "Second", "Third"]

    def test_property_value_match(self) -> None:
        entity = make_entity(
            name="Compound",
            properties={"mf": "C9H8O4", "inchikey": "BSYN..."},
        )
        ranker = Ranker()
        ranked = ranker.rank([entity], "C9H8O4")
        # Should still be ranked (property match)
        assert len(ranked) == 1


# ======================================================================
# Deduplicator
# ======================================================================


class TestDeduplicator:
    """Final safety-net deduplication."""

    def test_no_duplicates(self) -> None:
        e1 = make_entity(name="Entity1", canonical_id="1")
        e2 = make_entity(name="Entity2", canonical_id="2")
        dedup = Deduplicator()
        result = dedup.deduplicate([e1, e2])
        assert len(result) == 2

    def test_duplicate_canonical_id_merged(self) -> None:
        e1 = make_entity(
            name="Aspirin",
            canonical_id="pubchem:2244",
            properties={"mw": 180.16},
        )
        e2 = make_entity(
            name="ASA",
            canonical_id="pubchem:2244",
            properties={"mf": "C9H8O4"},
        )
        dedup = Deduplicator()
        result = dedup.deduplicate([e1, e2])
        assert len(result) == 1
        assert result[0].canonical_id == "pubchem:2244"
        # Properties merged
        assert "mw" in result[0].properties
        assert "mf" in result[0].properties

    def test_similar_names_kept_separate(self) -> None:
        """Different IDs but similar names — kept separate (safety net)."""
        e1 = make_entity(name="Glucose", canonical_id="pubchem:5793")
        e2 = make_entity(name="Glucose", canonical_id="pubchem:5794")  # different ID
        dedup = Deduplicator()
        result = dedup.deduplicate([e1, e2])
        # Different canonical IDs, so separate
        assert len(result) == 2

    def test_empty_list(self) -> None:
        dedup = Deduplicator()
        assert dedup.deduplicate([]) == []

    def test_single_entity(self) -> None:
        e = make_entity(name="Only")
        dedup = Deduplicator()
        result = dedup.deduplicate([e])
        assert len(result) == 1
        assert result[0] == e

    def test_merge_aliases(self) -> None:
        e1 = make_entity(
            name="Aspirin",
            canonical_id="pubchem:2244",
            aliases=["ASA"],
        )
        e2 = make_entity(
            name="Aspirin",
            canonical_id="pubchem:2244",
            aliases=["acetylsalicylic acid"],
        )
        dedup = Deduplicator()
        result = dedup.deduplicate([e1, e2])
        assert len(result[0].aliases) == 2


# ======================================================================
# Summarizer
# ======================================================================


class TestSummarizer:
    """Natural-language summary generation."""

    def test_empty_list(self) -> None:
        s = Summarizer()
        text = s.summarize([], "aspirin")
        assert "No scientific data found" in text

    def test_single_entity(self) -> None:
        e = make_entity(
            name="Aspirin",
            entity_type=EntityType.CHEMICAL_COMPOUND,
            canonical_id="pubchem:2244",
            source="pubchem",
            source_id="2244",
        )
        s = Summarizer()
        text = s.summarize([e], "aspirin")
        assert "Aspirin" in text
        assert "(pubchem:2244)" in text
        assert "chemical compound" in text

    def test_multiple_entities_top_10(self) -> None:
        entities = [
            make_entity(name=f"Entity{i}", canonical_id=str(i))
            for i in range(15)
        ]
        s = Summarizer()
        text = s.summarize(entities, "test query")
        assert "15 result(s)" in text
        assert "showing top 10" in text

    def test_entity_with_properties(self) -> None:
        e = make_entity(
            name="Aspirin",
            entity_type=EntityType.CHEMICAL_COMPOUND,
            properties={"mw": 180.16, "mf": "C9H8O4"},
        )
        s = Summarizer()
        text = s.summarize([e], "aspirin")
        assert "mw=180.16" in text
        assert "mf=C9H8O4" in text


# ======================================================================
# ContextGenerator
# ======================================================================


class TestContextGenerator:
    """Structured context block generation."""

    def test_generates_context_header(self) -> None:
        cg = ContextGenerator()
        text = cg.generate([], "No results.")
        assert "[SciRetrieval Context]" in text

    def test_includes_summary(self) -> None:
        cg = ContextGenerator()
        text = cg.generate([], "Found 2 results.")
        assert "Found 2 results." in text

    def test_entities_section(self) -> None:
        e = make_entity(
            name="Aspirin",
            entity_type=EntityType.CHEMICAL_COMPOUND,
            canonical_id="pubchem:2244",
            source="pubchem",
            source_id="2244",
            properties={"mw": 180.16},
        )
        cg = ContextGenerator()
        text = cg.generate([e], "Summary")
        assert "--- Entities ---" in text
        assert "Aspirin" in text
        assert "pubchem:2244" in text

    def test_relationships_section(self) -> None:
        rel = EntityRelationship(
            source_id="A", target_id="B", relationship_type="interacts_with"
        )
        e = make_entity(
            name="EntityA",
            relationships=[rel],
        )
        cg = ContextGenerator()
        text = cg.generate([e], "Summary")
        assert "--- Relationships ---" in text
        assert "A -> B" in text

    def test_no_relationships_section(self) -> None:
        e = make_entity(name="Alone")
        cg = ContextGenerator()
        text = cg.generate([e], "Summary")
        assert "--- Relationships ---" not in text

    def test_caps_output_size(self) -> None:
        """Context generator caps large outputs."""
        many_entities = [
            make_entity(name=f"Entity{i}", canonical_id=str(i))
            for i in range(1000)
        ]
        cg = ContextGenerator()
        text = cg.generate(many_entities, "Summary")
        # Should not exceed limit
        assert len(text.encode("utf-8")) < 100_000  # generous upper bound


# ======================================================================
# SciLabEngine
# ======================================================================


class TestSciLabEngine:
    """Full SciLab pipeline orchestration."""

    async def test_full_pipeline_returns_sci_lab_result(self) -> None:
        entities = [
            make_entity(
                name="Aspirin",
                entity_type=EntityType.CHEMICAL_COMPOUND,
                properties={"mw": 180.16},
            ),
            make_entity(
                name="Ibuprofen",
                entity_type=EntityType.CHEMICAL_COMPOUND,
                properties={"mw": 206.28},
            ),
        ]
        context = RetrievalContext(
            query="aspirin",
            domains=[ScientificDomain.CHEMISTRY],
        )
        engine = SciLabEngine()
        result = await engine.process(entities, context)

        assert isinstance(result, SciLabResult)
        assert len(result.entities) > 0
        assert result.summary != ""
        assert "[SciRetrieval Context]" in result.context
        assert result.processing_time_ms > 0

    async def test_processing_time_positive(self) -> None:
        engine = SciLabEngine()
        result = await engine.process(
            [make_entity(name="Test")],
            RetrievalContext(query="test", domains=[ScientificDomain.BIOLOGY]),
        )
        assert result.processing_time_ms > 0

    async def test_empty_entities(self) -> None:
        engine = SciLabEngine()
        context = RetrievalContext(
            query="nothing",
            domains=[ScientificDomain.BIOLOGY],
        )
        result = await engine.process([], context)
        assert result.summary != ""
        assert result.entities == []

    async def test_relationships_collected(self) -> None:
        rel = EntityRelationship(
            source_id="A", target_id="B", relationship_type="interacts_with"
        )
        e = make_entity(
            name="EntityA",
            relationships=[rel],
        )
        engine = SciLabEngine()
        context = RetrievalContext(
            query="test",
            domains=[ScientificDomain.BIOLOGY],
        )
        result = await engine.process([e], context)
        assert len(result.relationships) >= 1

    async def test_parser_ranker_dedup_called(self) -> None:
        """Engine calls each sub-component in order."""
        from unittest.mock import MagicMock

        parser = MagicMock(wraps=SciLabParser())
        ranker = MagicMock(wraps=Ranker())
        dedup = MagicMock(wraps=Deduplicator())

        engine = SciLabEngine(parser=parser, ranker=ranker, deduplicator=dedup)
        context = RetrievalContext(
            query="test",
            domains=[ScientificDomain.BIOLOGY],
        )
        await engine.process([make_entity(name="Test")], context)

        parser.parse.assert_called_once()
        ranker.rank.assert_called_once()
        dedup.deduplicate.assert_called_once()
