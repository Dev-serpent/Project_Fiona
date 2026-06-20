"""Built-in commands for geometry creation, transformation, and query."""

from __future__ import annotations

import uuid
from typing import Any

from cad.commands.registry import Command, CommandRegistry
from cad.core.document import Document
from cad.core.object import CADObject
from cad.geometry.primitives import (
    Point2D, Point3D, Line, Circle, Arc, Ellipse,
    Box, Cylinder, Cone, Sphere, Torus, Polygon,
)
from cad.geometry.math import Vector3, Matrix4
from cad.geometry.transforms import translate, rotate, scale
from cad.sketch.workspace import Sketch
from cad.part.features import Pad, Pocket, Revolve
from cad.assembly.assembly import Assembly, PartInstance
from cad.constraints.types import (
    Coincident, Parallel, Perpendicular, Horizontal, Vertical,
    Distance, Angle, Radius, Fix,
)


# ══════════════════════════════════════════════════════════════════════
# Document Commands
# ══════════════════════════════════════════════════════════════════════

class NewDocument(Command):
    name = "new_document"
    description = "Create a new CAD document"

    def execute(self, doc: Document, **kwargs: Any) -> Document:
        return Document(kwargs.get("name", "Untitled"))


class Recompute(Command):
    name = "recompute"
    description = "Recompute all dirty objects in the document"

    def execute(self, doc: Document, **kwargs: Any) -> None:
        doc.recompute()


class ListObjects(Command):
    name = "list_objects"
    description = "List all objects in the document"

    def execute(self, doc: Document, **kwargs: Any) -> list[dict]:
        return [{"name": o.name, "type": type(o).__name__} for o in doc.objects]


# ══════════════════════════════════════════════════════════════════════
# Geometry Creation Commands
# ══════════════════════════════════════════════════════════════════════

class CreateBox(Command):
    name = "create_box"
    aliases = ["box"]
    description = "Create a box primitive: create_box(width=10, height=20, depth=30)"

    def execute(self, doc: Document, **kwargs: Any) -> Box:
        obj = Box(kwargs.get("name", "Box"))
        obj.set_property("width", kwargs.get("width", 10.0))
        obj.set_property("height", kwargs.get("height", 10.0))
        obj.set_property("depth", kwargs.get("depth", 10.0))
        obj.set_property("x", kwargs.get("x", 0.0))
        obj.set_property("y", kwargs.get("y", 0.0))
        obj.set_property("z", kwargs.get("z", 0.0))
        doc.add_object(obj)
        return obj


class CreateCylinder(Command):
    name = "create_cylinder"
    aliases = ["cylinder"]
    description = "Create a cylinder primitive: create_cylinder(radius=5, height=15)"

    def execute(self, doc: Document, **kwargs: Any) -> Cylinder:
        obj = Cylinder(kwargs.get("name", "Cylinder"))
        obj.set_property("radius", kwargs.get("radius", 5.0))
        obj.set_property("height", kwargs.get("height", 15.0))
        obj.set_property("x", kwargs.get("x", 0.0))
        obj.set_property("y", kwargs.get("y", 0.0))
        obj.set_property("z", kwargs.get("z", 0.0))
        doc.add_object(obj)
        return obj


class CreateCone(Command):
    name = "create_cone"
    aliases = ["cone"]
    description = "Create a cone primitive"

    def execute(self, doc: Document, **kwargs: Any) -> Cone:
        obj = Cone(kwargs.get("name", "Cone"))
        obj.set_property("radius", kwargs.get("radius", 5.0))
        obj.set_property("height", kwargs.get("height", 15.0))
        doc.add_object(obj)
        return obj


class CreateSphere(Command):
    name = "create_sphere"
    aliases = ["sphere"]
    description = "Create a sphere primitive"

    def execute(self, doc: Document, **kwargs: Any) -> Sphere:
        obj = Sphere(kwargs.get("name", "Sphere"))
        obj.set_property("radius", kwargs.get("radius", 10.0))
        doc.add_object(obj)
        return obj


class CreateTorus(Command):
    name = "create_torus"
    aliases = ["torus"]
    description = "Create a torus primitive"

    def execute(self, doc: Document, **kwargs: Any) -> Torus:
        obj = Torus(kwargs.get("name", "Torus"))
        obj.set_property("major_radius", kwargs.get("major_radius", 20.0))
        obj.set_property("minor_radius", kwargs.get("minor_radius", 5.0))
        doc.add_object(obj)
        return obj


