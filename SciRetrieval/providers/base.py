"""Base provider with common HTTP / retry / error-handling logic.

All SciRetrieval data providers inherit from :class:`BaseProvider`,
which provides:

* Asynchronous HTTP requests via ``aiohttp`` (or a clear error if
  the optional dependency is missing).
* Timeout, rate-limit, and connection-error handling mapped to the
  provider error hierarchy.
* A convenience ``_get()`` method for JSON endpoints and
  ``_get_text()`` for plain-text / HTML responses.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from SciRetrieval.errors import (
    ProviderConnectionError,
    ProviderDataError,
    ProviderRateLimitedError,
    ProviderTimeoutError,
)
from SciRetrieval.interfaces import IProvider

logger = logging.getLogger(__name__)

# Attempt to import aiohttp; fall back to a stub that raises on use.
try:
    import aiohttp

    HAS_AIOHTTP = True
    AiohttpClientError = aiohttp.ClientError
except ImportError:  # pragma: no cover
    HAS_AIOHTTP = False
    aiohttp = None  # type: ignore[assignment]
    AiohttpClientError = Exception  # fallback so except clauses still compile


class BaseProvider(IProvider):
    """Base class for scientific data providers.

    Subclasses must set ``provider_name`` and ``supported_domains`` and
    implement :meth:`fetch`.

    Args:
        base_url: The root URL for the provider's API.
        timeout: Default request timeout in seconds.
        user_agent: User-Agent header value.
        session: Optional pre-existing ``aiohttp.ClientSession``.
    """

    def __init__(
        self,
        base_url: str,
        timeout: float = 30.0,
        user_agent: str | None = None,
        session: aiohttp.ClientSession | None = None,  # type: ignore[name-defined]
    ) -> None:
        if not HAS_AIOHTTP:
            raise ImportError(
                "aiohttp is required for SciRetrieval providers. "
                "Install with: pip install fiona[sciretrieval]"
            )
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout
        self._user_agent = user_agent or "FionaSciRetrieval/0.1.0"
        self._session = session
        self._owns_session = session is None

    # ------------------------------------------------------------------
    # Public helpers
    # ------------------------------------------------------------------

    async def _get(
        self,
        path: str,
        params: dict[str, str | int] | None = None,
        headers: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        """Perform an HTTP GET and parse the response as JSON.

        Args:
            path: URL path relative to ``base_url``.
            params: Query-string parameters.
            headers: Additional HTTP headers.

        Returns:
            Parsed JSON response as a dict.

        Raises:
            ProviderConnectionError: Network / HTTP error.
            ProviderTimeoutError: Request timed out.
            ProviderRateLimitedError: 429 response.
            ProviderDataError: Non-JSON or unexpected status.
        """
        session = await self._get_session()
        url = f"{self._base_url}/{path.lstrip('/')}"
        req_headers = {"User-Agent": self._user_agent, **(headers or {})}

        try:
            async with session.get(
                url, params=params, headers=req_headers, timeout=aiohttp.ClientTimeout(total=self._timeout)  # type: ignore[arg-type]
            ) as resp:
                if resp.status == 429:
                    raise ProviderRateLimitedError(
                        f"Rate limited by {self.provider_name} (429)"
                    )
                if resp.status >= 400:
                    text = await resp.text()
                    raise ProviderConnectionError(
                        f"{self.provider_name} returned HTTP {resp.status}: {text[:200]}"
                    )
                try:
                    return dict(await resp.json())
                except (ValueError, TypeError) as exc:
                    raise ProviderDataError(
                        f"{self.provider_name} returned non-JSON data: {exc}"
                    ) from exc
        except asyncio.TimeoutError as exc:
            raise ProviderTimeoutError(
                f"{self.provider_name} request timed out after {self._timeout}s"
            ) from exc
        except AiohttpClientError as exc:
            raise ProviderConnectionError(
                f"{self.provider_name} connection error: {exc}"
            ) from exc

    async def _get_text(
        self,
        path: str,
        params: dict[str, str | int] | None = None,
        headers: dict[str, str] | None = None,
    ) -> str:
        """Perform an HTTP GET and return the raw response text.

        Useful for providers that return HTML (e.g. NIST).

        Raises:
            Same as :meth:`_get`.
        """
        session = await self._get_session()
        url = f"{self._base_url}/{path.lstrip('/')}"
        req_headers = {"User-Agent": self._user_agent, **(headers or {})}

        try:
            async with session.get(
                url, params=params, headers=req_headers, timeout=aiohttp.ClientTimeout(total=self._timeout)  # type: ignore[arg-type]
            ) as resp:
                if resp.status == 429:
                    raise ProviderRateLimitedError(
                        f"Rate limited by {self.provider_name} (429)"
                    )
                if resp.status >= 400:
                    text = await resp.text()
                    raise ProviderConnectionError(
                        f"{self.provider_name} returned HTTP {resp.status}: {text[:200]}"
                    )
                return await resp.text()
        except asyncio.TimeoutError as exc:
            raise ProviderTimeoutError(
                f"{self.provider_name} request timed out after {self._timeout}s"
            ) from exc
        except AiohttpClientError as exc:
            raise ProviderConnectionError(
                f"{self.provider_name} connection error: {exc}"
            ) from exc

    # ------------------------------------------------------------------
    # Session management
    # ------------------------------------------------------------------

    async def _get_session(self) -> aiohttp.ClientSession:  # type: ignore[name-defined]
        """Return the shared ``aiohttp.ClientSession``, creating it if needed."""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()  # type: ignore[assignment]
            self._owns_session = True
        return self._session

    async def close(self) -> None:
        """Close the underlying HTTP session if we own it."""
        if self._owns_session and self._session is not None and not self._session.closed:
            await self._session.close()

    # ------------------------------------------------------------------
    # Abstract stubs
    # ------------------------------------------------------------------

    @property
    def provider_name(self) -> str:
        """Subclasses must override this."""
        raise NotImplementedError

    @property
    def supported_domains(self) -> frozenset:  # type: ignore[override]
        """Subclasses must override this."""
        raise NotImplementedError

    async def fetch(self, context: "RetrievalContext") -> "RawProviderResult":  # type: ignore[override]
        """Subclasses must override this."""
        raise NotImplementedError
