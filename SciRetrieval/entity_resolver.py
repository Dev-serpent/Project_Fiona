"""Entity resolution — alias resolution, canonical ID assignment, and
cross-provider duplicate merging.

The :class:`EntityResolver` uses a synonym registry (loaded from
``synonyms.json``) to map entity names and aliases to stable canonical
IDs, then groups and merges entities that share the same canonical ID.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from SciRetrieval.interfaces import IEntityResolver
from SciRetrieval.models import (
    EntityRelationship,
    EntityType,
    ProvenanceEntry,
    ScientificEntity,
)

logger = logging.getLogger(__name__)


@dataclass
class SynonymEntry:
    """A synonym entry from the registry.

    Attributes:
        canonical_id: Stable identifier (e.g. ``"pubchem:2244"``).
        canonical_name: Preferred display name.
        aliases: Known aliases for this entity.
        entity_type: The expected :class:`EntityType`.
    """

    canonical_id: str
    canonical_name: str
    aliases: list[str] = field(default_factory=list)
    entity_type: str = "unknown"


class EntityResolver(IEntityResolver):
    """Resolves aliases, assigns canonical IDs, and merges
    cross-provider duplicates.

    The resolver loads a synonym registry from a JSON file on startup
    (if available) and uses it to map entity names to canonical IDs.

    Graceful degradation: if the synonym file does not exist or is
    malformed, entities pass through without resolution.
    """

    def __init__(self, synonym_path: str | Path | None = None) -> None:
        """Initialise the resolver.

        Args:
            synonym_path: Path to ``synonyms.json``.  If *None* the
                built-in data file is used.  If the file does not exist
                the resolver starts with an empty registry.
        """
        self._synonym_registry: dict[str, SynonymEntry] = {}

        if synonym_path is None:
            synonym_path = Path(__file__).resolve().parent / "data" / "synonyms.json"

        path = Path(synonym_path)
        if path.exists():
            self._load_synonyms(path)
        else:
            logger.info("Synonym file not found at %s — starting empty", path)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def resolve(
        self, entities: list[ScientificEntity]
    ) -> list[ScientificEntity]:
        """Resolve entities to canonical form.

        Algorithm:
        1. For each entity, check if name or alias matches a known synonym.
        2. If matched: assign canonical_id, group under that ID.
        3. If no match: treat entity as its own canonical.
        4. Merge each group: pick best name, merge aliases, properties,
           relationships, provenance.
        5. Return deduplicated list.

        Args:
            entities: Entities from one or more providers.

        Returns:
            Resolved, deduplicated list of entities.
        """
        # Step 1: Group by canonical_id
        canonical_map: dict[str, list[ScientificEntity]] = {}

        for entity in entities:
            cid = self._resolve_canonical_id(entity)
            entity.canonical_id = cid
            canonical_map.setdefault(cid, []).append(entity)

        # Step 2: Merge each group
        resolved: list[ScientificEntity] = []
        for cid, group in canonical_map.items():
            merged = self._merge_group(cid, group)
            if merged:
                resolved.append(merged)

        return resolved

    # ------------------------------------------------------------------
    # Synonym registry
    # ------------------------------------------------------------------

    def _load_synonyms(self, path: Path) -> None:
        """Load synonym entries from a JSON file."""
        try:
            with open(path, "r", encoding="utf-8") as f:
                data: dict[str, Any] = json.load(f)

            for key, entry in data.items():
                synonyms = entry.get("aliases", [])
                if isinstance(synonyms, str):
                    synonyms = [synonyms]

                self._synonym_registry[key.lower()] = SynonymEntry(
                    canonical_id=entry.get("canonical_id", key),
                    canonical_name=entry.get("canonical_name", key),
                    aliases=synonyms,
                    entity_type=entry.get("entity_type", "unknown"),
                )

                # Also register each alias as a lookup key
                for alias in synonyms:
                    alias_lower = alias.lower().strip()
                    if alias_lower and alias_lower != key.lower():
                        self._synonym_registry[alias_lower] = SynonymEntry(
                            canonical_id=entry.get("canonical_id", key),
                            canonical_name=entry.get("canonical_name", key),
                            aliases=synonyms,
                            entity_type=entry.get("entity_type", "unknown"),
                        )

            logger.debug(
                "Loaded %d synonym entries from %s",
                len(self._synonym_registry),
                path,
            )

        except (FileNotFoundError, json.JSONDecodeError) as exc:
            logger.warning("Failed to load synonyms from %s: %s", path, exc)

    # ------------------------------------------------------------------
    # Resolution internals
    # ------------------------------------------------------------------

    def _resolve_canonical_id(self, entity: ScientificEntity) -> str:
        """Determine the canonical ID for *entity*.

        Priority:
        1. Exact name match in synonym registry.
        2. Any alias matches a synonym registry entry.
        3. Existing canonical_id on the entity.
        4. Existing source_id.
        5. Auto-generate from entity.id.
        """
        # Check name
        name_lower = entity.name.lower().strip()
        if name_lower in self._synonym_registry:
            return self._synonym_registry[name_lower].canonical_id

        # Check aliases
        for alias in entity.aliases:
            alias_lower = alias.lower().strip()
            if alias_lower in self._synonym_registry:
                return self._synonym_registry[alias_lower].canonical_id

        # Fall back to existing ID or generate
        if entity.canonical_id:
            return entity.canonical_id
        if entity.source_id:
            return f"{entity.source}:{entity.source_id}"
        return f"auto:{entity.id}"

    def _merge_group(
        self, canonical_id: str, group: list[ScientificEntity]
    ) -> ScientificEntity | None:
        """Merge a group of entities sharing a canonical ID into one.

        The best candidate is chosen by:
        - Finding an entry whose name matches the synonym registry's
          canonical name, or
        - Taking the entity with the highest confidence.
        """
        if not group:
            return None

        if len(group) == 1:
            return group[0]

        # Check if the canonical name from registry is available
        preferred_name: str | None = None
        preferred_type_str: str | None = None
        for entry in self._synonym_registry.values():
            if entry.canonical_id == canonical_id:
                preferred_name = entry.canonical_name
                preferred_type_str = entry.entity_type
                break

        # Sort by confidence descending, then by source existence
        sorted_group = sorted(
            group, key=lambda e: (e.confidence, 1 if e.source else 0), reverse=True
        )

        # Pick the base entity
        base = sorted_group[0]

        # Resolve name
        final_name = preferred_name or base.name

        # Resolve type
        if preferred_type_str:
            try:
                base.entity_type = EntityType(preferred_type_str)
            except ValueError:
                pass

        # Merge aliases (union, deduped)
        all_aliases: list[str] = [final_name]
        for ent in sorted_group:
            for alias in ent.aliases:
                if alias not in all_aliases:
                    all_aliases.append(alias)
        base.aliases = all_aliases

        # Merge properties (later overwrites earlier)
        merged_properties: dict[str, Any] = {}
        for ent in sorted_group:
            merged_properties.update(ent.properties)
        base.properties = merged_properties

        # Merge relationships (deduplicate by source+target+type)
        seen_rels: set[tuple[str, str, str]] = set()
        merged_rels: list[EntityRelationship] = []
        for ent in sorted_group:
            for rel in ent.relationships:
                key = (rel.source_id, rel.target_id, rel.relationship_type)
                if key not in seen_rels:
                    seen_rels.add(key)
                    merged_rels.append(rel)
        base.relationships = merged_rels

        # Merge provenance
        seen_sources: set[tuple[str, str]] = set()
        merged_sources: list[ProvenanceEntry] = []
        for ent in sorted_group:
            for src in ent.sources:
                key = (src.provider, src.source_id)
                if key not in seen_sources:
                    seen_sources.add(key)
                    merged_sources.append(src)
        base.sources = merged_sources

        # Confidence = max
        base.confidence = max(e.confidence for e in sorted_group)

        # Finalise
        base.name = final_name
        base.canonical_id = canonical_id

        return base
