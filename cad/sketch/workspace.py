"""2D Sketch workspace — entities, constraints, and construction geometry."""

from __future__ import annotations

from cad.core.object import CADObject, PropertyType
from cad.constraints.solver import ConstraintSolver
from cad.constraints.types import Constraint
from cad.geometry.math import Vector2, Plane
from cad.geometry.primitives import (
    Point2D, Line, Circle, Arc, Spline, Polygon,
)


class SketchEntity(CADObject):
    """An entity within a sketch (base class)."""

    def _define_properties(self) -> None:
        self.add_property("construction", PropertyType.BOOL, False,
                          description="Construction geometry (not used in solid generation)")
        self.add_property("layer", PropertyType.STRING, "default")


class Sketch(CADObject):
    """A 2D sketch workspace containing geometry and constraints.

    A sketch lives on a plane and contains:
    - Sketch entities (lines, circles, arcs, etc.)
    - Constraints between entities
    - Construction geometry (guidelines, reference points)
    """

    def __init__(self, name: str, plane: Plane | None = None) -> None:
        super().__init__(name)
        self._entities: dict[str, SketchEntity] = {}
        self._constraints: list[Constraint] = []
        self._solver = ConstraintSolver()
        self._plane = plane or Plane.XY()

    def _define_properties(self) -> None:
        self.add_property("entity_count", PropertyType.INT, 0, readonly=True)
        self.add_property("constraint_count", PropertyType.INT, 0, readonly=True)

    @property
    def plane(self) -> Plane:
        return self._plane

    @plane.setter
    def plane(self, p: Plane) -> None:
        self._plane = p
        self._mark_dirty()

    # ── Entity Management ───────────────────────────────────────────

    def add_entity(self, entity: SketchEntity) -> SketchEntity:
        self._entities[str(entity.uid)] = entity
        self.add_dependency(entity)
        self.set_property("entity_count", len(self._entities))
        return entity

    def remove_entity(self, entity: SketchEntity) -> None:
        self._entities.pop(str(entity.uid), None)
        self.set_property("entity_count", len(self._entities))

    def get_entity(self, uid_or_name: str) -> SketchEntity | None:
        for entity in self._entities.values():
            if str(entity.uid) == uid_or_name or entity.name == uid_or_name:
                return entity
        return None

    @property
    def entities(self) -> list[SketchEntity]:
        return list(self._entities.values())

    # ── Constraint Management ───────────────────────────────────────

    def add_constraint(self, constraint: Constraint) -> None:
        self._constraints.append(constraint)
        self._solver.add_constraint(constraint)
        self.add_dependency(constraint)
        self.set_property("constraint_count", len(self._constraints))

    def remove_constraint(self, constraint: Constraint) -> None:
        self._constraints.remove(constraint)
        self._solver.remove_constraint(constraint)
        self.set_property("constraint_count", len(self._constraints))

    @property
    def constraints(self) -> list[Constraint]:
        return list(self._constraints)

    # ── Solver Integration ──────────────────────────────────────────

    def solve_constraints(self) -> float:
        """Solve all sketch constraints. Returns residual error."""
        return self._solver.solve()

    # ── Convenience Entity Creators ─────────────────────────────────

    def add_point(self, name: str, x: float = 0.0, y: float = 0.0) -> Point2D:
        pt = Point2D(name)
        pt.set_property("x", x)
        pt.set_property("y", y)
        return self.add_entity(pt) or pt

    def add_line(self, name: str, x1: float = 0.0, y1: float = 0.0,
                 x2: float = 10.0, y2: float = 10.0) -> Line:
        line = Line(name)
        line.set_property("x1", x1)
        line.set_property("y1", y1)
        line.set_property("x2", x2)
        line.set_property("y2", y2)
        return self.add_entity(line)  # type: ignore

    def add_circle(self, name: str, cx: float = 0.0, cy: float = 0.0,
                   radius: float = 10.0) -> Circle:
        c = Circle(name)
        c.set_property("cx", cx)
        c.set_property("cy", cy)
        c.set_property("radius", radius)
        return self.add_entity(c)  # type: ignore

    def add_arc(self, name: str, cx: float = 0.0, cy: float = 0.0,
                radius: float = 10.0,
                start_angle: float = 0.0, end_angle: float = 90.0) -> Arc:
        arc = Arc(name)
        arc.set_property("cx", cx)
        arc.set_property("cy", cy)
        arc.set_property("radius", radius)
        arc.set_property("start_angle", start_angle)
        arc.set_property("end_angle", end_angle)
        return self.add_entity(arc)  # type: ignore

    # ── Flatten to 2D edges for extrusion ───────────────────────────

    def get_edges_2d(self) -> list[tuple[Vector2, Vector2]]:
        """Extract 2D edges from sketch for use in part features."""
        edges: list[tuple[Vector2, Vector2]] = []
        for entity in self._entities.values():
            if isinstance(entity, Line):
                start = Vector2(entity.get_property_value("x1"), entity.get_property_value("y1"))
                end = Vector2(entity.get_property_value("x2"), entity.get_property_value("y2"))
                edges.append((start, end))
            elif isinstance(entity, Circle):
                cx = entity.get_property_value("cx")
                cy = entity.get_property_value("cy")
                r = entity.get_property_value("radius")
                # Approximate circle as polygon
                n = 32
                for i in range(n):
                    a1 = 2 * math.pi * i / n
                    a2 = 2 * math.pi * (i + 1) / n
                    p1 = Vector2(cx + r * math.cos(a1), cy + r * math.sin(a1))
                    p2 = Vector2(cx + r * math.cos(a2), cy + r * math.sin(a2))
                    edges.append((p1, p2))
        return edges

    # ── Serialization ───────────────────────────────────────────────

    def to_dict(self) -> dict:
        data = super().to_dict()
        data["plane"] = self._plane.to_dict()
        data["entities"] = [e.to_dict() for e in self._entities.values()]
        data["constraints"] = [c.to_dict() for c in self._constraints]
        return data

    def recompute(self) -> None:
        if self._constraints:
            try:
                self._solver.solve()
            except Exception:
                pass  # Will be re-solved on next update
        self._dirty = False


import math  # noqa: E402 (needed for circle approximation)
