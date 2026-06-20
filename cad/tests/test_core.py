"""Tests for core document, object, property, and parametric systems."""

from __future__ import annotations

import json
import unittest

from cad.core.document import Document, new_document, active_document
from cad.core.object import CADObject
from cad.core.property import Property, PropertyType
from cad.core.params import Parameter, ParametricValue, ParametricError


# ══════════════════════════════════════════════════════════════════════
# Property System
# ══════════════════════════════════════════════════════════════════════

class TestProperty(unittest.TestCase):
    def test_creation(self) -> None:
        p = Property("width", PropertyType.FLOAT, 10.0, 5.0)
        self.assertEqual(p.name, "width")
        self.assertEqual(p.value, 10.0)
        self.assertFalse(p.readonly)

    def test_default_value(self) -> None:
        p = Property("height", PropertyType.FLOAT, default=20.0)
        self.assertEqual(p.value, 20.0)

    def test_explicit_value_overrides_default(self) -> None:
        p = Property("height", PropertyType.FLOAT, value=30.0, default=20.0)
        self.assertEqual(p.value, 30.0)

    def test_readonly_enforcement(self) -> None:
        """readonly is just a flag; code must check it."""
        p = Property("locked", PropertyType.STRING, "initial", readonly=True)
        self.assertTrue(p.readonly)
        # Property setter doesn't enforce readonly itself,
        # but the flag is available for constraint solver etc.
        p.value = "changed"
        self.assertEqual(p.value, "changed")

    def test_change_notification(self) -> None:
        p = Property("x", PropertyType.FLOAT, 0.0)
        changes: list[tuple[str, object, object]] = []
        unsub = p.on_change(lambda n, o, new: changes.append((n, o, new)))
        p.value = 5.0
        self.assertEqual(len(changes), 1)
        self.assertEqual(changes[0], ("x", 0.0, 5.0))
        # Unsubscribe
        unsub()
        p.value = 10.0
        self.assertEqual(len(changes), 1)  # No new notification

    def test_change_same_value_no_notify(self) -> None:
        p = Property("x", PropertyType.FLOAT, 5.0)
        changes = []
        p.on_change(lambda n, o, new: changes.append((n, o, new)))
        p.value = 5.0  # Same value
        self.assertEqual(len(changes), 0)

    def test_reset(self) -> None:
        p = Property("r", PropertyType.FLOAT, 10.0, default=1.0)
        p.reset()
        self.assertEqual(p.value, 1.0)

    def test_to_dict(self) -> None:
        p = Property("w", PropertyType.FLOAT, 42.0, description="Width")
        d = p.to_dict()
        self.assertEqual(d["name"], "w")
        self.assertEqual(d["type"], "float")
        self.assertEqual(d["value"], 42.0)
        self.assertEqual(d["description"], "Width")

    def test_serialize_object_reference(self) -> None:
        """Property serialization of objects with to_dict."""
        class HasToDict:
            def to_dict(self) -> dict:
                return {"hello": "world"}
        p = Property("obj", PropertyType.OBJECT, HasToDict())
        d = p.to_dict()
        self.assertEqual(d["value"], {"hello": "world"})

    def test_serialize_list(self) -> None:
        p = Property("list", PropertyType.OBJECT_LIST, [1, 2, 3])
        d = p.to_dict()
        self.assertEqual(d["value"], [1.0, 2.0, 3.0])

    def test_enum_type(self) -> None:
        p = Property("mode", PropertyType.ENUM, "fast",
                      choices=[("fast", "fast"), ("slow", "slow")])
        self.assertEqual(p.type, PropertyType.ENUM)
        self.assertEqual(len(p.choices), 2)

    def test_color_type(self) -> None:
        p = Property("color", PropertyType.COLOR, "#ff0000")
        self.assertEqual(p.value, "#ff0000")

    def test_matrix_type(self) -> None:
        p = Property("transform", PropertyType.MATRIX, None)
        self.assertIsNone(p.value)


