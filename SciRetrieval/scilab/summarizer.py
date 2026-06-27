"""Natural-language summary generation for retrieved scientific data.

The summarizer produces a human-readable paragraph describing the top
entities found for a query, their types, and key properties.
"""

from __future__ import annotations

import logging
from typing import Any

from SciRetrieval.models import EntityType, ScientificEntity

logger = logging.getLogger(__name__)

# Number of top entities to include in the summary
_DEFAULT_SUMMARY_LIMIT = 10


class Summarizer:
    """Generates natural-language summaries from ranked entity lists."""

    def __init__(self, summary_limit: int = _DEFAULT_SUMMARY_LIMIT) -> None:
        self._limit = summary_limit

    def summarize(
        self, entities: list[ScientificEntity], query: str
    ) -> str:
        """Generate a natural-language summary.

        Args:
            entities: Ranked, deduplicated entities.
            query: The original user query.

        Returns:
            A plain-text summary string.
        """
        if not entities:
            return f"No scientific data found for query: '{query}'."

        top = entities[: self._limit]

        # Count by type
        type_counts: dict[str, int] = {}
        for e in top:
            type_name = e.entity_type.value.replace("_", " ")
            type_counts[type_name] = type_counts.get(type_name, 0) + 1

        # Build summary
        parts: list[str] = []
        parts.append(
            f"Found {len(entities)} result(s) for '{query}' "
            f"(showing top {len(top)})."
        )

        # Type distribution
        type_summary = ", ".join(
            f"{count} {t}{'s' if count > 1 else ''}"
            for t, count in sorted(type_counts.items(), key=lambda x: -x[1])
        )
        if type_summary:
            parts.append(f"Types: {type_summary}.")

        # Entity details
        parts.append("")
        for i, entity in enumerate(top, 1):
            parts.append(self._format_entity(entity, i))

        return "\n".join(parts)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _format_entity(entity: ScientificEntity, index: int) -> str:
        """Format a single entity as a summary line."""
        name = entity.name or "(unnamed)"
        etype = entity.entity_type.value.replace("_", " ")
        source = f"[{entity.source}:{entity.source_id}]" if entity.source and entity.source_id else ""
        cid = f"({entity.canonical_id})" if entity.canonical_id else ""

        # Key properties
        props = []
        for key in ("mw", "mf", "canonical_smiles", "organism", "gene_symbol"):
            val = entity.properties.get(key)
            if val:
                label = key.replace("_", " ")
                props.append(f"{label}={val}")

        prop_str = f" [{', '.join(props)}]" if props else ""

        return f"  {index}. {name} {cid}{source} — {etype}{prop_str}"
