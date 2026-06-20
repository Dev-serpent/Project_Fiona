"""Tests for the 2D Sketch workspace."""

from __future__ import annotations

import math
import unittest

from cad.core.document import Document
from cad.geometry.math import Vector2, Plane
from cad.geometry.primitives import Point2D, Line, Circle, Arc
from cad.constraints.types import Coincident, Distance, Horizontal
from cad.sketch.workspace import Sketch, SketchEntity


class TestSketchCreation(unittest.TestCase):
    def setUp(self) -> None:
        self.doc = Document("test")

    def test_create_sketch(self) -> None:
        s = Sketch("Sketch1")
        self.doc.add_object(s)
        self.assertEqual(s.name, "Sketch1")
        self.assertEqual(s.plane, Plane.XY())
        self.assertEqual(len(s.entities), 0)

    def test_create_sketch_custom_plane(self) -> None:
        s = Sketch("Sketch1", Plane.XZ())
        self.assertEqual(s.plane, Plane.XZ())

    def test_plane_setter(self) -> None:
        s = Sketch("S")
        s.plane = Plane.YZ()
        self.assertEqual(s.plane, Plane.YZ())

    def test_add_entity(self) -> None:
        s = Sketch("S")
        p = Point2D("P1")
        p.set_property("x", 10)
        p.set_property("y", 20)
        s.add_entity(p)
        self.assertEqual(len(s.entities), 1)
        self.assertEqual(s.get_property_value("entity_count"), 1)

    def test_add_entity_adds_dependency(self) -> None:
        s = Sketch("S")
        p = Point2D("P")
        s.add_entity(p)
        self.assertIn(str(p.uid), s.get_dependencies())

    def test_remove_entity(self) -> None:
        s = Sketch("S")
        p = Point2D("P")
        s.add_entity(p)
        s.remove_entity(p)
        self.assertEqual(len(s.entities), 0)
        self.assertEqual(s.get_property_value("entity_count"), 0)

    def test_get_entity_by_uid(self) -> None:
        s = Sketch("S")
        p = Point2D("P")
        s.add_entity(p)
        found = s.get_entity(str(p.uid))
        self.assertIs(found, p)

    def test_get_entity_by_name(self) -> None:
        s = Sketch("S")
        p = Point2D("MyPoint")
        s.add_entity(p)
        found = s.get_entity("MyPoint")
        self.assertIs(found, p)

    def test_get_entity_not_found(self) -> None:
        s = Sketch("S")
        self.assertIsNone(s.get_entity("nonexistent"))

    def test_add_line_helper(self) -> None:
        s = Sketch("S")
        line = s.add_line("L1", x1=0, y1=0, x2=10, y2=10)
        self.assertEqual(len(s.entities), 1)
        self.assertEqual(line.get_property_value("x1"), 0)
        self.assertEqual(line.get_property_value("x2"), 10)

    def test_add_circle_helper(self) -> None:
        s = Sketch("S")
        c = s.add_circle("C1", cx=5, cy=5, radius=15)
        self.assertEqual(len(s.entities), 1)
        self.assertEqual(c.get_property_value("radius"), 15)

    def test_add_arc_helper(self) -> None:
        s = Sketch("S")
        a = s.add_arc("A1", cx=0, cy=0, radius=10, start_angle=0, end_angle=180)
        self.assertEqual(len(s.entities), 1)
        self.assertEqual(a.get_property_value("start_angle"), 0)
        self.assertEqual(a.get_property_value("end_angle"), 180)

    def test_add_constraint_to_sketch(self) -> None:
        s = Sketch("S")
        p1 = Point2D("P1")
        p2 = Point2D("P2")
        s.add_entity(p1)
        s.add_entity(p2)
        c = Coincident("c", p1, p2)
        s.add_constraint(c)
        self.assertEqual(len(s.constraints), 1)
        self.assertEqual(s.get_property_value("constraint_count"), 1)

    def test_remove_constraint(self) -> None:
        s = Sketch("S")
        p1 = Point2D("P1")
        p2 = Point2D("P2")
        s.add_entity(p1)
        s.add_entity(p2)
        c = Coincident("c", p1, p2)
        s.add_constraint(c)
        s.remove_constraint(c)
        self.assertEqual(len(s.constraints), 0)

    def test_solve_constraints(self) -> None:
        s = Sketch("S")
        p1 = Point2D("P1")
        p2 = Point2D("P2")
        p1.set_property("x", 0); p1.set_property("y", 0)
        p2.set_property("x", 10); p2.set_property("y", 10)
        s.add_entity(p1)
        s.add_entity(p2)
        s.add_constraint(Coincident("c", p1, p2))
        residual = s.solve_constraints()
        self.assertLess(residual, 1e-6)
        self.assertAlmostEqual(p1.get_property_value("x"),
                               p2.get_property_value("x"), places=4)

    def test_recompute_solves_constraints(self) -> None:
        s = Sketch("S")
        p1 = Point2D("P1")
        p2 = Point2D("P2")
        p1.set_property("x", 0); p1.set_property("y", 0)
        p2.set_property("x", 5); p2.set_property("y", 12)
        s.add_entity(p1)
        s.add_entity(p2)
        s.add_constraint(Distance("d", p1, p2, 13.0))
        s.recompute()
        d = math.sqrt(
            (p1.get_property_value("x") - p2.get_property_value("x")) ** 2 +
            (p1.get_property_value("y") - p2.get_property_value("y")) ** 2
        )
        self.assertAlmostEqual(d, 13.0, places=4)

    def test_get_edges_2d_empty(self) -> None:
        s = Sketch("S")
        edges = s.get_edges_2d()
        self.assertEqual(len(edges), 0)

    def test_get_edges_2d_line(self) -> None:
        s = Sketch("S")
        s.add_line("L", x1=0, y1=0, x2=10, y2=10)
        edges = s.get_edges_2d()
        self.assertEqual(len(edges), 1)
        self.assertEqual(edges[0][0], Vector2(0, 0))
        self.assertEqual(edges[0][1], Vector2(10, 10))

    def test_get_edges_2d_circle(self) -> None:
        s = Sketch("S")
        s.add_circle("C", cx=0, cy=0, radius=10)
        edges = s.get_edges_2d()
        # Circle approximated as 32-segment polygon
        self.assertEqual(len(edges), 32)

    def test_to_dict(self) -> None:
        s = Sketch("S")
        s.add_line("L", x1=0, y1=0, x2=10, y2=10)
        d = s.to_dict()
        self.assertEqual(d["name"], "S")
        self.assertIn("plane", d)
        self.assertIn("entities", d)
        self.assertEqual(len(d["entities"]), 1)

    def test_construction_geometry_property(self) -> None:
        entity = SketchEntity("E")
        self.assertFalse(entity.get_property_value("construction"))
        entity.set_property("construction", True)
        self.assertTrue(entity.get_property_value("construction"))

    def test_default_layer(self) -> None:
        entity = SketchEntity("E")
        self.assertEqual(entity.get_property_value("layer"), "default")


if __name__ == "__main__":
    unittest.main()
