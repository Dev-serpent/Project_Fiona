"""Tests for the constraint solver."""

from __future__ import annotations

import unittest
import math

from cad.core.document import Document
from cad.geometry.primitives import Point2D, Line, Circle
from cad.constraints.solver import ConstraintSolver, ConstraintError
from cad.constraints.types import (
    Coincident, Parallel, Perpendicular, Horizontal, Vertical,
    Distance, Angle, Radius, Fix,
)


class TestConstraintSolver(unittest.TestCase):
    def setUp(self) -> None:
        self.solver = ConstraintSolver()

    def test_coincident(self) -> None:
        p1 = Point2D("p1")
        p2 = Point2D("p2")
        p1.set_property("x", 0)
        p1.set_property("y", 0)
        p2.set_property("x", 5)
        p2.set_property("y", 5)
        constraint = Coincident("c", p1, p2)
        self.solver.add_constraint(constraint)
        residual = self.solver.solve()
        self.assertLess(residual, 1e-6)
        self.assertAlmostEqual(p1.get_property_value("x"),
                               p2.get_property_value("x"), places=4)
        self.assertAlmostEqual(p1.get_property_value("y"),
                               p2.get_property_value("y"), places=4)

    def test_horizontal(self) -> None:
        line = Line("line")
        line.set_property("x1", 0)
        line.set_property("y1", 10)
        line.set_property("x2", 10)
        line.set_property("y2", 15)
        constraint = Horizontal("h", line)
        self.solver.add_constraint(constraint)
        residual = self.solver.solve()
        self.assertLess(residual, 1e-6)
        self.assertAlmostEqual(line.get_property_value("y1"),
                               line.get_property_value("y2"), places=4)

    def test_vertical(self) -> None:
        line = Line("line")
        line.set_property("x1", 5)
        line.set_property("y1", 0)
        line.set_property("x2", 10)
        line.set_property("y2", 10)
        constraint = Vertical("v", line)
        self.solver.add_constraint(constraint)
        residual = self.solver.solve()
        self.assertLess(residual, 1e-6)
        self.assertAlmostEqual(line.get_property_value("x1"),
                               line.get_property_value("x2"), places=4)

    def test_distance(self) -> None:
        p1 = Point2D("p1")
        p2 = Point2D("p2")
        p1.set_property("x", 0)
        p1.set_property("y", 0)
        p2.set_property("x", 3)
        p2.set_property("y", 4)
        constraint = Distance("d", p1, p2, 10.0)
        self.solver.add_constraint(constraint)
        residual = self.solver.solve()
        self.assertLess(residual, 1e-6)
        d = math.sqrt(
            (p1.get_property_value("x") - p2.get_property_value("x")) ** 2 +
            (p1.get_property_value("y") - p2.get_property_value("y")) ** 2
        )
        self.assertAlmostEqual(d, 10.0, places=4)

    def test_perpendicular(self) -> None:
        l1 = Line("l1")
        l2 = Line("l2")
        l1.set_property("x1", 0); l1.set_property("y1", 0)
        l1.set_property("x2", 10); l1.set_property("y2", 0)
        l2.set_property("x1", 0); l2.set_property("y1", 0)
        l2.set_property("x2", 0); l2.set_property("y2", 10)
        constraint = Perpendicular("p", l1, l2)
        self.solver.add_constraint(constraint)
        residual = self.solver.solve()
        self.assertLess(residual, 1e-6)

    def test_radius(self) -> None:
        c = Circle("circle")
        c.set_property("radius", 5)
        constraint = Radius("r", c, 15.0)
        self.solver.add_constraint(constraint)
        residual = self.solver.solve()
        self.assertLess(residual, 1e-6)
        self.assertAlmostEqual(c.get_property_value("radius"), 15.0, places=4)


class TestDocumentConstraints(unittest.TestCase):
    def test_sketch_with_constraints(self) -> None:
        doc = Document("test")
        from cad.sketch.workspace import Sketch
        sketch = Sketch("Sketch1")
        doc.add_object(sketch)

        p1 = Point2D("p1")
        p2 = Point2D("p2")
        p1.set_property("x", 0); p1.set_property("y", 0)
        p2.set_property("x", 10); p2.set_property("y", 10)

        sketch.add_entity(p1)
        sketch.add_entity(p2)

        constraint = Distance("d", p1, p2, 5.0)
        sketch.add_constraint(constraint)

        doc.recompute()
        d = math.sqrt(
            (p1.get_property_value("x") - p2.get_property_value("x")) ** 2 +
            (p1.get_property_value("y") - p2.get_property_value("y")) ** 2
        )
        self.assertAlmostEqual(d, 5.0, places=4)


if __name__ == "__main__":
    unittest.main()