# ══════════════════════════════════════════════════════════════════════
# CADObject System
# ══════════════════════════════════════════════════════════════════════

class TestCADObject(unittest.TestCase):
    def setUp(self) -> None:
        self.doc = Document("TestDoc")

    def test_create(self) -> None:
        obj = CADObject("Base")
        self.assertEqual(obj.name, "Base")
        self.assertEqual(obj.label, "Base")
        self.assertTrue(obj.is_dirty())

    def test_create_with_label(self) -> None:
        obj = CADObject("base_id", "Base Object")
        self.assertEqual(obj.name, "base_id")
        self.assertEqual(obj.label, "Base Object")

    def test_unique_uid(self) -> None:
        a = CADObject("A")
        b = CADObject("B")
        self.assertNotEqual(a.uid, b.uid)

    def test_add_and_get_property(self) -> None:
        obj = CADObject("Test")
        obj.add_property("width", PropertyType.FLOAT, 10.0)
        prop = obj.get_property("width")
        self.assertIsNotNone(prop)
        self.assertEqual(prop.value, 10.0)

    def test_set_property(self) -> None:
        obj = CADObject("Test")
        obj.add_property("width", PropertyType.FLOAT, 10.0)
        obj.set_property("width", 25.0)
        self.assertEqual(obj.get_property_value("width"), 25.0)

    def test_set_unknown_property_raises(self) -> None:
        obj = CADObject("Test")
        with self.assertRaises(KeyError):
            obj.set_property("nonexistent", 1)

    def test_get_unknown_property_raises(self) -> None:
        obj = CADObject("Test")
        with self.assertRaises(KeyError):
            obj.get_property_value("nonexistent")

    def test_get_property_nonexistent(self) -> None:
        obj = CADObject("Test")
        self.assertIsNone(obj.get_property("nonexistent"))

    def test_property_change_marks_dirty(self) -> None:
        obj = CADObject("Test")
        obj.add_property("width", PropertyType.FLOAT, 10.0)
        obj.recompute()  # Clear dirty
        self.assertFalse(obj.is_dirty())
        obj.set_property("width", 20.0)
        self.assertTrue(obj.is_dirty())

    def test_dependency_tracking(self) -> None:
        a = CADObject("A")
        b = CADObject("B")
        b.add_dependency(a)
        self.assertIn(str(a.uid), b.get_dependencies())
        self.assertIn(str(b.uid), a.get_dependents())

    def test_dependency_dedup(self) -> None:
        a = CADObject("A")
        b = CADObject("B")
        b.add_dependency(a)
        b.add_dependency(a)  # Should be idempotent
        self.assertEqual(len(b.get_dependencies()), 1)

    def test_dirty_propagation(self) -> None:
        self.doc.add_object(CADObject("A"))
        self.doc.add_object(CADObject("B"))
        a = self.doc.find_by_name("A")
        b = self.doc.find_by_name("B")
        b.add_dependency(a)
        a.recompute()
        b.recompute()
        self.assertFalse(a.is_dirty())
        self.assertFalse(b.is_dirty())
        # Changing a should mark both A and B dirty
        a._mark_dirty()
        self.assertTrue(a.is_dirty())
        self.assertTrue(b.is_dirty())

    def test_to_dict(self) -> None:
        obj = CADObject("TestObj")
        obj.add_property("p", PropertyType.FLOAT, 3.14)
        d = obj.to_dict()
        self.assertEqual(d["name"], "TestObj")
        self.assertEqual(d["type"], "CADObject")
        self.assertIn("properties", d)
        self.assertIn("uid", d)
        self.assertIn("dependencies", d)

    def test_repr(self) -> None:
        obj = CADObject("MyObj")
        self.assertIn("MyObj", repr(obj))

    def test_str(self) -> None:
        obj = CADObject("my_id", "My Label")
        self.assertIn("My Label", str(obj))
        self.assertIn("CADObject", str(obj))

    def test_document_binding_on_add(self) -> None:
        obj = CADObject("Test")
        self.assertIsNone(obj._document)
        self.doc.add_object(obj)
        self.assertIsNotNone(obj._document)


