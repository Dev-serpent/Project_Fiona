"""Provider-specific normalisation adapters.

Each provider that returns data in a unique format needs an adapter
that converts its ``RawProviderResult.raw_data`` into a list of
:class:`ScientificEntity` objects.

Adapters are registered by provider name and called by the
:class:`Normalizer` when processing raw results.
"""

from __future__ import annotations

import logging
import re
from typing import Any, Callable

from SciRetrieval.errors import NormalizationError
from SciRetrieval.interfaces import INormalizer
from SciRetrieval.models import (
    EntityType,
    ProvenanceEntry,
    RawProviderResult,
    ScientificEntity,
)
from SciPhi.interfaces.model import ScientificDomain

logger = logging.getLogger(__name__)

# Type alias for an adapter function
AdapterFn = Callable[[dict[str, Any], dict[str, Any]], list[ScientificEntity]]


class Normalizer(INormalizer):
    """Converts raw provider responses into :class:`ScientificEntity` lists.

    Each provider must have a registered adapter function.
    Built-in adapters for ``pubchem``, ``ncbi``, and ``nist`` are
    registered at construction time.
    """

    def __init__(self) -> None:
        self._adapters: dict[str, AdapterFn] = {}
        self._register_builtins()

    def register_adapter(self, provider_name: str, adapter_fn: AdapterFn) -> None:
        """Register an adapter for *provider_name*.

        Args:
            provider_name: Must match ``IProvider.provider_name``.
            adapter_fn: A callable that receives ``(raw_data, metadata)``
                and returns a list of :class:`ScientificEntity`.
        """
        self._adapters[provider_name] = adapter_fn
        logger.debug("Registered normalizer adapter for %s", provider_name)

    async def normalize(self, raw: RawProviderResult) -> list[ScientificEntity]:
        """Normalise a single raw provider result.

        Args:
            raw: Raw data from a provider.

        Returns:
            A list of normalised entities (may be empty if no adapter
            exists or data is unparseable).
        """
        adapter = self._adapters.get(raw.provider)
        if adapter is None:
            logger.warning("No normalizer adapter for provider %s", raw.provider)
            return []

        try:
            entities = adapter(raw.raw_data, raw.metadata)
            # Stamp provenance on each entity
            for ent in entities:
                ent.source = raw.provider
                ent.sources.append(
                    ProvenanceEntry(
                        provider=raw.provider,
                        source_id=ent.source_id,
                        fields=list(ent.properties.keys()),
                    )
                )
            return entities
        except Exception as exc:
            raise NormalizationError(
                f"Failed to normalise data from {raw.provider}: {exc}"
            ) from exc

    # ------------------------------------------------------------------
    # Built-in adapters
    # ------------------------------------------------------------------

    def _register_builtins(self) -> None:
        self._adapters["pubchem"] = _normalize_pubchem
        self._adapters["ncbi"] = _normalize_ncbi
        self._adapters["nist"] = _normalize_nist


# ======================================================================
# Adapter implementations
# ======================================================================


def _normalize_pubchem(
    raw_data: dict[str, Any], metadata: dict[str, Any]
) -> list[ScientificEntity]:
    """Extract compounds from PubChem JSON.

    Expects the PubChem PUG REST compound JSON format with a
    ``PC_Compounds`` array.
    """
    compounds = raw_data.get("PC_Compounds") or raw_data.get("PC_CompoundsArray")
    if not compounds:
        # Some PubChem endpoints use a different structure
        if "Record" in raw_data:
            compounds = [raw_data]
        else:
            # Try to find any list value
            for val in raw_data.values():
                if isinstance(val, list) and val:
                    compounds = val
                    break
            if not compounds:
                return []

    entities: list[ScientificEntity] = []
    for comp in compounds if isinstance(compounds, list) else [compounds]:
        try:
            entity = _extract_pubchem_compound(comp)
            if entity:
                entities.append(entity)
        except Exception as exc:
            logger.debug("Skipping unparseable PubChem compound: %s", exc)
            continue

    return entities


def _extract_pubchem_compound(comp: dict[str, Any]) -> ScientificEntity | None:
    """Extract a single PubChem compound from its JSON object."""
    props: dict[str, Any] = {}

    # Navigate the nested PubChem JSON structure
    # Standard PC_Compound format:
    #   comp -> props -> [urn -> label, value -> sval/fval]
    #   comp -> id -> id -> cid

    cid: str = ""
    name: str = ""

    # CID
    try:
        cid_obj = comp.get("id", {})
        if isinstance(cid_obj, dict):
            cid = str(cid_obj.get("id", {}).get("CID", "") or cid_obj.get("id", ""))
    except Exception:
        pass

    # Properties array
    raw_props = comp.get("props", []) or comp.get("properties", [])
    if isinstance(raw_props, dict):
        raw_props = [raw_props]

    for prop in raw_props if isinstance(raw_props, list) else []:
        try:
            urn = prop.get("urn", {})
            label = urn.get("label", "")
            val = prop.get("value", {})
            # String value
            sval = val.get("sval") or val.get("stringVal") or val.get("sVal")
            # Float value
            fval = val.get("fval") or val.get("numberVal") or val.get("fVal")
            if sval:
                props[label] = sval
            elif fval is not None:
                props[label] = fval
        except Exception:
            continue

    # Name fallback: check IUPAC Name or synonym
    name = props.get("IUPAC Name", "")
    if not name:
        name = props.get("Synonym", metadata.get("identifier", ""))

    if not name and not cid:
        return None

    canonical_smiles = props.get("Canonical SMILES", "")
    inchikey = props.get("InChIKey", "")
    mw = props.get("Molecular Weight", "")
    mf = props.get("Molecular Formula", "")

    entity = ScientificEntity(
        canonical_id=f"pubchem:{cid}" if cid else "",
        name=name,
        entity_type=EntityType.CHEMICAL_COMPOUND,
        source="pubchem",
        source_id=cid,
        properties={
            "mw": mw,
            "mf": mf,
            "canonical_smiles": canonical_smiles,
            "inchikey": inchikey,
            "iupac_name": props.get("IUPAC Name", ""),
            "logp": props.get("Log P", ""),
        },
        domain=ScientificDomain.CHEMISTRY,
    )

    # Collect aliases from synonyms
    synonyms = props.get("Synonym", "")
    if synonyms and isinstance(synonyms, str):
        entity.aliases = [s.strip() for s in synonyms.split("|") if s.strip()]

    return entity


