"""Generalized plugin discovery and lifecycle management.

Extends the existing ``cad/plugins/`` pattern to all Fiona subsystems.

Usage:
    manager = PluginManager(search_paths=[...])
    manifests = manager.discover()
    manager.load_all()
"""

from __future__ import annotations

import importlib
import json
import os
import sys
import traceback
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Conditional YAML support
# ---------------------------------------------------------------------------

_HAS_YAML: bool = False
try:
    import yaml  # type: ignore[import-untyped]  # noqa: F811

    _HAS_YAML = True
except ImportError:  # pragma: no cover
    _HAS_YAML = False

# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PluginManifest:
    """Declarative metadata describing a plugin.

    Attributes:
        name: Unique plugin identifier (e.g. ``"stl-export"``).
        version: Semantic version string (e.g. ``"1.0.0"``).
        description: Short human-readable summary.
        author: Author or organisation name / email.
        entry_point: Dotted module path that the ``PluginManager``
            will import to obtain the plugin class (e.g.
            ``"fiona_plugins.stl_export"``).
    """

    name: str
    version: str = "0.1.0"
    description: str = ""
    author: str = ""
    entry_point: str = ""

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PluginManifest:
        """Construct a manifest from a parsed metadata dict.

        Args:
            data: Raw dict (e.g. from JSON / YAML).

        Returns:
            A ``PluginManifest`` instance.

        Raises:
            ValueError: If the required ``name`` field is missing.
        """
        name = data.get("name")
        if not name:
            raise ValueError("Plugin manifest is missing required field: 'name'")
        return cls(
            name=str(name),
            version=str(data.get("version", "0.1.0")),
            description=str(data.get("description", "")),
            author=str(data.get("author", "")),
            entry_point=str(data.get("entry_point", "")),
        )


# ---------------------------------------------------------------------------
# Plugin base class
# ---------------------------------------------------------------------------


class FionaPlugin(ABC):
    """Abstract base class for all Fiona plugins.

    Subclasses must implement ``manifest()``, ``activate()``, and
    ``deactivate()``.
    """

    @abstractmethod
    def manifest(self) -> PluginManifest:
        """Return the plugin's manifest (metadata)."""

    @abstractmethod
    def activate(self, container: Any) -> None:
        """Register services, commands, and providers with the system.

        Called once after the plugin is loaded.  Implementations should
        use the *container* (a ``fiona.di.FionaContainer`` or compatible
        object) to register any new services or extensions.

        Args:
            container: The dependency injection container.
        """

    @abstractmethod
    def deactivate(self) -> None:
        """Clean up resources and unregister services.

        Called when the plugin is unloaded.  Implementations should
        release any acquired resources (threads, file handles, network
        connections).
        """


# ---------------------------------------------------------------------------
# Plugin manager
# ---------------------------------------------------------------------------


class PluginError(Exception):
    """Raised when plugin loading, activation, or deactivation fails."""


