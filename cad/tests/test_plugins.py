"""Tests for the plugin system."""

from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from cad.commands.registry import CommandRegistry
from cad.plugins.manager import PluginManager, Plugin, PluginContext, PluginError


class TestPluginSystem(unittest.TestCase):
    def setUp(self) -> None:
        self.registry = CommandRegistry()
        self.manager = PluginManager(self.registry)

    def test_create_manager(self) -> None:
        self.assertEqual(len(self.manager.plugins), 0)

    def test_add_plugin_dir(self) -> None:
        with TemporaryDirectory() as tmp:
            path = Path(tmp)
            self.manager.add_plugin_dir(path)
            # Add same dir again (should be idempotent)
            self.manager.add_plugin_dir(path)

    def test_add_plugin_dir_nonexistent(self) -> None:
        """Adding a non-existent directory should be silently ignored."""
        self.manager.add_plugin_dir(Path("/nonexistent/path"))
        # No crash

    def test_discover_plugins_empty(self) -> None:
        discovered = self.manager.discover_plugins()
        self.assertEqual(len(discovered), 0)

    def test_discover_plugins(self) -> None:
        with TemporaryDirectory() as tmp:
            dir_path = Path(tmp)
            # Create a plugin file
            plugin_file = dir_path / "test_plugin.py"
            plugin_file.write_text("""
from cad.plugins.manager import Plugin

class TestPlugin(Plugin):
    @property
    def name(self):
        return "test_plugin"
    
    @property
    def version(self):
        return "1.0.0"
    
    def on_load(self, context):
        pass
""")
            self.manager.add_plugin_dir(dir_path)
            discovered = self.manager.discover_plugins()
            self.assertIn("test_plugin", discovered)

    def test_discover_skips_private(self) -> None:
        with TemporaryDirectory() as tmp:
            dir_path = Path(tmp)
            (dir_path / "_private.py").write_text("# private")
            self.manager.add_plugin_dir(dir_path)
            discovered = self.manager.discover_plugins()
            self.assertNotIn("_private", discovered)

    def test_load_nonexistent_plugin(self) -> None:
        with self.assertRaises(PluginError):
            self.manager.load_plugin("does_not_exist_module")

    def test_load_plugin_no_subclass(self) -> None:
        with TemporaryDirectory() as tmp:
            mod_path = Path(tmp) / "bad_plugin.py"
            mod_path.write_text("# No Plugin subclass")
            import sys
            sys.path.insert(0, tmp)
            try:
                with self.assertRaises(PluginError):
                    self.manager.load_plugin("bad_plugin")
            finally:
                sys.path.remove(tmp)

    def test_load_plugin_from_path(self) -> None:
        with TemporaryDirectory() as tmp:
            plugin_path = Path(tmp) / "good_plugin.py"
            plugin_path.write_text("""
from cad.plugins.manager import Plugin

class GoodPlugin(Plugin):
    @property
    def name(self):
        return "good_plugin"
    
    def on_load(self, context):
        self.loaded = True
""")
            plugin = self.manager.load_plugin_from_path(plugin_path)
            self.assertEqual(plugin.name, "good_plugin")

    def test_load_twice_returns_cached(self) -> None:
        with TemporaryDirectory() as tmp:
            plugin_path = Path(tmp) / "cached_plugin.py"
            plugin_path.write_text("""
from cad.plugins.manager import Plugin

class CachedPlugin(Plugin):
    @property
    def name(self):
        return "cached_plugin"
""")
            self.manager.add_plugin_dir(Path(tmp))
            # module_name needs to match the stem
            import sys
            sys.path.insert(0, tmp)
            try:
                p1 = self.manager.load_plugin("cached_plugin")
                p2 = self.manager.load_plugin("cached_plugin")
                self.assertIs(p1, p2)
            finally:
                sys.path.remove(tmp)

    def test_unload_plugin(self) -> None:
        with TemporaryDirectory() as tmp:
            plugin_path = Path(tmp) / "unload_plugin.py"
            plugin_path.write_text("""
from cad.plugins.manager import Plugin

class UnloadPlugin(Plugin):
    @property
    def name(self):
        return "unload_plugin"
    
    def on_unload(self, context):
        self.unloaded = True
""")
            import sys
            sys.path.insert(0, tmp)
            try:
                self.manager.load_plugin("unload_plugin")
                self.assertIn("unload_plugin", self.manager.plugins)
                self.manager.unload_plugin("unload_plugin")
                self.assertNotIn("unload_plugin", self.manager.plugins)
            finally:
                sys.path.remove(tmp)

    def test_unload_nonexistent(self) -> None:
        # Should not crash
        self.manager.unload_plugin("nonexistent")

    def test_get_plugin(self) -> None:
        self.assertIsNone(self.manager.get_plugin("nonexistent"))

    def test_plugin_default_version(self) -> None:
        with TemporaryDirectory() as tmp:
            plugin_path = Path(tmp) / "ver_plugin.py"
            plugin_path.write_text("""
from cad.plugins.manager import Plugin

class VerPlugin(Plugin):
    @property
    def name(self):
        return "ver_plugin"
""")
            import sys
            sys.path.insert(0, tmp)
            try:
                plugin = self.manager.load_plugin("ver_plugin")
                self.assertEqual(plugin.version, "0.1.0")
            finally:
                sys.path.remove(tmp)


class TestPluginContext(unittest.TestCase):
    def test_context_creation(self) -> None:
        registry = CommandRegistry()
        ctx = PluginContext(registry, Path("/tmp/plugins"))
        self.assertIs(ctx.registry, registry)
        self.assertEqual(ctx.plugin_dir, Path("/tmp/plugins"))


if __name__ == "__main__":
    unittest.main()
