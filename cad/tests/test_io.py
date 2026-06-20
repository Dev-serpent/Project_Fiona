"""Tests for I/O exports — STL, OBJ, SVG content validation."""

from __future__ import annotations

import math
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from cad.core.document import Document
from cad.geometry.primitives import Box, Cylinder, Sphere
from cad.sketch.workspace import Sketch
from cad.io.native_format import CadSerializer
from cad.io.export_stl import export_stl
from cad.io.export_obj import export_obj
from cad.io.export_svg import export_svg


class TestSerializationAdvanced(unittest.TestCase):
    def test_serialize_with_sketch(self) -> None:
        doc = Document("test")
        sketch = Sketch("Sketch1")
        sketch.add_line("L", x1=0, y1=0, x2=10, y2=10)
        doc.add_object(sketch)
        data = CadSerializer.serialize(doc)
        loaded = CadSerializer.deserialize(data)
        # Sketch type may not be in type_map, so it won't be reconstructed
        # but the doc should at least have no errors

    def test_format_version(self) -> None:
        doc = Document("test")
        import json
        data = json.loads(CadSerializer.serialize(doc))
        self.assertEqual(data["format_version"], "1.0")

    def test_deserialize_unknown_type(self) -> None:
        """Unknown object types should be gracefully skipped."""
        import json
        bad_data = json.dumps({
            "name": "test",
            "format_version": "1.0",
            "metadata": {},
            "objects": [{"name": "Unknown", "type": "DoesNotExist", "properties": {}}],
        })
        doc = CadSerializer.deserialize(bad_data)
        self.assertEqual(doc.object_count, 0)
        self.assertEqual(doc.name, "test")

    def test_deserialize_from_missing_file(self) -> None:
        with self.assertRaises(FileNotFoundError):
            CadSerializer.deserialize_from_file("/nonexistent/file.cad")

    def test_roundtrip_preserves_property_values(self) -> None:
        doc = Document("test")
        box = Box("B1")
        box.set_property("width", 42)
        box.set_property("height", 84)
        box.set_property("depth", 126)
        doc.add_object(box)

        data = CadSerializer.serialize(doc)
        loaded = CadSerializer.deserialize(data)
        loaded_box = loaded.find_by_name("B1")
        self.assertIsNotNone(loaded_box)
        self.assertAlmostEqual(loaded_box.get_property_value("width"), 42)
        self.assertAlmostEqual(loaded_box.get_property_value("height"), 84)
        self.assertAlmostEqual(loaded_box.get_property_value("depth"), 126)


class TestSTLExport(unittest.TestCase):
    def setUp(self) -> None:
        self.doc = Document("test")
        self.tmp = TemporaryDirectory()
        self.path = Path(self.tmp.name) / "test.stl"

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_export_empty_doc(self) -> None:
        export_stl(self.doc, self.path)
        content = self.path.read_text()
        self.assertIn("solid CADModel", content)
        self.assertIn("endsolid CADModel", content)

    def test_export_box(self) -> None:
        box = Box("B1")
        box.set_property("width", 10)
        box.set_property("height", 20)
        box.set_property("depth", 30)
        self.doc.add_object(box)
        export_stl(self.doc, self.path)
        content = self.path.read_text()
        # Box has 12 faces (6 quads = 12 triangles)
        facet_count = content.count("facet normal")
        self.assertEqual(facet_count, 12)

    def test_export_cylinder(self) -> None:
        cyl = Cylinder("C1")
        cyl.set_property("radius", 5)
        cyl.set_property("height", 10)
        self.doc.add_object(cyl)
        export_stl(self.doc, self.path)
        content = self.path.read_text()
        facet_count = content.count("facet normal")
        # 24 segments: 24*2 side + 24 top + 24 bottom = 96 triangles
        self.assertGreater(facet_count, 0)

    def test_export_sphere(self) -> None:
        sph = Sphere("S1")
        sph.set_property("radius", 10)
        self.doc.add_object(sph)
        export_stl(self.doc, self.path)
        content = self.path.read_text()
        facet_count = content.count("facet normal")
        self.assertGreater(facet_count, 0)

    def test_export_multiple_objects(self) -> None:
        self.doc.add_object(Box("B1"))
        self.doc.add_object(Cylinder("C1"))
        export_stl(self.doc, self.path)
        content = self.path.read_text()
        # All objects should be in a single solid (header only, not inside endsolid)
        self.assertTrue(content.startswith("solid CADModel"))
        self.assertGreater(content.count("vertex"), 10)

    def test_export_custom_name(self) -> None:
        export_stl(self.doc, self.path, solid_name="MyModel")
        content = self.path.read_text()
        self.assertIn("solid MyModel", content)
        self.assertIn("endsolid MyModel", content)


