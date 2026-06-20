"""Plugin manager — load, unload, and discover plugins."""

from __future__ import annotations

import importlib
import inspect
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

from cad.commands.registry import CommandRegistry
from cad.core.document import Document


class PluginError(Exception):
    """Raised when plugin loading or execution fails."""


class Plugin(ABC):
    """Base class for all CAD plugins.

    A plugin can:
    - Register commands
    - Register geometry types
    - Register importers/exporters
    - Register UI panels
    - Subscribe to events
    """

    @property
    @abstractmethod
    def name(self) -> str: ...

    @property
    def version(self) -> str:
        return "0.1.0"

    def on_load(self, context: PluginContext) -> None:
        """Called when the plugin is loaded."""
        pass

    def on_unload(self, context: PluginContext) -> None:
        """Called when the plugin is unloaded."""
        pass


class PluginContext:
    """Context provided to plugins at load time."""

    def __init__(self, registry: CommandRegistry, plugin_dir: Path) -> None:
        self.registry = registry
        self.plugin_dir = plugin_dir


class PluginManager:
    """Manages plugin lifecycle — discovery, loading, unloading."""

    def __init__(self, registry: CommandRegistry,
                 plugin_dirs: list[Path] | None = None) -> None:
        self.registry = registry
        self._plugin_dirs = plugin_dirs or []
        self._plugins: dict[str, Plugin] = {}

    def add_plugin_dir(self, path: Path) -> None:
        if path.exists() and path.is_dir():
            self._plugin_dirs.append(path)

    def discover_plugins(self) -> list[str]:
        """Scan plugin directories for discoverable plugins."""
        discovered: list[str] = []
        for plugin_dir in self._plugin_dirs:
            for entry in plugin_dir.iterdir():
                if entry.suffix == ".py" and not entry.name.startswith("_"):
                    module_name = entry.stem
                    if module_name not in self._plugins:
                        discovered.append(module_name)
        return discovered

    def load_plugin(self, module_name: str) -> Plugin:
        """Load a plugin from a Python module."""
        if module_name in self._plugins:
            return self._plugins[module_name]

        try:
            module = importlib.import_module(module_name)
        except ImportError as exc:
            raise PluginError(f"Cannot import plugin '{module_name}': {exc}") from exc

        # Find Plugin subclass in module
        plugin_class = None
        for name, cls in inspect.getmembers(module, inspect.isclass):
            if issubclass(cls, Plugin) and cls is not Plugin:
                plugin_class = cls
                break

        if plugin_class is None:
            raise PluginError(f"No Plugin subclass found in '{module_name}'")

        plugin = plugin_class()
        context = PluginContext(self.registry,
                                Path(module.__file__).parent if module.__file__ else Path())
        plugin.on_load(context)
        self._plugins[plugin.name] = plugin
        return plugin

    def load_plugin_from_path(self, path: Path) -> Plugin:
        """Load a plugin from a specific file path."""
        module_name = path.stem
        # Add parent to sys.path temporarily
        import sys
        parent = str(path.parent)
        if parent not in sys.path:
            sys.path.insert(0, parent)
        return self.load_plugin(module_name)

    def unload_plugin(self, name: str) -> None:
        """Unload a plugin by name."""
        plugin = self._plugins.pop(name, None)
        if plugin:
            context = PluginContext(self.registry, Path())
            plugin.on_unload(context)

    def get_plugin(self, name: str) -> Plugin | None:
        return self._plugins.get(name)

    @property
    def plugins(self) -> dict[str, Plugin]:
        return dict(self._plugins)

    def __repr__(self) -> str:
        return f"PluginManager({len(self._plugins)} plugins)"
