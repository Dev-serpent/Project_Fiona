"""Tests for the command system."""

from __future__ import annotations

import unittest

from cad.core.document import Document, new_document
from cad.commands.registry import CommandRegistry
from cad.commands.builtins import register_builtin_commands
from cad.geometry.primitives import Box, Cylinder, Sphere, Line, Circle


class TestCommandExecution(unittest.TestCase):
    def setUp(self) -> None:
        self.doc = new_document("test")
        self.registry = CommandRegistry()
        register_builtin_commands(self.registry)

    def test_create_box_command(self) -> None:
        result = self.registry.execute("create_box", self.doc,
                                       width=10, height=20, depth=30,
                                       name="MyBox")
        self.assertIsInstance(result, Box)
        self.assertEqual(result.get_property_value("width"), 10)
        self.assertEqual(result.get_property_value("height"), 20)
        self.assertEqual(result.get_property_value("depth"), 30)
        self.assertEqual(self.doc.object_count, 1)

    def test_create_cylinder_command(self) -> None:
        result = self.registry.execute("create_cylinder", self.doc,
                                       radius=5, height=15)
        self.assertIsInstance(result, Cylinder)

    def test_create_sphere_command(self) -> None:
        result = self.registry.execute("create_sphere", self.doc, radius=10)
        self.assertIsInstance(result, Sphere)

    def test_list_objects(self) -> None:
        self.registry.execute("create_box", self.doc, name="Box1")
        self.registry.execute("create_cylinder", self.doc, name="Cyl1")
        result = self.registry.execute("list_objects", self.doc)
        self.assertEqual(len(result), 2)
        names = [r["name"] for r in result]
        self.assertIn("Box1", names)
        self.assertIn("Cyl1", names)

    def test_command_aliases(self) -> None:
        box = self.registry.execute("box", self.doc, name="B")
        self.assertIsInstance(box, Box)

        cyl = self.registry.execute("cylinder", self.doc, name="C")
        self.assertIsInstance(cyl, Cylinder)

    def test_unknown_command(self) -> None:
        with self.assertRaises(Exception):
            self.registry.execute("nonexistent", self.doc)

    def test_recompute(self) -> None:
        self.registry.execute("create_box", self.doc, name="Box1")
        self.registry.execute("recompute", self.doc)
        # Should not raise


class TestCommandList(unittest.TestCase):
    def test_registered_commands(self) -> None:
        registry = CommandRegistry()
        register_builtin_commands(registry)
        names = registry.list_names()
        self.assertIn("create_box", names)
        self.assertIn("create_cylinder", names)
        self.assertIn("create_sphere", names)
        self.assertIn("list_objects", names)
        self.assertIn("recompute", names)
        self.assertGreater(len(names), 5)


if __name__ == "__main__":
    unittest.main()
