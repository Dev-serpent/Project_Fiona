"""Tests for the assembly system."""

from __future__ import annotations

import unittest

from cad.core.document import Document, new_document
from cad.assembly.assembly import Assembly, PartInstance, AssemblyConstraint
from cad.geometry.primitives import Box


class TestAssembly(unittest.TestCase):
    def setUp(self) -> None:
        self.doc = new_document("test")

    def test_create_assembly(self) -> None:
        assembly = Assembly("MainAssembly")
        self.doc.add_object(assembly)
        self.assertEqual(assembly.name, "MainAssembly")

    def test_add_part_to_assembly(self) -> None:
        assembly = Assembly("Main")
        self.doc.add_object(assembly)

        box = Box("Base")
        self.doc.add_object(box)

        part = PartInstance("BasePart", source=box)
        part.set_property("px", 10)
        part.set_property("py", 20)
        assembly.add_part(part)

        self.assertEqual(len(assembly.parts), 1)
        self.assertEqual(assembly.parts[0].name, "BasePart")

    def test_add_subassembly(self) -> None:
        main = Assembly("Main")
        sub = Assembly("Sub")
        main.add_subassembly(sub)
        self.assertEqual(len(main.subassemblies), 1)

    def test_add_constraint(self) -> None:
        assembly = Assembly("Main")
        part_a = PartInstance("A")
        part_b = PartInstance("B")
        assembly.add_part(part_a)
        assembly.add_part(part_b)

        constraint = AssemblyConstraint("Mate", part_a, part_b, "coincident")
        assembly.add_constraint(constraint)

        self.assertEqual(len(assembly.constraints), 1)
        self.assertEqual(constraint.get_property_value("type"), "coincident")

    def test_get_all_parts(self) -> None:
        main = Assembly("Main")
        sub = Assembly("Sub")
        main.add_subassembly(sub)

        part1 = PartInstance("Part1")
        part2 = PartInstance("Part2")
        main.add_part(part1)
        sub.add_part(part2)

        all_parts = main.get_all_parts()
        self.assertEqual(len(all_parts), 2)

    def test_part_transform(self) -> None:
        part = PartInstance("Test")
        part.set_property("px", 5)
        part.set_property("py", 10)
        part.set_property("pz", 15)
        transform = part.get_transform()
        from cad.geometry.math import Vector3
        p = transform.transform_point(Vector3(0, 0, 0))
        self.assertAlmostEqual(p.x, 5)
        self.assertAlmostEqual(p.y, 10)
        self.assertAlmostEqual(p.z, 15)


if __name__ == "__main__":
    unittest.main()
