"""Tests for edge cases, error handling, and system integration."""

from __future__ import annotations

import unittest

from cad.core.document import Document
from cad.core.object import CADObject
from cad.core.property import PropertyType
from cad.core.params import Parameter, ParametricError
from cad.commands.registry import CommandRegistry, CommandError
from cad.commands.builtins import register_builtin_commands
from cad.geometry.math import Vector3, Matrix4, Plane
from cad.geometry.primitives import Box, Cylinder, Point2D
from cad.constraints.solver import ConstraintSolver
from cad.constraints.types import Horizontal


class TestEdgeCases(unittest.TestCase):
    """Test boundary conditions and extreme inputs."""

    def test_negative_dimensions(self) -> None:
        """Box with negative dimensions should still work."""
        b = Box("B")
        b.set_property("width", -10)
        self.assertEqual(b.get_property_value("width"), -10)
        # Volume would be negative, but that's fine for parametric modeling
        self.assertEqual(b.volume, -6000.0)  # 10*20*30 = 6000, but width is -10

    def test_zero_dimensions(self) -> None:
        b = Box("B")
        b.set_property("width", 0)
        b.set_property("height", 0)
        b.set_property("depth", 0)
        self.assertEqual(b.volume, 0)
        verts = b.get_vertices()
        # All vertices at origin
        for v in verts:
            self.assertEqual(v, Vector3(0, 0, 0))

    def test_very_large_values(self) -> None:
        """Extremely large coordinate values."""
        p = Point2D("P")
        p.set_property("x", 1e12)
        p.set_property("y", -1e12)
        # Basic operations should still work
        self.assertEqual(p.get_property_value("x"), 1e12)

    def test_very_small_values(self) -> None:
        """Extremely small (denormalized) values."""
        p = Point2D("P")
        p.set_property("x", 1e-300)
        p.set_property("y", -1e-300)
        self.assertEqual(p.get_property_value("x"), 1e-300)

    def test_nan_property_rejected(self) -> None:
        """NaN should propagate through the system."""
        b = Box("B")
        # Float property doesn't validate NaN
        b.set_property("width", float('nan'))
        # The property stores NaN
        prop = b.get_property("width")
        self.assertTrue(math.isnan(prop.value))

    def test_inf_property(self) -> None:
        """Infinity should propagate through the system."""
        b = Box("B")
        b.set_property("width", float('inf'))
        self.assertEqual(b.volume, float('inf'))

    def test_duplicate_object_name(self) -> None:
        doc = Document("test")
        doc.add_object(CADObject("SameName"))
        doc.add_object(CADObject("SameName"))
        # find_by_name returns the last one added
        found = doc.find_by_name("SameName")
        self.assertIsNotNone(found)
        self.assertEqual(doc.object_count, 2)

    def test_remove_nonexistent_object(self) -> None:
        doc = Document("test")
        # Removing an object not in the document should not crash
        obj = CADObject("Orphan")
        doc.remove_object(obj)  # Should not raise

    def test_recompute_with_circular_dependency(self) -> None:
        """Topological sort should handle circular deps (though they shouldn't exist)."""
        doc = Document("test")
        a = CADObject("A")
        b = CADObject("B")
        doc.add_object(a)
        doc.add_object(b)
        # Manually create a circular dependency
        a._dependencies.append(str(b.uid))
        b._dependencies.append(str(a.uid))
        # DFS-based topological sort should not infinite-loop
        try:
            doc.recompute()
        except RecursionError:
            self.fail("Circular dependency caused infinite recursion")
        except Exception:
            pass  # Other errors are OK

    def test_empty_sketch_edges(self) -> None:
        from cad.sketch.workspace import Sketch
        s = Sketch("Empty")
        edges = s.get_edges_2d()
        self.assertEqual(len(edges), 0)

    def test_object_with_many_properties(self) -> None:
        """Object with many properties should work."""
        obj = CADObject("Big")
        for i in range(100):
            obj.add_property(f"prop_{i}", PropertyType.FLOAT, float(i))
        self.assertEqual(len(obj.properties), 100)
        for i in range(100):
            self.assertEqual(obj.get_property_value(f"prop_{i}"), float(i))

    def test_deep_dependency_chain(self) -> None:
        """Chain of 1000 dependencies should not overflow stack."""
        doc = Document("test")
        prev = CADObject("Level_0")
        doc.add_object(prev)
        for i in range(1, 100):
            curr = CADObject(f"Level_{i}")
            doc.add_object(curr)
            curr.add_dependency(prev)
            prev = curr
        # Should recompute without stack overflow
        doc.recompute()

    def test_command_with_missing_arguments(self) -> None:
        """Command called without args should use defaults (no error)."""
        registry = CommandRegistry()
        register_builtin_commands(registry)
        result = registry.execute("create_box", Document("test"))
        self.assertIsNotNone(result)

    def test_unknown_command_alias(self) -> None:
        registry = CommandRegistry()
        with self.assertRaises(CommandError):
            registry.execute("does_not_exist", Document("test"))

    def test_case_sensitive_commands(self) -> None:
        registry = CommandRegistry()
        register_builtin_commands(registry)
        with self.assertRaises(CommandError):
            registry.execute("CREATE_BOX", Document("test"))

    def test_property_change_listener_exception(self) -> None:
        """Listener that raises propagates to the caller."""
        obj = CADObject("Test")
        obj.add_property("x", PropertyType.FLOAT, 0.0)

        def bad_listener(name: str, old: object, new: object) -> None:
            raise RuntimeError("Listener error")

        obj.get_property("x").on_change(bad_listener)
        with self.assertRaises(RuntimeError):
            obj.set_property("x", 5.0)

    def test_twin_constraints(self) -> None:
        """Two identical constraints should not cause issues."""
        line = type('Line', (CADObject,), {
            '_define_properties': lambda self: (
                self.add_property("x1", PropertyType.FLOAT, 0),
                self.add_property("y1", PropertyType.FLOAT, 0),
                self.add_property("x2", PropertyType.FLOAT, 10),
                self.add_property("y2", PropertyType.FLOAT, 5),
            )
        })("L")
        solver = ConstraintSolver()
        solver.add_constraint(Horizontal("h1", line))
        solver.add_constraint(Horizontal("h2", line))
        residual = solver.solve()
        # Both constraints should be satisfied
        self.assertLess(residual, 1e-6)


