"""ChemResolver tool — resolves chemical names/identifiers via PubChem.

Uses ``aiohttp`` to query the PubChem PUG REST API.  If ``aiohttp``
is not installed the tool raises ``MissingDependencyError`` at runtime.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from fiona.tools.interfaces import ITool
from fiona.tools.models import ToolCategory, ToolContext, ToolResult, ToolSpec

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Optional aiohttp import
# ---------------------------------------------------------------------------
try:
    import aiohttp

    HAS_AIOHTTP = True
except ImportError:
    HAS_AIOHTTP = False
    aiohttp = None  # type: ignore[assignment]

PUBCHEM_BASE = "https://pubchem.ncbi.nlm.nih.gov/rest/pug"
TIMEOUT_SECONDS = 10.0


class ChemResolver(ITool):
    """Resolves a chemical query (name, SMILES, or CID) via the PubChem API.

    Returns structured information including formula, molecular weight,
    SMILES, and IUPAC name.
    """

    @property
    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="resolve_chemical",
            description=(
                "Look up a chemical compound by name, SMILES, or PubChem CID "
                "and return its formula, molecular weight, canonical SMILES, "
                "and IUPAC name."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": (
                            "Chemical name (e.g. 'aspirin'), SMILES string, "
                            "or PubChem CID."
                        ),
                    },
                },
                "required": ["query"],
            },
            category=ToolCategory.CHEMISTRY,
        )

    async def run(
        self, context: ToolContext, **kwargs: object
    ) -> ToolResult:
        """Execute the chemical lookup.

        Args:
            context: Execution context with logger.
            **kwargs: Must contain ``query`` (str).

        Returns:
            :class:`ToolResult` with structured chemical information.
        """
        if not HAS_AIOHTTP:
            return ToolResult(
                success=False,
                content="",
                error=(
                    "aiohttp is required for ChemResolver. "
                    "Install with: pip install fiona[sciretrieval]"
                ),
            )

        query = kwargs.get("query")
        if not query:
            return ToolResult(
                success=False,
                content="",
                error="Missing required argument: 'query'",
            )

        query_str = str(query).strip()
        if not query_str:
            return ToolResult(
                success=False,
                content="",
                error="Query string is empty",
            )

        try:
            data = await self._fetch_pubchem(query_str, context)
            formatted = self._format_result(data, query_str)
            return ToolResult(
                success=True,
                content=formatted,
                metadata={
                    "query": query_str,
                    "cid": data.get("id", {}).get("id", {}).get("CID"),
                },
            )
        except Exception as exc:
            context.logger.warning(
                "chem_resolver failed for %r: %s", query_str, exc
            )
            return ToolResult(
                success=False,
                content="",
                error=f"Chemical lookup failed: {exc}",
            )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    async def _fetch_pubchem(
        self, query: str, context: ToolContext
    ) -> dict[str, Any]:
        """Query PubChem PUG REST and return the compound JSON."""
        id_type, identifier = self._parse_identifier(query)
        path = f"compound/{id_type}/{self._urlencode(identifier)}/JSON"

        url = f"{PUBCHEM_BASE}/{path}"
        context.logger.debug("ChemResolver GET %s", url)

        timeout = aiohttp.ClientTimeout(total=TIMEOUT_SECONDS)  # type: ignore[arg-type]
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(
                url,
                headers={"User-Agent": "FionaSciTool/0.1.0"},
            ) as resp:
                if resp.status == 404:
                    raise ValueError(
                        f"Compound not found: {query!r}"
                    )
                if resp.status >= 400:
                    text = await resp.text()
                    raise ValueError(
                        f"PubChem returned HTTP {resp.status}: {text[:200]}"
                    )
                raw = await resp.json()

        # Navigate the PUG JSON structure
        pc_compounds = raw.get("PC_Compounds", [])
        if not pc_compounds:
            raise ValueError(f"No compound data returned for {query!r}")

        return pc_compounds[0]

    @staticmethod
    def _parse_identifier(query: str) -> tuple[str, str]:
        """Heuristically determine the identifier type for the PubChem URL.

        Returns:
            ``(id_type, identifier)`` where ``id_type`` is one of
            ``"cid"``, ``"smiles"``, or ``"name"``.
        """
        import re

        q = query.strip()

        # Pure digits -> CID
        if q.isdigit():
            return "cid", q

        # Explicit prefix
        cid_match = re.match(
            r"^(?:cid|pubchem)[:\s]*(\d+)$", q, re.IGNORECASE
        )
        if cid_match:
            return "cid", cid_match.group(1)

        # SMILES heuristic
        if (
            re.match(r"^[A-Za-z0-9@+\-\[\]\(\)\\/=#\.]+$", q)
            and re.search(r"[CONPSconps]", q)
            and " " not in q
            and len(q) > 2
        ):
            return "smiles", q

        return "name", q

    @staticmethod
    def _urlencode(name: str) -> str:
        """Basic URL-safe encoding for compound names."""
        import urllib.parse

        return urllib.parse.quote(name, safe="")

    @staticmethod
    def _format_result(data: dict[str, Any], query: str) -> str:
        """Format the PubChem compound data into a readable string."""
        props = data.get("props", [])

        def _find_prop(urn_label: str) -> str | None:
            """Search props list for a matching URN label."""
            for p in props:
                urn = p.get("urn", {})
                if urn.get("label") == urn_label:
                    val = p.get("value", {})
                    # Try string value first, then number value
                    sval = val.get("sval")
                    if sval:
                        return sval
                    bval = val.get("bval")
                    if bval is not None:
                        return str(bval)
                    fval = val.get("fval")
                    if fval is not None:
                        return str(fval)
                    ival = val.get("ival")
                    if ival is not None:
                        return str(ival)
            return None

        cid = data.get("id", {}).get("id", {}).get("CID", "?")
        formula = _find_prop("Molecular Formula") or "?"
        mol_weight = _find_prop("Molecular Weight") or "?"
        smiles = _find_prop("Canonical SMILES") or _find_prop("SMILES") or "?"
        iupac_name = (
            _find_prop("IUPAC Name")
            or _find_prop("Preferred IUPAC Name")
            or "?"
        )

        lines = [
            f"Query: {query}",
            f"PubChem CID: {cid}",
            f"Molecular Formula: {formula}",
            f"Molecular Weight: {mol_weight}",
            f"Canonical SMILES: {smiles}",
            f"IUPAC Name: {iupac_name}",
        ]
        return "\n".join(lines)
