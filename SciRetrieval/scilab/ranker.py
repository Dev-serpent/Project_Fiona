"""Relevance scoring and ranking of scientific entities.

The ranker scores each entity based on how well its name, aliases,
and properties match the original user query, then returns the list
sorted by descending score.
"""

from __future__ import annotations

import logging
import re
from typing import Any

from SciRetrieval.models import EntityType, ScientificEntity

logger = logging.getLogger(__name__)


class Ranker:
    """Scores and sorts entities by query relevance.

    Scoring rules:
    * +5: exact name match (case-insensitive)
    * +3: name contains query as a substring
    * +2: any alias matches query exactly
    * +1: any alias contains query as a substring
    * +0.5: any property value contains a query term
    * +1: entity type matches the query context
    * -2 for ``UNKNOWN`` entity type (penalty)
    """

    def rank(
        self, entities: list[ScientificEntity], query: str
    ) -> list[ScientificEntity]:
        """Score and sort entities by relevance to *query*.

        Args:
            entities: Entities to rank (already parsed).
            query: The original user query.

        Returns:
            Sorted list (highest score first).
        """
        query_lower = query.lower().strip()
        query_terms = self._tokenize(query_lower)

        scored = [(entity, self._score(entity, query_lower, query_terms)) for entity in entities]
        scored.sort(key=lambda x: -x[1])

        return [e for e, _ in scored]

    # ------------------------------------------------------------------
    # Scoring
    # ------------------------------------------------------------------

    def _score(
        self,
        entity: ScientificEntity,
        query_lower: str,
        query_terms: list[str],
    ) -> float:
        """Compute a relevance score for *entity*."""
        score = 0.0

        # Exact name match
        if entity.name.lower() == query_lower:
            score += 5.0
        elif entity.name.lower() in query_lower or query_lower in entity.name.lower():
            score += 3.0

        # Alias matches
        for alias in entity.aliases:
            alias_lower = alias.lower()
            if alias_lower == query_lower:
                score += 2.0
            elif query_lower in alias_lower or alias_lower in query_lower:
                score += 1.0

        # Property value matches
        for key, value in entity.properties.items():
            val_str = str(value).lower()
            for term in query_terms:
                if term in val_str:
                    score += 0.5

        # Entity type penalty
        if entity.entity_type == EntityType.UNKNOWN:
            score -= 2.0

        return score

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _tokenize(text: str) -> list[str]:
        """Split text into lowercase tokens."""
        return [t for t in re.findall(r"[a-zA-Z0-9]+", text) if len(t) > 1]
