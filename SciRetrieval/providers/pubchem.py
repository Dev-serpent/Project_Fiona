"""PubChem PUG REST provider.

Accesses PubChem's compound, substance, and assay databases through
the Power User Gateway (PUG) REST interface at
https://pubchem.ncbi.nlm.nih.gov/rest/pug.

Supports **CHEMISTRY** and **BIOLOGY** domains.
"""

from __future__ import annotations

import logging
import re
from typing import Any

from SciRetrieval.models import RawProviderResult, RetrievalContext
from SciRetrieval.providers.base import BaseProvider
from SciPhi.interfaces.model import ScientificDomain

logger = logging.getLogger(__name__)


class PubChemProvider(BaseProvider):
    """Provider for PubChem PUG REST API.

    Automatically detects the input type (CID, name, SMILES) and
    queries the appropriate endpoint.
    """

    BASE_URL = "https://pubchem.ncbi.nlm.nih.gov/rest/pug"

    def __init__(self, timeout: float = 30.0) -> None:
        super().__init__(base_url=self.BASE_URL, timeout=timeout)

    # ------------------------------------------------------------------
    # IProvider
    # ------------------------------------------------------------------

    @property
    def provider_name(self) -> str:
        return "pubchem"

    @property
    def supported_domains(self) -> frozenset[ScientificDomain]:
        return frozenset({ScientificDomain.CHEMISTRY, ScientificDomain.BIOLOGY})

    async def fetch(self, context: RetrievalContext) -> RawProviderResult:
        """Fetch compound data from PubChem.

        The query is parsed heuristically to determine the identifier
        type (CID, name, or SMILES).  If parsing fails, the query is
        sent as a name search.
        """
        query = context.query.strip()

        # Try to identify the input type
        id_type, identifier = self._parse_identifier(query)

        if id_type == "cid":
            path = f"compound/cid/{identifier}/JSON"
        elif id_type == "smiles":
            path = f"compound/smiles/{identifier}/JSON"
        else:
            # Default: name search
            path = f"compound/name/{identifier}/JSON"

        try:
            data = await self._get(path)
        except Exception:
            # Fallback: try name search if CID/SMILES parsing was wrong
            logger.debug(
                "PubChem query failed with id_type=%s, retrying as name", id_type
            )
            path = f"compound/name/{_urlencode_name(query)}/JSON"
            data = await self._get(path)

        return RawProviderResult(
            provider=self.provider_name,
            raw_data=dict(data),
            metadata={
                "id_type": id_type,
                "identifier": identifier,
                "query": query,
            },
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_identifier(query: str) -> tuple[str, str]:
        """Heuristically determine identifier type.

        Returns:
            A tuple of ``(id_type, identifier)`` where ``id_type`` is
            one of ``"cid"``, ``"smiles"``, or ``"name"``.
        """
        q = query.strip()

        # Pure digits → CID
        if q.isdigit():
            return "cid", q

        # PubChem CID prefix
        cid_match = re.match(r"^(?:cid|pubchem)[:\s]*(\d+)$", q, re.IGNORECASE)
        if cid_match:
            return "cid", cid_match.group(1)

        # SMILES heuristic: contains typical organic chemistry characters
        # but no spaces, and at least one of C, O, N, etc.
        if (
            re.match(r"^[A-Za-z0-9@+\-\[\]\(\)\\/=#\.]+$", q)
            and re.search(r"[CONPSconps]", q)
            and " " not in q
            and len(q) > 2
        ):
            return "smiles", q

        # Default: treat as name
        return "name", q


def _urlencode_name(name: str) -> str:
    """Basic URL-safe encoding for compound names."""
    import urllib.parse
    return urllib.parse.quote(name, safe="")
