"""Entity property parser — extracts structured fields from entity properties.

The parser enriches :class:`ScientificEntity` objects by extracting
typed, well-known fields from the generic ``properties`` dictionary
and promoting them to a canonical structure.
"""

from __future__ import annotations

import logging
from typing import Any

from SciRetrieval.models import EntityType, ScientificEntity

logger = logging.getLogger(__name__)


class SciLabParser:
    """Extracts structured data from ``ScientificEntity.properties``.

    Each entity type has known property keys.  The parser normalises
    these so downstream stages (ranking, summarisation) can rely on
    consistent field names.
    """

    def parse(self, entities: list[ScientificEntity]) -> list[ScientificEntity]:
        """Parse and enrich entity properties.

        Iterates over all entities and applies type-specific extraction.

        Args:
            entities: Entities to parse.

        Returns:
            Same list, with each entity's ``properties`` dict enriched.
        """
        for entity in entities:
            try:
                self._parse_entity(entity)
            except Exception as exc:
                logger.debug(
                    "Failed to parse entity %s: %s", entity.name or entity.id, exc
                )

        return entities

    # ------------------------------------------------------------------
    # Type-specific parsers
    # ------------------------------------------------------------------

    def _parse_entity(self, entity: ScientificEntity) -> None:
        """Apply type-specific parsing to a single entity."""
        parser = self._PARSERS.get(entity.entity_type)
        if parser:
            parser(self, entity)

    def _parse_chemical_compound(self, entity: ScientificEntity) -> None:
        """Extract well-known chemical compound fields."""
        props = entity.properties

        # Canonicalise molecular weight
        mw = props.get("mw", props.get("Molecular Weight", props.get("MW", "")))
        if mw and isinstance(mw, (int, float)):
            props["mw"] = float(mw)
        elif mw and isinstance(mw, str):
            # Remove units like " g/mol"
            mw_clean = mw.replace("g/mol", "").replace("g·mol⁻¹", "").strip()
            try:
                props["mw"] = float(mw_clean.split()[0])
            except (ValueError, IndexError):
                pass

        # Canonicalise molecular formula
        mf = props.get("mf", props.get("Molecular Formula", props.get("MF", "")))
        if mf:
            props["mf"] = str(mf).strip()

        # Canonicalise SMILES
        smiles = props.get(
            "canonical_smiles",
            props.get("Canonical SMILES", props.get("SMILES", "")),
        )
        if smiles:
            props["canonical_smiles"] = str(smiles).strip()

        # Canonicalise InChIKey
        inchikey = props.get("inchikey", props.get("InChIKey", props.get("InChI Key", "")))
        if inchikey:
            props["inchikey"] = str(inchikey).strip()

        # Canonicalise LogP
        logp = props.get("logp", props.get("Log P", props.get("LogP", "")))
        if logp:
            try:
                props["logp"] = float(logp)
            except (ValueError, TypeError):
                pass

        # IUPAC Name
        iupac = props.get("iupac_name", props.get("IUPAC Name", ""))
        if iupac:
            props["iupac_name"] = str(iupac).strip()

    def _parse_protein(self, entity: ScientificEntity) -> None:
        """Extract well-known protein / gene fields."""
        props = entity.properties

        organism = props.get("organism", props.get("Organism", ""))
        if organism:
            props["organism"] = str(organism).strip()

        gene_symbol = props.get(
            "gene_symbol",
            props.get("Gene Symbol", props.get("symbol", "")),
        )
        if gene_symbol:
            props["gene_symbol"] = str(gene_symbol).strip()

        function = props.get(
            "function",
            props.get("summary", props.get("description", "")),
        )
        if function:
            props["function"] = str(function).strip()

    def _parse_gene(self, entity: ScientificEntity) -> None:
        """Gene parsing is similar to protein."""
        self._parse_protein(entity)

    _PARSERS: dict[EntityType, Any] = {
        EntityType.CHEMICAL_COMPOUND: _parse_chemical_compound,
        EntityType.PROTEIN: _parse_protein,
        EntityType.GENE: _parse_gene,
    }
