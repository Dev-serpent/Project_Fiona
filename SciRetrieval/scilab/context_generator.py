"""Structured context block generator for LLM prompt injection.

Produces a formatted text block that can be injected into an LLM
prompt to provide structured scientific context alongside the
natural-language summary.
"""

from __future__ import annotations

import logging
from typing import Any

from SciRetrieval.models import EntityRelationship, ScientificEntity

logger = logging.getLogger(__name__)

# Maximum output size in bytes (approximate)
_MAX_OUTPUT_BYTES = 50_000


class ContextGenerator:
    """Generates a structured, LLM-friendly context block.

    The output format is::

        [SciRetrieval Context]
        {summary}

        --- Entities ---
        - Name [source:id] type=... props=[...] rels=[...]

        --- Relationships ---
        source -> target: type (confidence)
    """

    def generate(
        self, entities: list[ScientificEntity], summary: str
    ) -> str:
        """Produce a structured context block.

        Args:
            entities: Processed entities.
            summary: Natural-language summary from the summarizer.

        Returns:
            A string suitable for LLM prompt injection, capped at
            ``_MAX_OUTPUT_BYTES`` bytes.
        """
        lines: list[str] = []
        lines.append("[SciRetrieval Context]")
        lines.append(summary)
        lines.append("")

        # Entities section
        lines.append("--- Entities ---")
        for entity in entities:
            try:
                line = self._format_entity(entity)
                lines.append(line)
            except Exception as exc:
                logger.debug("Failed to format entity %s: %s", entity.id, exc)

        # Relationships section
        all_rels: list[EntityRelationship] = []
        for entity in entities:
            all_rels.extend(entity.relationships)

        if all_rels:
            lines.append("")
            lines.append("--- Relationships ---")
            for rel in all_rels:
                lines.append(
                    f"  {rel.source_id} -> {rel.target_id}: "
                    f"{rel.relationship_type} (conf={rel.confidence:.2f})"
                )

        result = "\n".join(lines)

        # Enforce size cap
        if len(result.encode("utf-8")) > _MAX_OUTPUT_BYTES:
            # Truncate entities section
            cutoff = result.find("--- Relationships ---")
            if cutoff == -1:
                cutoff = len(result)
            # Keep only first portion
            max_lines = 500  # rough heuristic
            short_lines = result.split("\n")[:max_lines]
            result = "\n".join(short_lines)
            result += f"\n... (truncated, {len(entities)} entities total)"

        return result

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _format_entity(entity: ScientificEntity) -> str:
        """Format a single entity for the context block."""
        name = entity.name or entity.canonical_id or entity.id
        src_tag = f"[{entity.source}:{entity.source_id}]" if entity.source else ""
        type_str = entity.entity_type.value
        cid = entity.canonical_id or ""

        # Key properties (compact)
        prop_items = []
        for k, v in entity.properties.items():
            if v:
                prop_items.append(f"{k}={v}")
        prop_str = f"props=[{', '.join(prop_items[:6])}]" if prop_items else ""

        # Relationships count
        rel_count = len(entity.relationships)
        rel_str = f" rels={rel_count}" if rel_count else ""

        # Aliases
        alias_str = ""
        if entity.aliases:
            alias_list = [a for a in entity.aliases[:3]]
            alias_str = f" aliases=[{', '.join(alias_list)}]" if alias_list else ""

        return (
            f"  - {name} {cid} {src_tag} type={type_str}"
            f"{prop_str}{rel_str}{alias_str}"
        )
