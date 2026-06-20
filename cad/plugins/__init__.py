"""Plugin system — extend CAD with new commands, geometry, importers, and UI panels."""

from cad.plugins.manager import Plugin, PluginManager, PluginError

__all__ = ["Plugin", "PluginManager", "PluginError"]
