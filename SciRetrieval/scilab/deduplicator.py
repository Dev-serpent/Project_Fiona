"""Final safety-net deduplication after entity resolution.

While :class:`SciRetrieval.entity_resolver.EntityResolver` handles
canonical merging by synonym registry, the deduplicator catches any
remaining duplicates that share a canonical ID or have very similar
names.
"""

from __future__ import annotations

import logging
from typing import Any

from SciRetrieval.models import EntityRelationship, EntityType, ProvenanceEntry, ScientificEntity

logger = logging.getLogger(__name__)


class Deduplicator:
    """Removes duplicate entities that share a canonical ID or have
    highly similar names.

    This is a lightweight final pass — it does not reload the synonym
    registry or attempt cross-provider resolution.
    """

    def deduplicate(
        self, entities: list[ScientificEntity]
    ) -> list[ScientificEntity]:
        """Deduplicate a list of entities.

        Grouping priority:
        1. ``canonical_id`` (if set)
        2. Normalised name (lowercase, stripped)

        Within each group the entity with the highest confidence is kept
        and properties / aliases / relationships / provenance are merged.

        Args:
            entities: Entities from the ranker (may still have duplicates).

        Returns:
            Deduplicated list.
        """
        if not entities:
            return []

        # Build groups
        groups: dict[str, list[ScientificEntity]] = {}
        for entity in entities:
            key = self._group_key(entity)
            groups.setdefault(key, []).append(entity)

        # Merge each group
        result: list[ScientificEntity] = []
        for key, group in groups.items():
            if len(group) == 1:
                result.append(group[0])
            else:
                merged = self._merge_group(group)
                if merged:
                    result.append(merged)

        return result

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    @staticmethod
    def _group_key(entity: ScientificEntity) -> str:
        """Determine the grouping key for an entity."""
        if entity.canonical_id:
            return entity.canonical_id
        name_key = entity.name.lower().strip()
        if name_key:
            return name_key
        return entity.id

    @staticmethod
    def _merge_group(group: list[ScientificEntity]) -> ScientificEntity | None:
        """Merge a group of duplicate entities into one."""
        if not group:
            return None

        # Sort by confidence descending
        sorted_group = sorted(
            group, key=lambda e: (e.confidence, 1 if e.source else 0), reverse=True
        )
        base = sorted_group[0]

        # Merge aliases
        all_aliases: list[str] = []
        for ent in sorted_group:
            for alias in ent.aliases:
                if alias.lower() not in (a.lower() for a in all_aliases):
                    all_aliases.append(alias)
        base.aliases = all_aliases

        # Merge properties (later overwrites earlier)
        for ent in sorted_group[1:]:
            base.properties.update(ent.properties)

        # Merge relationships (deduplicate)
        seen_rels: set[tuple[str, str, str]] = {
            (r.source_id, r.target_id, r.relationship_type)
            for r in base.relationships
        }
        for ent in sorted_group[1:]:
            for rel in ent.relationships:
                key = (rel.source_id, rel.target_id, rel.relationship_type)
                if key not in seen_rels:
                    seen_rels.add(key)
                    base.relationships.append(rel)

        # Merge provenance
        seen_src: set[tuple[str, str]] = {
            (s.provider, s.source_id) for s in base.sources
        }
        for ent in sorted_group[1:]:
            for src in ent.sources:
                key = (src.provider, src.source_id)
                if key not in seen_src:
                    seen_src.add(key)
                    base.sources.append(src)

        # Confidence = max
        base.confidence = max(e.confidence for e in sorted_group)

        return base