class PluginManager:
    """Discovers, loads, and manages Fiona plugins.

    Plugins are discovered by scanning *search_paths* for subdirectories
    containing a ``plugin.json`` or ``plugin.yaml`` metadata file.  The
    metadata file declares the plugin's entry point module, which is
    imported using ``importlib``.

    Thread-safety: Not guaranteed — the caller should ensure that
    discovery / loading is performed from a single thread or under
    suitable external synchronisation.

    Attributes:
        search_paths: List of directory paths to scan for plugins.
        manifests: Mapping of plugin name → ``PluginManifest``
            (populated by ``discover()``).
        active_plugins: Mapping of plugin name → loaded ``FionaPlugin``
            instance.
    """

    def __init__(self, search_paths: list[str] | None = None) -> None:
        """Initialise the manager.

        Args:
            search_paths: List of filesystem paths to scan for plugins.
                Defaults to an empty list.
        """
        self.search_paths: list[str] = list(search_paths) if search_paths else []
        self.manifests: dict[str, PluginManifest] = {}
        self.active_plugins: dict[str, FionaPlugin] = {}

    # ------------------------------------------------------------------
    # Discovery
    # ------------------------------------------------------------------

    def discover(self) -> list[PluginManifest]:
        """Scan *search_paths* for plugin metadata files.

        For each subdirectory inside a search path, the method looks
        for a ``plugin.json`` or ``plugin.yaml`` file.  If found, it is
        parsed into a ``PluginManifest`` and stored.  Duplicate plugin
        names silently overwrite earlier entries (last-found wins).

        Returns:
            A list of all discovered ``PluginManifest`` instances.
        """
        discovered: list[PluginManifest] = []

        for search_path in self.search_paths:
            base = Path(search_path).expanduser().resolve()
            if not base.is_dir():
                continue

            for entry in sorted(base.iterdir()):
                if not entry.is_dir():
                    continue

                manifest = self._load_manifest_from_dir(entry)
                if manifest is not None:
                    self.manifests[manifest.name] = manifest
                    discovered.append(manifest)

        return list(discovered)

    @staticmethod
    def _load_manifest_from_dir(plugin_dir: Path) -> PluginManifest | None:
        """Try to read a manifest from a single plugin directory.

        Looks for ``plugin.json`` (preferred) or ``plugin.yaml``.

        Args:
            plugin_dir: Directory that may contain a plugin.

        Returns:
            A ``PluginManifest`` if found, else ``None``.
        """
        json_path = plugin_dir / "plugin.json"
        yaml_path = plugin_dir / "plugin.yaml"

        if json_path.is_file():
            try:
                with json_path.open("r", encoding="utf-8") as fh:
                    data = json.load(fh)
                return PluginManifest.from_dict(data)
            except (json.JSONDecodeError, ValueError, OSError):
                return None

        if _HAS_YAML and yaml_path.is_file():
            try:
                with yaml_path.open("r", encoding="utf-8") as fh:
                    data = yaml.safe_load(fh)
                if isinstance(data, dict):
                    return PluginManifest.from_dict(data)
            except (ValueError, OSError):
                return None

        return None

    # ------------------------------------------------------------------
    # Loading
    # ------------------------------------------------------------------

    def load(self, plugin_name: str) -> FionaPlugin:
        """Load and activate a plugin by name.

        The plugin must have been discovered first (see ``discover()``).

        Args:
            plugin_name: Name of the plugin to load (matching
                ``PluginManifest.name``).

        Returns:
            The activated ``FionaPlugin`` instance.

        Raises:
            PluginError: If the plugin is not found, its entry point
                cannot be imported, or activation fails.
        """
        if plugin_name in self.active_plugins:
            return self.active_plugins[plugin_name]

        manifest = self.manifests.get(plugin_name)
        if manifest is None:
            raise PluginError(
                f"Plugin {plugin_name!r} not found. "
                f"Call discover() first or check the name."
            )

        plugin = self._import_plugin(manifest)

        try:
            plugin.activate(self)  # the container-compatible interface
        except Exception as exc:
            raise PluginError(
                f"Failed to activate plugin {plugin_name!r}: {exc}"
            ) from exc

        self.active_plugins[plugin_name] = plugin
        return plugin

    def load_all(self) -> list[FionaPlugin]:
        """Discover and load every available plugin.

        Shortcut for calling ``discover()`` followed by ``load()`` for
        each discovered manifest.

        Returns:
            A list of successfully activated ``FionaPlugin`` instances.
        """
        self.discover()
        loaded: list[FionaPlugin] = []
        for name in list(self.manifests.keys()):
            try:
                loaded.append(self.load(name))
            except PluginError:
                # Log and skip — a single broken plugin should not
                # prevent others from loading.
                traceback.print_exc()
        return loaded

    # ------------------------------------------------------------------
    # Unloading
    # ------------------------------------------------------------------

    def unload(self, plugin_name: str) -> None:
        """Deactivate and unload a previously loaded plugin.

        Args:
            plugin_name: Name of the plugin to unload.

        Raises:
            PluginError: If deactivation raises an error.
        """
        plugin = self.active_plugins.pop(plugin_name, None)
        if plugin is None:
            return  # idempotent — nothing to do

        try:
            plugin.deactivate()
        except Exception as exc:
            raise PluginError(
                f"Failed to deactivate plugin {plugin_name!r}: {exc}"
            ) from exc

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _import_plugin(manifest: PluginManifest) -> FionaPlugin:
        """Import the entry point module and locate the ``FionaPlugin``
        subclass.

        Args:
            manifest: Plugin manifest containing the entry point.

        Returns:
            An instance of the plugin class.

        Raises:
            PluginError: If the module cannot be imported or does not
                contain a valid ``FionaPlugin`` subclass.
        """
        entry_point = manifest.entry_point
        if not entry_point:
            raise PluginError(
                f"Plugin {manifest.name!r} has no entry_point in manifest"
            )

        try:
            module = importlib.import_module(entry_point)
        except ImportError as exc:
            raise PluginError(
                f"Cannot import entry point {entry_point!r} "
                f"for plugin {manifest.name!r}: {exc}"
            ) from exc

        # Locate a FionaPlugin subclass (not FionaPlugin itself).
        plugin_class = None
        for attr_name in dir(module):
            obj = getattr(module, attr_name)
            if (
                isinstance(obj, type)
                and issubclass(obj, FionaPlugin)
                and obj is not FionaPlugin
            ):
                plugin_class = obj
                break

        if plugin_class is None:
            raise PluginError(
                f"No FionaPlugin subclass found in module "
                f"{entry_point!r} (plugin {manifest.name!r})"
            )

        try:
            return plugin_class()
        except Exception as exc:
            raise PluginError(
                f"Failed to instantiate plugin {manifest.name!r}: {exc}"
            ) from exc

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def get_plugin(self, name: str) -> FionaPlugin | None:
        """Return a loaded plugin by name, or ``None`` if not loaded.

        Args:
            name: Plugin name.

        Returns:
            The loaded ``FionaPlugin`` instance, or ``None``.
        """
        return self.active_plugins.get(name)

    def __repr__(self) -> str:
        return (
            f"PluginManager("
            f"{len(self.manifests)} manifests, "
            f"{len(self.active_plugins)} active)"
        )
