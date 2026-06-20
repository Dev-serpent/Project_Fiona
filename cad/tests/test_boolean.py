"""Tests for boolean operations on solids."""

from __future__ import annotations

import unittest

from cad.core.document import Document
from cad.geometry.primitives import Box
from cad.geometry.boolean import BooleanOperation, boolean_union, boolean_difference, boolean_intersect


class TestBooleanOperations(unittest.TestCase):
    def setUp(self) -> None:
        self.doc = Document("test")
        self.box_a = Box("BoxA")
        self.box_b = Box("BoxB")
        self.doc.add_object(self.box_a)
        self.doc.add_object(self.box_b)

    def test_boolean_union(self) -> None:
        op = boolean_union(self.box_a, self.box_b)
        self.doc.add_object(op)
        self.assertEqual(op.get_property_value("operation"), "union")
        self.assertIn(str(self.box_a.uid), op.get_dependencies())
        self.assertIn(str(self.box_b.uid), op.get_dependencies())

    def test_boolean_difference(self) -> None:
        op = boolean_difference(self.box_a, self.box_b)
        self.doc.add_object(op)
        self.assertEqual(op.get_property_value("operation"), "difference")

    def test_boolean_intersect(self) -> None:
        op = boolean_intersect(self.box_a, self.box_b)
        self.doc.add_object(op)
        self.assertEqual(op.get_property_value("operation"), "intersect")

    def test_boolean_object_count(self) -> None:
        op = boolean_union(self.box_a, self.box_b)
        self.doc.add_object(op)
        self.assertEqual(op.get_property_value("object_count"), 2)

    def test_boolean_recompute_clears_dirty(self) -> None:
        op = boolean_union(self.box_a, self.box_b)
        self.doc.add_object(op)
        self.assertTrue(op.is_dirty())
        self.doc.recompute()
        self.assertFalse(op.is_dirty())

    def test_boolean_readonly_property(self) -> None:
        op = boolean_union(self.box_a, self.box_b)
        self.doc.add_object(op)
        # object_count should be readonly
        prop = op.get_property("object_count")
        self.assertTrue(prop.readonly)

    def test_boolean_naming(self) -> None:
        op = boolean_union(self.box_a, self.box_b)
        self.assertIn("Union", op.name)
        op2 = boolean_difference(self.box_a, self.box_b)
        self.assertIn("Difference", op2.name)


if __name__ == "__main__":
    unittest.main()
