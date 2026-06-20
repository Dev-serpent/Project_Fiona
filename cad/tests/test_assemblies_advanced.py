"""Advanced tests for assemblies, sub-assemblies, and hierarchy."""

from __future__ import annotations

import unittest

from cad.core.document import Document
from cad.assembly.assembly import Assembly, PartInstance, AssemblyConstraint
from cad.geometry.primitives import Box


class TestAssemblyAdvanced(unittest.TestCase):
    def setUp(self) -> None:
        self.doc = Document("test")

    def test_create_assembly(self) -> None:
        assembly = Assembly("RootAssembly")
        self.doc.add_object(assembly)
        self.assertEqual(assembly.name, "RootAssembly")

    def test_add_part(self) -> None:
        assembly = Assembly("Assembly1")
        self.doc.add_object(assembly)
        part = PartInstance("Part1")
        assembly.add_part(part)
        self.assertEqual(len(assembly.parts), 1)

    def test_add_sub_assembly(self) -> None:
        parent = Assembly("Parent")
        child = Assembly("Child")
        self.doc.add_object(parent)
        self.doc.add_object(child)
        parent.add_subassembly(child)
        self.assertIn(child, parent.subassemblies)

    def test_get_all_parts_flat(self) -> None:
        assembly = Assembly("Assembly1")
        self.doc.add_object(assembly)
        part1 = PartInstance("Part1")
        part2 = PartInstance("Part2")
        assembly.add_part(part1)
        assembly.add_part(part2)
        all_parts = assembly.get_all_parts()
        self.assertEqual(len(all_parts), 2)

    def test_get_all_parts_nested(self) -> None:
        parent = Assembly("Parent")
        child = Assembly("Child")
        self.doc.add_object(parent)
        self.doc.add_object(child)
        parent.add_subassembly(child)
        child.add_part(PartInstance("NestedPart"))
        all_parts = parent.get_all_parts()
        self.assertEqual(len(all_parts), 1)

    def test_remove_part(self) -> None:
        assembly = Assembly("Assembly1")
        self.doc.add_object(assembly)
        part = PartInstance("Part1")
        assembly.add_part(part)
        assembly.remove_part("Part1")
        self.assertEqual(len(assembly.parts), 0)

    def test_add_constraint(self) -> None:
        assembly = Assembly("Assembly1")
        self.doc.add_object(assembly)
        part_a = PartInstance("PartA")
        part_b = PartInstance("PartB")
        assembly.add_part(part_a)
        assembly.add_part(part_b)
        constraint = AssemblyConstraint("Mate1", part_a, part_b, "coincident")
        assembly.add_constraint(constraint)
        self.assertEqual(len(assembly.constraints), 1)

    def test_property_counts(self) -> None:
        assembly = Assembly("Assembly1")
        self.doc.add_object(assembly)
        self.assertEqual(assembly.get_property_value("part_count"), 0)
        self.assertEqual(assembly.get_property_value("subassembly_count"), 0)
        self.assertEqual(assembly.get_property_value("constraint_count"), 0)

    def test_part_instance_placement(self) -> None:
        part = PartInstance("Part1")
        part.set_property("px", 100.0)
        part.set_property("py", 50.0)
        part.set_property("rz", 45.0)
        self.assertEqual(part.get_property_value("px"), 100.0)
        self.assertEqual(part.get_property_value("rz"), 45.0)

    def test_part_instance_default_values(self) -> None:
        part = PartInstance("DefaultPart")
        self.assertEqual(part.get_property_value("sx"), 1.0)
        self.assertEqual(part.get_property_value("sy"), 1.0)
        self.assertEqual(part.get_property_value("sz"), 1.0)

    def test_assembly_recompute(self) -> None:
        assembly = Assembly("Assembly1")
        self.doc.add_object(assembly)
        self.assertTrue(assembly.is_dirty())
        assembly.recompute()
        self.assertFalse(assembly.is_dirty())

    def test_assembly_to_dict(self) -> None:
        assembly = Assembly("Assembly1")
        self.doc.add_object(assembly)
        part = PartInstance("Part1")
        assembly.add_part(part)
        data = assembly.to_dict()
        self.assertEqual(data["name"], "Assembly1")
        self.assertEqual(len(data["parts"]), 1)

    def test_constraint_properties(self) -> None:
        part_a = PartInstance("PartA")
        part_b = PartInstance("PartB")
        constraint = AssemblyConstraint("Mate1", part_a, part_b, "coincident")
        self.assertEqual(constraint.get_property_value("type"), "coincident")
        self.assertTrue(constraint.get_property("type").readonly)

    def test_assembly_dependency_tracking(self) -> None:
        assembly = Assembly("Assembly1")
        self.doc.add_object(assembly)
        part = PartInstance("Part1")
        assembly.add_part(part)
        # The assembly should list the part as a dependency
        deps = assembly.get_dependencies()
        self.assertIn(str(part.uid), deps)

    def test_part_instance_with_source(self) -> None:
        source = Box("SourceBox")
        self.doc.add_object(source)
        instance = PartInstance("Instance", source=source)
        self.doc.add_object(instance)
        deps = instance.get_dependencies()
        self.assertIn(str(source.uid), deps)


if __name__ == "__main__":
    unittest.main()