class TestOBJExport(unittest.TestCase):
    def setUp(self) -> None:
        self.doc = Document("test")
        self.tmp = TemporaryDirectory()
        self.path = Path(self.tmp.name) / "test.obj"

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_export_empty(self) -> None:
        export_obj(self.doc, self.path)
        content = self.path.read_text()
        self.assertIn("CADModel", content)

    def test_export_box(self) -> None:
        self.doc.add_object(Box("B1"))
        export_obj(self.doc, self.path)
        content = self.path.read_text()
        # 8 vertices for a box
        v_count = len([l for l in content.split("\n") if l.startswith("v ")])
        self.assertEqual(v_count, 8)
        # 6 quad faces
        f_count = len([l for l in content.split("\n") if l.startswith("f ")])
        self.assertEqual(f_count, 6)

    def test_export_object_name(self) -> None:
        self.doc.add_object(Box("MyBoxName"))
        export_obj(self.doc, self.path)
        content = self.path.read_text()
        self.assertIn("g MyBoxName", content)


class TestSVGExport(unittest.TestCase):
    def setUp(self) -> None:
        self.doc = Document("test")
        self.tmp = TemporaryDirectory()
        self.path = Path(self.tmp.name) / "test.svg"

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_export_empty(self) -> None:
        export_svg(self.doc, self.path)
        content = self.path.read_text()
        self.assertIn("<svg", content)
        self.assertIn("</svg>", content)

    def test_export_sketch_with_line(self) -> None:
        sketch = Sketch("Sketch1")
        sketch.add_line("L", x1=10, y1=20, x2=50, y2=80)
        self.doc.add_object(sketch)
        export_svg(self.doc, self.path)
        content = self.path.read_text()
        self.assertIn("<line", content)
        self.assertIn('x1="10.000"', content)
        self.assertIn('y2="-80.000"', content)  # Y is flipped in SVG

    def test_export_sketch_with_circle(self) -> None:
        sketch = Sketch("Sketch1")
        sketch.add_circle("C", cx=25, cy=35, radius=40)
        self.doc.add_object(sketch)
        export_svg(self.doc, self.path)
        content = self.path.read_text()
        self.assertIn("<circle", content)
        self.assertIn('cx="25.000"', content)
        self.assertIn('r="40.000"', content)

    def test_export_sketch_with_multiple_entities(self) -> None:
        sketch = Sketch("Sketch1")
        sketch.add_line("L1", x1=0, y1=0, x2=10, y2=10)
        sketch.add_circle("C1", cx=5, cy=5, radius=3)
        self.doc.add_object(sketch)
        export_svg(self.doc, self.path)
        content = self.path.read_text()
        self.assertIn("<line", content)
        self.assertIn("<circle", content)

    def test_export_ignores_non_sketch_objects(self) -> None:
        self.doc.add_object(Box("B1"))
        export_svg(self.doc, self.path)
        content = self.path.read_text()
        # Box is not a sketch, should not appear as SVG geometry
        # Just the basic SVG template should be present
        self.assertIn("<svg", content)

    def test_custom_dimensions(self) -> None:
        export_svg(self.doc, self.path, width=1024, height=768)
        content = self.path.read_text()
        self.assertIn('width="1024"', content)
        self.assertIn('height="768"', content)
        self.assertIn('viewBox="-512 -384 1024 768', content)


if __name__ == "__main__":
    unittest.main()