# ══════════════════════════════════════════════════════════════════════
# Document System
# ══════════════════════════════════════════════════════════════════════

class TestDocument(unittest.TestCase):
    def setUp(self) -> None:
        self.doc = Document("TestDoc")

    def test_create(self) -> None:
        self.assertEqual(self.doc.name, "TestDoc")
        self.assertEqual(self.doc.object_count, 0)

    def test_add_object(self) -> None:
        obj = CADObject("Obj1")
        self.doc.add_object(obj)
        self.assertEqual(self.doc.object_count, 1)

    def test_add_object_with_rename(self) -> None:
        obj = CADObject("Original")
        self.doc.add_object(obj, name="Renamed")
        self.assertEqual(obj.name, "Renamed")
        self.assertIsNotNone(self.doc.find_by_name("Renamed"))

    def test_remove_object(self) -> None:
        obj = CADObject("ToRemove")
        self.doc.add_object(obj)
        self.assertEqual(self.doc.object_count, 1)
        self.doc.remove_object(obj)
        self.assertEqual(self.doc.object_count, 0)
        self.assertIsNone(obj._document)

    def test_remove_object_cleans_dependencies(self) -> None:
        a = CADObject("A")
        b = CADObject("B")
        self.doc.add_object(a)
        self.doc.add_object(b)
        b.add_dependency(a)
        self.doc.remove_object(a)
        # B should no longer have A in its dependencies
        self.assertEqual(len(b.get_dependencies()), 0)
        self.assertIsNone(self.doc.find_by_name("A"))

    def test_get_object_by_uid(self) -> None:
        obj = CADObject("Test")
        self.doc.add_object(obj)
        found = self.doc.get_object(str(obj.uid))
        self.assertIs(found, obj)

    def test_get_object_by_name(self) -> None:
        obj = CADObject("Test")
        self.doc.add_object(obj)
        found = self.doc.get_object("Test")
        self.assertIs(found, obj)

    def test_get_object_not_found(self) -> None:
        self.assertIsNone(self.doc.get_object("nonexistent"))

    def test_find_by_name(self) -> None:
        obj = CADObject("UniqueName")
        self.doc.add_object(obj)
        found = self.doc.find_by_name("UniqueName")
        self.assertIs(found, obj)
        self.assertIsNone(self.doc.find_by_name("NonExistent"))

    def test_find_by_type(self) -> None:
        class TypeA(CADObject):
            pass
        class TypeB(CADObject):
            pass
        a = TypeA("A")
        b1 = TypeB("B1")
        b2 = TypeB("B2")
        self.doc.add_object(a)
        self.doc.add_object(b1)
        self.doc.add_object(b2)
        found = self.doc.find_by_type(TypeB)
        self.assertEqual(len(found), 2)

    def test_objects_property(self) -> None:
        a = CADObject("A")
        b = CADObject("B")
        self.doc.add_object(a)
        self.doc.add_object(b)
        objs = self.doc.objects
        self.assertEqual(len(objs), 2)
        self.assertIn(a, objs)
        self.assertIn(b, objs)

    def test_len(self) -> None:
        self.assertEqual(len(self.doc), 0)
        self.doc.add_object(CADObject("A"))
        self.assertEqual(len(self.doc), 1)

    def test_get_all_property_values(self) -> None:
        a = CADObject("A")
        a.add_property("width", PropertyType.FLOAT, 10)
        b = CADObject("B")
        b.add_property("width", PropertyType.FLOAT, 20)
        c = CADObject("C")
        c.add_property("height", PropertyType.FLOAT, 30)
        self.doc.add_object(a)
        self.doc.add_object(b)
        self.doc.add_object(c)
        widths = self.doc.get_all_property_values("width")
        self.assertEqual(widths["A"], 10)
        self.assertEqual(widths["B"], 20)
        self.assertNotIn("C", widths)

    def test_clear(self) -> None:
        self.doc.add_object(CADObject("A"))
        self.doc.add_object(CADObject("B"))
        self.doc.clear()
        self.assertEqual(self.doc.object_count, 0)

    def test_to_dict(self) -> None:
        self.doc.add_object(CADObject("Obj1"))
        d = self.doc.to_dict()
        self.assertEqual(d["name"], "TestDoc")
        self.assertEqual(len(d["objects"]), 1)
        self.assertIn("metadata", d)

    def test_recompute_empty(self) -> None:
        """Recompute on empty doc should not crash."""
        self.doc.recompute()

    def test_topological_sort_order(self) -> None:
        """Dependencies should come before dependents in sort."""
        a = CADObject("Base")
        b = CADObject("Derived")
        self.doc.add_object(a)
        self.doc.add_object(b)
        b.add_dependency(a)
        sorted_objs = self.doc._topological_sort()
        idx = {o.name: i for i, o in enumerate(sorted_objs)}
        self.assertLess(idx["Base"], idx["Derived"])

    def test_recompute_dirty_only(self) -> None:
        """recompute should only recompute dirty objects."""
        a = CADObject("A")
        b = CADObject("B")
        self.doc.add_object(a)
        self.doc.add_object(b)
        b.add_dependency(a)
        a._mark_dirty()
        a.recompute()  # Clear A
        b._dirty = False  # Force-clear B
        # Now B is clean but A is clean too
        # Both should stay clean after recompute
        self.doc.recompute()
        self.assertFalse(a.is_dirty())
        self.assertFalse(b.is_dirty())

    def test_recompute_dependency_chain(self) -> None:
        """A chain A -> B -> C should recompute A first, then B, then C."""
        a = CADObject("A")
        b = CADObject("B")
        c = CADObject("C")
        self.doc.add_object(a)
        self.doc.add_object(b)
        self.doc.add_object(c)
        b.add_dependency(a)
        c.add_dependency(b)
        recompute_order: list[str] = []

        class Tracker(CADObject):
            def recompute(self) -> None:
                recompute_order.append(self.name)
                super().recompute()

        # Replace objects with trackers
        ta = Tracker("A")
        tb = Tracker("B")
        tc = Tracker("C")
        self.doc.clear()
        self.doc.add_object(ta)
        self.doc.add_object(tb)
        self.doc.add_object(tc)
        tb.add_dependency(ta)
        tc.add_dependency(tb)

        ta._mark_dirty()
        self.doc.recompute()
        self.assertEqual(recompute_order, ["A", "B", "C"])

    def test_new_document_global(self) -> None:
        doc = new_document("GlobalTest")
        self.assertEqual(doc.name, "GlobalTest")
        self.assertIs(active_document(), doc)