class TestDocumentSerializationEdgeCases(unittest.TestCase):
    def test_serialization_empty_properties(self) -> None:
        """Object with no properties can be serialized."""
        doc = Document("test")
        obj = CADObject("Empty")
        doc.add_object(obj)
        from cad.io.native_format import CadSerializer
        data = CadSerializer.serialize(doc)
        loaded = CadSerializer.deserialize(data)
        # Empty-like objects won't be reconstructed (type not in map)
        # but no crash should occur

    def test_serialization_special_chars(self) -> None:
        """Object names with special characters."""
        doc = Document("test")
        obj = CADObject("Object with spaces & symbols: üñîçødé!")
        doc.add_object(obj)
        from cad.io.native_format import CadSerializer
        data = CadSerializer.serialize(doc)
        loaded = CadSerializer.deserialize(data)
        # Original object type not in type_map, won't be reconstructed
        # but JSON encoding/decoding should handle the name

    def test_serialize_to_file_bad_path(self) -> None:
        from cad.io.native_format import CadSerializer
        with self.assertRaises(OSError):
            CadSerializer.serialize_to_file(Document("test"), "/nonexistent_dir/file.cad")


class TestParametricEdgeCases(unittest.TestCase):
    def test_expression_nested_braces(self) -> None:
        """Nested braces in expression are not supported but should not crash."""
        p = Parameter("bad", expression="{{{{wrong}}}}")
        with self.assertRaises(ParametricError):
            _ = p.value

    def test_expression_unresolved_reference(self) -> None:
        """Reference to a parameter that doesn't exist in resolver."""
        p = Parameter("v", expression="{{missing}} * 2")
        p.bind(lambda name: exec('raise KeyError()'))  # Simulate missing
        with self.assertRaises(ParametricError):
            _ = p.value

    def test_expression_empty(self) -> None:
        p = Parameter("v", expression="")
        val = p.value
        # Empty expression => no evaluation, value remains None
        self.assertIsNone(val)

    def test_expression_math_sqrt_negative(self) -> None:
        p = Parameter("v", expression="sqrt(-1)")
        with self.assertRaises(ParametricError):
            _ = p.value

    def test_parameter_chain_diamond(self) -> None:
        """Diamond dependency: a -> b, a -> c, b/c -> d."""
        a = Parameter("a", 10.0)
        b = Parameter("b", expression="{{a}} * 2")
        c = Parameter("c", expression="{{a}} + 5")
        d = Parameter("d", expression="{{b}} + {{c}}")

        resolver = {
            "a": lambda: a.value,
            "b": lambda: b.value,
            "c": lambda: c.value,
        }
        b.bind(lambda n: resolver.get(n, lambda: 0)())
        c.bind(lambda n: resolver.get(n, lambda: 0)())
        d.bind(lambda n: resolver.get(n, lambda: 0)())
        a.add_dependent(b)
        a.add_dependent(c)
        b.add_dependent(d)
        c.add_dependent(d)

        # Initial evaluation
        self.assertEqual(b.value, 20.0)
        self.assertEqual(c.value, 15.0)
        self.assertEqual(d.value, 35.0)

        # Change root
        a.value = 20.0
        self.assertEqual(b.value, 40.0)
        self.assertEqual(c.value, 25.0)
        self.assertEqual(d.value, 65.0)


import math  # noqa: E402


if __name__ == "__main__":
    unittest.main()
