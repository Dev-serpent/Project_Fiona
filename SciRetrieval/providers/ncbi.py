"""NCBI E-utilities provider.

Provides access to PubMed, Gene, Protein, and other NCBI databases
through the Entrez Programming Utilities API (esearch + esummary).

Supports **BIOLOGY** and **CHEMISTRY** domains.
"""

from __future__ import annotations

import logging
from typing import Any

from SciRetrieval.models import RawProviderResult, RetrievalContext
from SciRetrieval.providers.base import BaseProvider
from SciPhi.interfaces.model import ScientificDomain

logger = logging.getLogger(__name__)


class NCBIProvider(BaseProvider):
    """Provider for NCBI E-utilities (Entrez).

    Two-step fetch:
      1. ``esearch`` — find IDs matching the query.
      2. ``esummary`` — fetch summaries for those IDs.

    Args:
        tool: Name of the calling tool for NCBI usage stats.
        email: Contact email (NCBI requirement).
        timeout: Request timeout in seconds.
    """

    BASE_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"

    def __init__(
        self,
        tool: str = "FionaSciRetrieval",
        email: str = "fiona@localhost",
        timeout: float = 30.0,
    ) -> None:
        super().__init__(
            base_url=self.BASE_URL,
            timeout=timeout,
            user_agent=f"{tool}/0.1.0",
        )
        self._tool = tool
        self._email = email

    # ------------------------------------------------------------------
    # IProvider
    # ------------------------------------------------------------------

    @property
    def provider_name(self) -> str:
        return "ncbi"

    @property
    def supported_domains(self) -> frozenset[ScientificDomain]:
        return frozenset({ScientificDomain.BIOLOGY, ScientificDomain.CHEMISTRY})

    async def fetch(self, context: RetrievalContext) -> RawProviderResult:
        """Fetch data from NCBI for the given context.

        Returns a :class:`RawProviderResult` with the esummary JSON
        stored under the ``"result"`` key, plus metadata about the
        database searched.
        """
        db = self._select_db(context)
        query = context.query

        # Step 1: esearch
        search_params: dict[str, str | int] = {
            "db": db,
            "term": query,
            "retmax": "10",
            "retmode": "json",
            "tool": self._tool,
            "email": self._email,
        }
        search_data = await self._get("esearch.fcgi", params=search_params)

        id_list = search_data.get("esearchresult", {}).get("idlist", [])
        if not id_list:
            return RawProviderResult(
                provider=self.provider_name,
                raw_data={"result": [], "db": db},
                metadata={"database": db, "ids": []},
            )

        # Step 2: esummary
        summary_params: dict[str, str | int] = {
            "db": db,
            "id": ",".join(id_list),
            "retmode": "json",
            "tool": self._tool,
            "email": self._email,
        }
        summary_data = await self._get("esummary.fcgi", params=summary_params)

        return RawProviderResult(
            provider=self.provider_name,
            raw_data=dict(summary_data),
            metadata={
                "database": db,
                "ids": id_list,
                "query": query,
            },
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _select_db(context: RetrievalContext) -> str:
        """Choose the NCBI database based on the primary domain."""
        domains = context.domains
        if not domains:
            return "pubmed"
        primary = domains[0]
        if primary == ScientificDomain.BIOLOGY:
            return "gene"  # broad coverage for biology
        if primary == ScientificDomain.CHEMISTRY:
            return "pubmed"  # chemistry literature
        return "pubmed"
