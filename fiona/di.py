"""Simple service container for dependency injection.

Not a full DI framework — just enough to avoid global singletons
while remaining pytest-friendly.

Usage:
    container = FionaContainer()
    container.register_instance("config", config)
    container.register_factory("browser_provider", lambda: PlaywrightProvider())
    browser = container.resolve("browser_provider")
"""

from __future__ import annotations

import threading
from collections.abc import Callable
from typing import Any


class FionaContainer:
    """Lightweight dependency injection container.

    Supports registration of concrete instances and lazy-singleton
    factories.  All public methods are thread-safe.

    Attributes:
        _services: Mapping of service names to cached instances.
        _factories: Mapping of service names to factory callables.
        _lock: Reentrant lock guarding all mutations.
    """

    def __init__(self) -> None:
        """Initialise an empty container."""
        self._services: dict[str, Any] = {}
        self._factories: dict[str, Callable[[], Any]] = {}
        self._lock = threading.RLock()

    def register_instance(self, name: str, instance: Any) -> None:
        """Register a concrete instance under *name*.

        The instance is returned as-is on every ``resolve(name)`` call.

        Args:
            name: Unique service identifier.
            instance: The object to register.

        Raises:
            ValueError: If *name* is already registered (as instance or
                factory).
        """
        with self._lock:
            if name in self._services:
                raise ValueError(f"Service already registered as instance: {name}")
            if name in self._factories:
                raise ValueError(f"Service already registered as factory: {name}")
            self._services[name] = instance

    def register_factory(self, name: str, factory: Callable[[], Any]) -> None:
        """Register a *factory* that produces the service on first access.

        The factory is called at most once; the result is cached and
        returned for all subsequent ``resolve(name)`` calls (lazy
        singleton semantics).

        Args:
            name: Unique service identifier.
            factory: Zero-argument callable that returns the service.

        Raises:
            ValueError: If *name* is already registered (as instance or
                factory).
        """
        with self._lock:
            if name in self._services:
                raise ValueError(f"Service already registered as instance: {name}")
            if name in self._factories:
                raise ValueError(f"Service already registered as factory: {name}")
            self._factories[name] = factory

    def resolve(self, name: str) -> Any:
        """Return the service registered under *name*.

        If a factory was registered, it is invoked once and the result
        is cached for subsequent calls.

        Args:
            name: Service identifier to look up.

        Returns:
            The registered instance (or factory result).

        Raises:
            KeyError: If no service is registered under *name*.
        """
        with self._lock:
            # Fast path — already instantiated.
            if name in self._services:
                return self._services[name]

            # Lazy-init path — factory exists, call & cache.
            factory = self._factories.get(name)
            if factory is not None:
                instance = factory()
                self._services[name] = instance
                return instance

        raise KeyError(
            f"Service not registered: {name!r}. "
            f"Call register_instance() or register_factory() first."
        )

    def __contains__(self, name: str) -> bool:
        """Check if a service is registered (instance or factory).

        Args:
            name: Service identifier.

        Returns:
            True if the service can be resolved.
        """
        with self._lock:
            return name in self._services or name in self._factories

    def __repr__(self) -> str:
        with self._lock:
            instances = len(self._services)
            factories = len(self._factories)
        return f"FionaContainer({instances} instances, {factories} factories)"