def _normalize_ncbi(
    raw_data: dict[str, Any], metadata: dict[str, Any]
) -> list[ScientificEntity]:
    """Extract entities from NCBI esummary JSON.

    Handles both ``result`` dict (keyed by UID) and flat list formats.
    """
    result = raw_data.get("result", {})
    if not result:
        return []

    entities: list[ScientificEntity] = []
    uids = metadata.get("ids", [])

    for uid in uids:
        try:
            uid_str = str(uid)
            entry = result.get(uid_str)
            if not entry or not isinstance(entry, dict):
                continue

            name = entry.get("name", "") or entry.get("title", "") or entry.get("description", "")
            if not name:
                continue

            # Determine entity type based on available fields
            etype = EntityType.UNKNOWN
            db = metadata.get("database", "")

            if db == "gene":
                etype = EntityType.GENE
            elif db == "protein":
                etype = EntityType.PROTEIN
            elif db == "pubmed":
                etype = EntityType.UNKNOWN  # literature reference
            elif "organism" in entry:
                etype = EntityType.PROTEIN
            elif "maplocation" in entry:
                etype = EntityType.GENE

            entity = ScientificEntity(
                canonical_id=f"ncbi:{uid_str}",
                name=name,
                entity_type=etype,
                source="ncbi",
                source_id=uid_str,
                properties={
                    "summary": entry.get("summary", ""),
                    "organism": entry.get("organism", ""),
                    "pubdate": entry.get("pubdate", ""),
                    "source": entry.get("source", ""),
                    "subtype": entry.get("subtype", ""),
                    "sourcedb": entry.get("sourcedb", ""),
                },
                domain=ScientificDomain.BIOLOGY,
            )

            # Add aliases
            aliases = entry.get("otheraliases", "") or entry.get("aliases", "")
            if aliases:
                if isinstance(aliases, str):
                    entity.aliases = [a.strip() for a in aliases.split(",") if a.strip()]
                elif isinstance(aliases, list):
                    entity.aliases = [str(a) for a in aliases]

            entities.append(entity)

        except Exception as exc:
            logger.debug("Skipping unparseable NCBI entry %s: %s", uid, exc)
            continue

    return entities


def _normalize_nist(
    raw_data: dict[str, Any], metadata: dict[str, Any]
) -> list[ScientificEntity]:
    """Extract basic compound info from NIST WebBook HTML.

    NIST returns HTML pages.  This adapter uses simple regex patterns
    to extract compound name, formula, and molecular weight from the
    page title and body content.
    """
    html = raw_data.get("html", "")
    if not html:
        return []

    entities: list[ScientificEntity] = []

    try:
        # Extract compound name from <title> tag
        title_match = re.search(r"<title>(.+?)</title>", html, re.IGNORECASE)
        name = ""
        if title_match:
            title_text = title_match.group(1)
            # Typical format: "Compound Name"
            name = title_text.split("(")[0].split("-")[0].strip()
            if not name or "webbook" in name.lower():
                name = ""

        # Extract molecular formula from page
        formula = ""
        mf_match = re.search(
            r"Molecular\s*(?:Formula|Weight)[:\s]*</strong>\s*([^<]+)",
            html,
            re.IGNORECASE,
        )
        if mf_match:
            formula = mf_match.group(1).strip()

        # Extract molecular weight
        mw = ""
        mw_match = re.search(
            r"Molecular\s*weight[:\s]*</strong>\s*([^<]+)",
            html,
            re.IGNORECASE,
        )
        if mw_match:
            mw = mw_match.group(1).strip()

        # Use query as fallback name
        if not name:
            name = metadata.get("query", "")

        if name:
            entity = ScientificEntity(
                name=name,
                entity_type=EntityType.CHEMICAL_COMPOUND,
                source="nist",
                source_id=name,
                properties={
                    "mw": mw,
                    "mf": formula,
                    "source_url": "https://webbook.nist.gov/cgi/cbook.cgi",
                },
                domain=ScientificDomain.CHEMISTRY,
            )
            entities.append(entity)

    except Exception as exc:
        logger.debug("Failed to parse NIST HTML: %s", exc)

    return entities