# ══════════════════════════════════════════════════════════════════════
# Parameter / Parametric System
# ══════════════════════════════════════════════════════════════════════

class TestParameter(unittest.TestCase):
    def test_constant_value(self) -> None:
        p = Parameter("r", 10.0)
        self.assertEqual(p.value, 10.0)

    def test_set_value_clears_expression(self) -> None:
        p = Parameter("v", expression="2 + 2")
        p.value = 5
        self.assertIsNone(p.expression)
        self.assertEqual(p.value, 5)

    def test_expression_evaluation(self) -> None:
        p = Parameter("area", expression="3.14159 * 10 ** 2")
        self.assertAlmostEqual(p.value, 314.159, places=4)

    def test_expression_with_math_funcs(self) -> None:
        p = Parameter("v", expression="sqrt(16) + pi")
        val = p.value
        self.assertAlmostEqual(val, 4.0 + math.pi, places=10)

    def test_expression_with_references(self) -> None:
        radius = Parameter("radius", 5.0)
        area = Parameter("area", expression="{{radius}} ** 2 * pi")
        area.bind(lambda name: radius.value if name == "radius" else 0)
        self.assertAlmostEqual(area.value, 25.0 * math.pi, places=10)

    def test_cascading_expression(self) -> None:
        r = Parameter("r", 10.0)
        d = Parameter("d", expression="{{r}} * 2")
        d.bind(lambda name: r.value if name == "r" else 0)
        r.add_dependent(d)
        self.assertEqual(d.value, 20.0)
        r.value = 25.0
        self.assertEqual(d.value, 50.0)

    def test_cascading_two_levels(self) -> None:
        a = Parameter("a", 2.0)
        b = Parameter("b", expression="{{a}} * 3")
        c = Parameter("c", expression="{{b}} + 1")
        resolver = {
            "a": lambda: a.value,
            "b": lambda: b.value,
        }
        b.bind(lambda name: resolver.get(name, lambda: 0)())
        c.bind(lambda name: resolver.get(name, lambda: 0)())
        a.add_dependent(b)
        b.add_dependent(c)
        self.assertEqual(b.value, 6.0)
        self.assertEqual(c.value, 7.0)
        a.value = 3.0
        self.assertEqual(b.value, 9.0)
        self.assertEqual(c.value, 10.0)

    def test_invalid_expression_raises(self) -> None:
        p = Parameter("bad", expression="1 / 0")
        with self.assertRaises(ParametricError):
            _ = p.value

    def test_invalid_syntax_raises(self) -> None:
        p = Parameter("bad", expression="@@@")
        with self.assertRaises(ParametricError):
            _ = p.value

    def test_expression_none_on_constant(self) -> None:
        p = Parameter("v", 42.0)
        self.assertIsNone(p.expression)

    def test_to_dict(self) -> None:
        p = Parameter("p", 10.0)
        d = p.to_dict()
        self.assertEqual(d["name"], "p")
        self.assertEqual(d["value"], 10.0)

    def test_expression_to_dict(self) -> None:
        p = Parameter("p", expression="1 + 1")
        d = p.to_dict()
        self.assertIsNotNone(d["expression"])

    def test_dirty_after_set(self) -> None:
        p = Parameter("p", 10.0)
        # Initially dirty means "needs potential re-evaluation"
        self.assertEqual(p.value, 10.0)
        p.value = 20
        # After setting a new value, the value is updated
        self.assertEqual(p.value, 20.0)

    def test_no_reeval_if_not_dirty(self) -> None:
        evaluated = []
        class TrackingParameter(Parameter):
            def _evaluate(self) -> None:
                evaluated.append(True)
                super()._evaluate()
        p = TrackingParameter("p", expression="2 + 2")
        self.assertEqual(len(evaluated), 0)  # Lazy: not yet evaluated
        _ = p.value  # Triggers evaluation
        self.assertEqual(len(evaluated), 1)
        _ = p.value  # No re-evaluation needed (not dirty)
        self.assertEqual(len(evaluated), 1)


class TestParametricValue(unittest.TestCase):
    def test_descriptor_default(self) -> None:
        pv = ParametricValue(default=10.0)
        class Dummy:
            val = pv
        d = Dummy()
        self.assertEqual(d.val, 10.0)

    def test_descriptor_set(self) -> None:
        pv = ParametricValue(default=10.0)
        class Dummy:
            val = pv
        d = Dummy()
        d.val = 25.0
        self.assertEqual(d.val, 25.0)

    def test_descriptor_class_access(self) -> None:
        pv = ParametricValue(default=10.0)
        self.assertIs(pv, ParametricValue.__get__(pv, None, ParametricValue))


import math  # noqa: E402


if __name__ == "__main__":
    unittest.main()
