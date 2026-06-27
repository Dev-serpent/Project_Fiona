"""NIST Chemistry WebBook provider.

Provides access to thermochemical, spectroscopic, and physical
property data via the NIST WebBook at
https://webbook.nist.gov/cgi/cbook.cgi.

Supports **CHEMISTRY**, **PHYSICS**, and **ENGINEERING** domains.

Note: NIST returns HTML, not JSON.  The raw HTML is stored in the
``raw_data`` dict under the ``"html"`` key.
"""

from __future__ import annotations

import logging
from typing import Any

from SciRetrieval.models import RawProviderResult, RetrievalContext
from SciRetrieval.providers.base import BaseProvider
from SciPhi.interfaces.model import ScientificDomain

logger = logging.getLogger(__name__)


class NISTProvider(BaseProvider):
    """Provider for the NIST Chemistry WebBook.

    Queries the cbook.cgi endpoint with the compound name and stores
    the full HTML response for later parsing by the normalizer.
    """

    BASE_URL = "https://webbook.nist.gov/cgi/cbook.cgi"

    def __init__(self, timeout: float = 30.0) -> None:
        super().__init__(base_url=self.BASE_URL, timeout=timeout)

    # ------------------------------------------------------------------
    # IProvider
    # ------------------------------------------------------------------

    @property
    def provider_name(self) -> str:
        return "nist"

    @property
    def supported_domains(self) -> frozenset[ScientificDomain]:
        return frozenset(
            {
                ScientificDomain.CHEMISTRY,
                ScientificDomain.PHYSICS,
                ScientificDomain.ENGINEERING,
            }
        )

    async def fetch(self, context: RetrievalContext) -> RawProviderResult:
        """Fetch compound data from NIST WebBook.

        The query is sent as the ``Name`` parameter.  The raw HTML
        response is stored in the result so the normaliser can extract
        structured data from it.
        """
        query = context.query.strip()

        # NIST CGI takes a 'Name' parameter
        params: dict[str, str | int] = {
            "Name": query,
            "Units": "SI",
        }

        html_text = await self._get_text("", params=params)

        return RawProviderResult(
            provider=self.provider_name,
            raw_data={"html": html_text},
            metadata={
                "query": query,
                "content_type": "text/html",
            },
        )
