"""Tests for the native .cad file format."""

from __future__ import annotations

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from cad.core.document import Document, new_document
from cad.io.native_format import CadSerializer
from cad.geometry.primitives import Box, Cylinder, Sphere


class TestSerialization(unittest.TestCase):
    def setUp(self) -> None:
        self.doc = new_document("TestDoc")

    def test_serialize_deserialize_empty_doc(self) -> None:
        data = CadSerializer.serialize(self.doc)
        loaded = CadSerializer.deserialize(data)
        self.assertEqual(loaded.name, "TestDoc")

    def test_serialize_with_objects(self) -> None:
        box = Box("Box1")
        box.set_property("width", 15)
        box.set_property("height", 25)
        self.doc.add_object(box)

        cyl = Cylinder("Cyl1")
        cyl.set_property("radius", 5)
        cyl.set_property("height", 20)
        self.doc.add_object(cyl)

        data = CadSerializer.serialize(self.doc)
        parsed = json.loads(data)
        self.assertEqual(parsed["name"], "TestDoc")
        self.assertEqual(len(parsed["objects"]), 2)
        self.assertEqual(parsed["objects"][0]["type"], "Box")

        loaded = CadSerializer.deserialize(data)
        self.assertEqual(loaded.object_count, 2)
        box_loaded = loaded.find_by_name("Box1")
        self.assertIsNotNone(box_loaded)

    def test_file_round_trip(self) -> None:
        self.doc.add_object(Box("TestBox"))
        self.doc.add_object(Sphere("TestSphere"))

        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "test.cad"
            CadSerializer.serialize_to_file(self.doc, path)
            self.assertTrue(path.exists())

            loaded = CadSerializer.deserialize_from_file(path)
            self.assertEqual(loaded.object_count, 2)
            self.assertIsNotNone(loaded.find_by_name("TestBox"))
            self.assertIsNotNone(loaded.find_by_name("TestSphere"))


if __name__ == "__main__":
    unittest.main()
