"""Tests for ProviderRegistry — registration, lookup, and ordering."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from SciRetrieval.provider_registry import ProviderRegistry
from SciPhi.interfaces.model import ScientificDomain


@pytest.fixture()
def registry() -> ProviderRegistry:
    return ProviderRegistry()


@pytest.fixture()
def bio_provider() -> MagicMock:
    m = MagicMock()
    m.provider_name = "bio_provider"
    m.supported_domains = frozenset({ScientificDomain.BIOLOGY})
    return m


@pytest.fixture()
def chem_provider() -> MagicMock:
    m = MagicMock()
    m.provider_name = "chem_provider"
    m.supported_domains = frozenset({ScientificDomain.CHEMISTRY})
    return m


@pytest.fixture()
def multi_domain_provider() -> MagicMock:
    m = MagicMock()
    m.provider_name = "multi_provider"
    m.supported_domains = frozenset(
        {ScientificDomain.BIOLOGY, ScientificDomain.CHEMISTRY}
    )
    return m


class TestRegistration:
    """Registering providers for domains."""

    def test_register_single_domain(
        self, registry: ProviderRegistry, bio_provider: MagicMock
    ) -> None:
        registry.register(bio_provider, [ScientificDomain.BIOLOGY])
        providers = registry.get_providers(ScientificDomain.BIOLOGY)
        assert len(providers) == 1
        assert providers[0] == bio_provider

    def test_register_uses_provider_default_domains(
        self, registry: ProviderRegistry, bio_provider: MagicMock
    ) -> None:
        """When domains is None, use provider.supported_domains."""
        registry.register(bio_provider)
        providers = registry.get_providers(ScientificDomain.BIOLOGY)
        assert len(providers) == 1

    def test_register_with_explicit_domains(
        self,
        registry: ProviderRegistry,
        bio_provider: MagicMock,
        chem_provider: MagicMock,
    ) -> None:
        """Explicit domains override provider defaults."""
        registry.register(bio_provider, [ScientificDomain.CHEMISTRY])
        providers = registry.get_providers(ScientificDomain.CHEMISTRY)
        assert len(providers) == 1
        assert providers[0] == bio_provider

    def test_register_same_provider_twice(
        self, registry: ProviderRegistry, bio_provider: MagicMock
    ) -> None:
        """Registering the same provider twice does not duplicate."""
        registry.register(bio_provider, [ScientificDomain.BIOLOGY])
        registry.register(bio_provider, [ScientificDomain.BIOLOGY])
        providers = registry.get_providers(ScientificDomain.BIOLOGY)
        assert len(providers) == 1

    def test_register_for_different_domains(
        self,
        registry: ProviderRegistry,
        multi_domain_provider: MagicMock,
    ) -> None:
        """Same provider can be registered for multiple domains."""
        registry.register(multi_domain_provider, [ScientificDomain.BIOLOGY])
        registry.register(multi_domain_provider, [ScientificDomain.CHEMISTRY])
        bio = registry.get_providers(ScientificDomain.BIOLOGY)
        chem = registry.get_providers(ScientificDomain.CHEMISTRY)
        assert len(bio) == 1
        assert len(chem) == 1


class TestPrimarySecondaryOrdering:
    """Primary vs secondary provider ordering."""

    def test_primary_first(
        self,
        registry: ProviderRegistry,
        bio_provider: MagicMock,
        chem_provider: MagicMock,
    ) -> None:
        """Primary providers appear first in the list."""
        registry.register(chem_provider, [ScientificDomain.BIOLOGY], primary=False)
        registry.register(bio_provider, [ScientificDomain.BIOLOGY], primary=True)
        providers = registry.get_providers(ScientificDomain.BIOLOGY)
        assert providers[0] == bio_provider  # primary first
        assert providers[1] == chem_provider

    def test_primary_replaces_existing(
        self,
        registry: ProviderRegistry,
        bio_provider: MagicMock,
        chem_provider: MagicMock,
    ) -> None:
        """Re-registering as primary moves it to front."""
        registry.register(chem_provider, [ScientificDomain.BIOLOGY], primary=False)
        registry.register(bio_provider, [ScientificDomain.BIOLOGY], primary=False)
        # Now promote bio to primary
        registry.register(bio_provider, [ScientificDomain.BIOLOGY], primary=True)
        providers = registry.get_providers(ScientificDomain.BIOLOGY)
        assert providers[0] == bio_provider

    def test_all_secondary_if_no_primary(
        self,
        registry: ProviderRegistry,
        bio_provider: MagicMock,
        chem_provider: MagicMock,
    ) -> None:
        """Without primary flag, order is insertion order."""
        registry.register(bio_provider, [ScientificDomain.BIOLOGY])
        registry.register(chem_provider, [ScientificDomain.BIOLOGY])
        providers = registry.get_providers(ScientificDomain.BIOLOGY)
        assert providers == [bio_provider, chem_provider]


class TestQuery:
    """Querying the registry."""

    def test_get_primary_provider(
        self, registry: ProviderRegistry, bio_provider: MagicMock
    ) -> None:
        registry.register(bio_provider, [ScientificDomain.BIOLOGY], primary=True)
        primary = registry.get_primary_provider(ScientificDomain.BIOLOGY)
        assert primary == bio_provider

    def test_get_primary_provider_no_registrations(
        self, registry: ProviderRegistry
    ) -> None:
        assert registry.get_primary_provider(ScientificDomain.BIOLOGY) is None

    def test_get_providers_no_registrations(
        self, registry: ProviderRegistry
    ) -> None:
        assert registry.get_providers(ScientificDomain.BIOLOGY) == []

    def test_list_providers(
        self,
        registry: ProviderRegistry,
        bio_provider: MagicMock,
        chem_provider: MagicMock,
    ) -> None:
        registry.register(bio_provider, [ScientificDomain.BIOLOGY])
        registry.register(chem_provider, [ScientificDomain.CHEMISTRY])
        listing = registry.list_providers()
        assert "bio_provider" in listing
        assert "chem_provider" in listing
        assert "BIOLOGY" in listing["bio_provider"]
        assert "CHEMISTRY" in listing["chem_provider"]

    def test_list_providers_empty(self, registry: ProviderRegistry) -> None:
        assert registry.list_providers() == {}

    def test_find_by_name(
        self, registry: ProviderRegistry, bio_provider: MagicMock
    ) -> None:
        registry.register(bio_provider, [ScientificDomain.BIOLOGY])
        found = registry.find_by_name("bio_provider")
        assert found == bio_provider

    def test_find_by_name_not_found(
        self, registry: ProviderRegistry
    ) -> None:
        assert registry.find_by_name("nonexistent") is None
