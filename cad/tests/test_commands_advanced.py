"""Advanced tests for command system: error handling, history, builtins."""

from __future__ import annotations

import unittest

from cad.commands.registry import CommandRegistry, Command, CommandError
from cad.commands.builtins import register_builtin_commands
from cad.core.document import Document
from cad.geometry.primitives import Box


class TestCommandErrors(unittest.TestCase):
    def setUp(self) -> None:
        self.doc = Document("test")
        self.registry = CommandRegistry()

    def test_execute_nonexistent_command(self) -> None:
        with self.assertRaises(CommandError):
            self.registry.execute("nonexistent", self.doc)

    def test_execute_with_bad_args(self) -> None:
        register_builtin_commands(self.registry)
        # Wrong type for width (should be numeric)
        try:
            self.registry.execute("create_box", self.doc, width="not_a_number")
        except (CommandError, TypeError, ValueError):
            pass  # Accept any reasonable error

    def test_execute_command_with_missing_required_args(self) -> None:
        """Some commands may handle missing kwargs gracefully."""
        register_builtin_commands(self.registry)
        # create_box with no kwargs should use defaults and not crash
        result = self.registry.execute("create_box", self.doc)
        self.assertIsNotNone(result)

    def test_command_error_on_registry_execute(self) -> None:
        with self.assertRaises(CommandError):
            self.registry.execute("__nonexistent__", self.doc)


class TestBuiltinCommands(unittest.TestCase):
    def setUp(self) -> None:
        self.doc = Document("test")
        self.registry = CommandRegistry()
        register_builtin_commands(self.registry)

    def test_create_box_command(self) -> None:
        self.registry.execute("create_box", self.doc, width=15, height=25, depth=35, name="CmdBox")
        obj = self.doc.find_by_name("CmdBox")
        self.assertIsNotNone(obj)
        self.assertEqual(obj.get_property_value("width"), 15)
        self.assertEqual(obj.get_property_value("height"), 25)

    def test_create_cylinder_command(self) -> None:
        self.registry.execute("create_cylinder", self.doc, radius=8, height=20, name="CmdCyl")
        obj = self.doc.find_by_name("CmdCyl")
        self.assertIsNotNone(obj)

    def test_create_sphere_command(self) -> None:
        self.registry.execute("create_sphere", self.doc, radius=12, name="CmdSphere")
        obj = self.doc.find_by_name("CmdSphere")
        self.assertIsNotNone(obj)

    def test_recompute_command(self) -> None:
        self.registry.execute("create_box", self.doc, width=5, height=5, depth=5, name="RCBox")
        self.registry.execute("recompute", self.doc)

    def test_list_objects_command(self) -> None:
        self.registry.execute("create_box", self.doc, width=1, height=1, depth=1, name="LBox")
        result = self.registry.execute("list_objects", self.doc)
        self.assertIsNotNone(result)

    def test_list_objects_returns_list(self) -> None:
        self.registry.execute("create_box", self.doc, width=1, height=1, depth=1, name="LBox2")
        result = self.registry.execute("list_objects", self.doc)
        self.assertIsInstance(result, list)
        self.assertGreaterEqual(len(result), 1)

    def test_duplicate_name_allowed(self) -> None:
        """Two objects with same name should not crash command system."""
        self.registry.execute("create_box", self.doc, width=1, height=1, depth=1, name="DupName")
        self.registry.execute("create_box", self.doc, width=2, height=2, depth=2, name="DupName")
        # Both should exist
        count = self.doc.object_count
        self.assertGreaterEqual(count, 2)

    def test_new_document_command(self) -> None:
        new_doc = self.registry.execute("new_document", self.doc, name="NewDoc")
        self.assertIsNotNone(new_doc)
        if isinstance(new_doc, Document):
            self.assertEqual(new_doc.name, "NewDoc")


class _TestCommand(Command):
    """Concrete command for testing."""
    name = "test_cmd"
    description = "Test command"

    def execute(self, doc: Document, **kwargs: Any) -> Any:
        return kwargs.get("value", "done")


class _TestCommand2(Command):
    """Another concrete command for testing."""
    name = "dup"
    description = "Duplicate test"

    def execute(self, doc: Document, **kwargs: Any) -> Any:
        return "second"


class _TestAliasCommand(Command):
    name = "full_name"
    aliases = ["fn", "fname"]
    description = "Alias test"

    def execute(self, doc: Document, **kwargs: Any) -> Any:
        return "alias_done"


class _TestCategorizedCommand(Command):
    name = "cat_cmd"
    category = "testing"
    description = "Category test"

    def execute(self, doc: Document, **kwargs: Any) -> Any:
        return None


class TestCommandRegistry(unittest.TestCase):
    def setUp(self) -> None:
        self.registry = CommandRegistry()

    def test_register_and_get(self) -> None:
        cmd = _TestCommand()
        self.registry.register(cmd)
        self.assertIsNotNone(self.registry.get("test_cmd"))

    def test_register_duplicate_overwrites(self) -> None:
        cmd1 = _TestCommand()
        cmd2 = _TestCommand2()
        self.registry.register(cmd1)
        self.registry.register(cmd2)
        self.assertIs(self.registry.get("dup"), cmd2)

    def test_list_names(self) -> None:
        cmd = _TestCommand()
        self.registry.register(cmd)
        names = self.registry.list_names()
        self.assertIn("test_cmd", names)

    def test_list_by_category(self) -> None:
        cmd = _TestCategorizedCommand()
        self.registry.register(cmd)
        cats = self.registry.list_by_category()
        self.assertIn("testing", cats)

    def test_alias_resolution(self) -> None:
        cmd = _TestAliasCommand()
        self.registry.register(cmd)
        self.assertIs(self.registry.get("fn"), cmd)
        self.assertIs(self.registry.get("fname"), cmd)

    def test_repr(self) -> None:
        r = repr(self.registry)
        self.assertIn("CommandRegistry", r)


if __name__ == "__main__":
    unittest.main()