class CreateLine(Command):
    name = "create_line"
    aliases = ["line"]
    description = "Create a line: create_line(x1=0, y1=0, x2=10, y2=10)"

    def execute(self, doc: Document, **kwargs: Any) -> Line:
        obj = Line(kwargs.get("name", "Line"))
        for attr in ("x1", "y1", "x2", "y2"):
            obj.set_property(attr, kwargs.get(attr, 0.0))
        doc.add_object(obj)
        return obj


class CreateCircleCmd(Command):
    name = "create_circle"
    aliases = ["circle"]
    description = "Create a circle: create_circle(cx=0, cy=0, radius=10)"

    def execute(self, doc: Document, **kwargs: Any) -> Circle:
        obj = Circle(kwargs.get("name", "Circle"))
        obj.set_property("cx", kwargs.get("cx", 0.0))
        obj.set_property("cy", kwargs.get("cy", 0.0))
        obj.set_property("radius", kwargs.get("radius", 10.0))
        doc.add_object(obj)
        return obj


# ══════════════════════════════════════════════════════════════════════
# Sketch Commands
# ══════════════════════════════════════════════════════════════════════

class CreateSketch(Command):
    name = "create_sketch"
    aliases = ["sketch"]
    description = "Create a 2D sketch: create_sketch(name='Sketch1')"

    def execute(self, doc: Document, **kwargs: Any) -> Sketch:
        sketch = Sketch(kwargs.get("name", "Sketch"))
        doc.add_object(sketch)
        return sketch


class AddPointToSketch(Command):
    name = "add_point"
    description = "Add a point to a sketch"

    def execute(self, doc: Document, **kwargs: Any) -> Any:
        sketch_name = kwargs.get("sketch", "")
        sketch = doc.find_by_name(sketch_name)
        if not sketch or not isinstance(sketch, Sketch):
            raise ValueError(f"Sketch not found: {sketch_name}")
        return sketch.add_point(kwargs.get("name", "Point"),
                                kwargs.get("x", 0.0), kwargs.get("y", 0.0))


class AddLineToSketch(Command):
    name = "sketch_add_line"
    description = "Add a line to a sketch"

    def execute(self, doc: Document, **kwargs: Any) -> Any:
        sketch_name = kwargs.get("sketch", "")
        sketch = doc.find_by_name(sketch_name)
        if not sketch or not isinstance(sketch, Sketch):
            raise ValueError(f"Sketch not found: {sketch_name}")
        line = Line(kwargs.get("name", "Line"))
        for attr in ("x1", "y1", "x2", "y2"):
            line.set_property(attr, kwargs.get(attr, 0.0))
        sketch.add_entity(line)
        return line


# ══════════════════════════════════════════════════════════════════════
# Part Feature Commands
# ══════════════════════════════════════════════════════════════════════

class ExtrudeSketch(Command):
    name = "extrude"
    description = "Extrude a sketch: extrude(sketch='Sketch1', height=25)"

    def execute(self, doc: Document, **kwargs: Any) -> Pad:
        sketch_name = kwargs.get("sketch", "")
        sketch = doc.find_by_name(sketch_name)
        if not sketch or not isinstance(sketch, Sketch):
            raise ValueError(f"Sketch not found: {sketch_name}")
        pad = Pad(kwargs.get("name", f"Pad_{sketch.name}"),
                  sketch, kwargs.get("height", 10.0))
        doc.add_object(pad)
        return pad


class RevolveSketch(Command):
    name = "revolve"
    description = "Revolve a sketch: revolve(sketch='Sketch1', angle=360)"

    def execute(self, doc: Document, **kwargs: Any) -> Revolve:
        sketch_name = kwargs.get("sketch", "")
        sketch = doc.find_by_name(sketch_name)
        if not sketch or not isinstance(sketch, Sketch):
            raise ValueError(f"Sketch not found: {sketch_name}")
        revolve = Revolve(kwargs.get("name", f"Revolve_{sketch.name}"),
                          sketch, kwargs.get("angle", 360.0))
        doc.add_object(revolve)
        return revolve


# ══════════════════════════════════════════════════════════════════════
# Constraint Commands
# ══════════════════════════════════════════════════════════════════════

