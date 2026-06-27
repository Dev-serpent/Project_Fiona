"""Registry that maps scientific domains to data providers.

Allows registering providers for specific domains and querying them
at retrieval time.
"""

from __future__ import annotations

import logging
from collections import defaultdict

from SciRetrieval.interfaces import IProvider
from SciPhi.interfaces.model import ScientificDomain

logger = logging.getLogger(__name__)


class ProviderRegistry:
    """Maps :class:`ScientificDomain` values to lists of :class:`IProvider`.

    Providers can be registered as *primary* (shortlisted first) or
    secondary.  The registry does not call providers — it only manages
    the mapping so the :class:`RetrievalManager` can select the right
    ones at query time.
    """

    def __init__(self) -> None:
        self._domain_map: dict[ScientificDomain, list[tuple[str, IProvider]]] = (
            defaultdict(list)
        )

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    def register(
        self,
        provider: IProvider,
        domains: list[ScientificDomain] | None = None,
        primary: bool = False,
    ) -> None:
        """Register a provider for one or more domains.

        Args:
            provider: An :class:`IProvider` implementation.
            domains: The domains this provider supports.  If *None* the
                provider's own ``supported_domains`` property is used.
            primary: If *True* the provider is inserted at index 0 so it
                is preferred over others for these domains.
        """
        domains = domains or list(provider.supported_domains)
        entry = (provider.provider_name, provider)
        for domain in domains:
            existing = self._domain_map[domain]
            if primary:
                # Insert at front, removing any previous occurrence
                self._domain_map[domain] = [
                    e for e in existing if e[0] != provider.provider_name
                ]
                self._domain_map[domain].insert(0, entry)
            else:
                if not any(e[0] == provider.provider_name for e in existing):
                    self._domain_map[domain].append(entry)

        logger.debug(
            "Registered provider %s for domains %s (primary=%s)",
            provider.provider_name,
            [d.name for d in domains],
            primary,
        )

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------

    def get_providers(self, domain: ScientificDomain) -> list[IProvider]:
        """Return all providers registered for *domain*.

        Returns:
            A list of :class:`IProvider` instances, ordered by
            registration priority (primaries first).
        """
        return [p for _, p in self._domain_map.get(domain, [])]

    def get_primary_provider(self, domain: ScientificDomain) -> IProvider | None:
        """Return the highest-priority (first registered) provider.

        Returns:
            The primary provider, or *None* if none are registered.
        """
        providers = self._domain_map.get(domain, [])
        if providers:
            return providers[0][1]
        return None

    def list_providers(self) -> dict[str, list[str]]:
        """Return a human-readable mapping for debugging.

        Returns:
            ``{provider_name: [domain_name, ...]}``
        """
        result: dict[str, list[str]] = {}
        for domain, entries in self._domain_map.items():
            for name, _ in entries:
                result.setdefault(name, []).append(domain.name)
        return result

    def find_by_name(self, name: str) -> IProvider | None:
        """Find a provider by its ``provider_name`` string.

        Args:
            name: The provider name to search for.

        Returns:
            The matching :class:`IProvider`, or *None*.
        """
        for entries in self._domain_map.values():
            for pname, provider in entries:
                if pname == name:
                    return provider
        return None