class AddConstraint(Command):
    name = "add_constraint"
    description = "Add a constraint: add_constraint(type='coincident', entity1=..., entity2=...)"

    def execute(self, doc: Document, **kwargs: Any) -> Any:
        constraint_type = kwargs.get("type", "coincident")
        name = kwargs.get("name", f"Constraint_{constraint_type}")
        e1_name = kwargs.get("entity1", "")
        e2_name = kwargs.get("entity2", "")
        e1 = doc.find_by_name(e1_name)
        e2 = doc.find_by_name(e2_name) if e2_name else None

        if not e1:
            raise ValueError(f"Entity not found: {e1_name}")

        constraint_map = {
            "coincident": lambda: Coincident(name, e1, e2),
            "parallel": lambda: Parallel(name, e1, e2),
            "perpendicular": lambda: Perpendicular(name, e1, e2),
            "horizontal": lambda: Horizontal(name, e1),
            "vertical": lambda: Vertical(name, e1),
            "distance": lambda: Distance(name, e1, e2, kwargs.get("value", 10.0)),
            "angle": lambda: Angle(name, e1, e2, kwargs.get("value", 45.0)),
            "radius": lambda: Radius(name, e1, kwargs.get("value", 10.0)),
            "fix": lambda: Fix(name, e1, kwargs.get("x"), kwargs.get("y")),
        }

        maker = constraint_map.get(constraint_type)
        if not maker:
            raise ValueError(f"Unknown constraint type: {constraint_type}")

        constraint = maker()
        doc.add_object(constraint)
        return constraint


# ══════════════════════════════════════════════════════════════════════
# Assembly Commands
# ══════════════════════════════════════════════════════════════════════

class CreateAssembly(Command):
    name = "create_assembly"
    aliases = ["assembly"]
    description = "Create an assembly: create_assembly(name='Assembly1')"

    def execute(self, doc: Document, **kwargs: Any) -> Assembly:
        assembly = Assembly(kwargs.get("name", "Assembly"))
        doc.add_object(assembly)
        return assembly


class AddPartToAssembly(Command):
    name = "assembly_add_part"
    description = "Add a part instance to an assembly"

    def execute(self, doc: Document, **kwargs: Any) -> PartInstance:
        assembly_name = kwargs.get("assembly", "")
        assembly = doc.find_by_name(assembly_name)
        if not assembly or not isinstance(assembly, Assembly):
            raise ValueError(f"Assembly not found: {assembly_name}")
        part = PartInstance(kwargs.get("name", "Part"),
                            kwargs.get("source"))
        part.set_property("px", kwargs.get("x", 0.0))
        part.set_property("py", kwargs.get("y", 0.0))
        part.set_property("pz", kwargs.get("z", 0.0))
        assembly.add_part(part)
        return part


# ══════════════════════════════════════════════════════════════════════
# Duplicate Command
# ══════════════════════════════════════════════════════════════════════

class DuplicateObject(Command):
    name = "duplicate"
    aliases = ["dup", "copy"]
    description = "Duplicate an object with optional position offset"

    def execute(self, doc: Document, **kwargs: Any) -> CADObject:
        import copy
        obj_name = kwargs.get("name", "")
        obj = doc.find_by_name(obj_name)
        if obj is None:
            raise ValueError(f"Object not found: {obj_name}")

        new_obj = copy.deepcopy(obj)
        new_obj.name = kwargs.get("new_name", f"{obj.name}_copy")
        new_obj.uid = uuid.uuid4()

        # Apply position offset
        offset = kwargs.get("offset", 10.0)
        for prop_name in ("x", "y", "z"):
            prop = new_obj.get_property(prop_name)
            if prop is not None and not prop.readonly:
                try:
                    new_obj.set_property(prop_name, prop.value + offset)
                except (TypeError, ValueError):
                    pass

        doc.add_object(new_obj)
        return new_obj


# ══════════════════════════════════════════════════════════════════════
# Registration
# ══════════════════════════════════════════════════════════════════════

def register_builtin_commands(registry: CommandRegistry) -> None:
    """Register all built-in commands with the given registry."""
    commands = [
        NewDocument(),
        Recompute(),
        ListObjects(),
        CreateBox(),
        CreateCylinder(),
        CreateCone(),
        CreateSphere(),
        CreateTorus(),
        CreateCircleCmd(),
        CreateLine(),
        CreateSketch(),
        AddPointToSketch(),
        AddLineToSketch(),
        ExtrudeSketch(),
        RevolveSketch(),
        AddConstraint(),
        CreateAssembly(),
        AddPartToAssembly(),
        DuplicateObject(),
    ]
    for cmd in commands:
        registry.register(cmd)
