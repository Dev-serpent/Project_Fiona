"""Tests for part design features."""

from __future__ import annotations

import unittest

from cad.core.document import Document
from cad.geometry.primitives import Box
from cad.sketch.workspace import Sketch
from cad.part.features import (
    Pad, Pocket, Revolve, Loft, Sweep,
    Fillet, Chamfer, Shell,
    LinearPattern, CircularPattern, MirrorFeature,
)


class TestFeatures(unittest.TestCase):
    def setUp(self) -> None:
        self.doc = Document("test")
        self.sketch = Sketch("Sketch1")
        self.doc.add_object(self.sketch)

    def test_pad_creation(self) -> None:
        pad = Pad("Pad1", self.sketch, height=25.0)
        self.doc.add_object(pad)
        self.assertEqual(pad.get_property_value("height"), 25.0)
        self.assertFalse(pad.get_property_value("reverse"))

    def test_pad_reverse(self) -> None:
        pad = Pad("Pad1", self.sketch, height=10, reverse=True)
        self.doc.add_object(pad)
        self.assertTrue(pad.get_property_value("reverse"))

    def test_pad_recompute(self) -> None:
        pad = Pad("Pad1", self.sketch, height=10)
        self.doc.add_object(pad)
        self.assertTrue(pad.is_dirty())
        pad.recompute()
        self.assertFalse(pad.is_dirty())

    def test_pad_dependency(self) -> None:
        pad = Pad("Pad1", self.sketch, height=10)
        self.doc.add_object(pad)
        self.assertIn(str(self.sketch.uid), pad.get_dependencies())

    def test_pocket_creation(self) -> None:
        pocket = Pocket("Pocket1", self.sketch, depth=15)
        self.doc.add_object(pocket)
        self.assertEqual(pocket.get_property_value("depth"), 15)

    def test_revolve_creation(self) -> None:
        rev = Revolve("Rev1", self.sketch, angle=270, axis="x")
        self.doc.add_object(rev)
        self.assertEqual(rev.get_property_value("angle"), 270)
        self.assertEqual(rev.get_property_value("axis"), "x")

    def test_loft_creation(self) -> None:
        s2 = Sketch("Sketch2")
        self.doc.add_object(s2)
        loft = Loft("Loft1", [self.sketch, s2])
        self.doc.add_object(loft)
        self.assertEqual(loft.get_property_value("profile_count"), 2)

    def test_sweep_creation(self) -> None:
        path = Sketch("Path")
        self.doc.add_object(path)
        swp = Sweep("Sweep1", self.sketch, path)
        self.doc.add_object(swp)
        self.assertIn(str(self.sketch.uid), swp.get_dependencies())
        self.assertIn(str(path.uid), swp.get_dependencies())

    def test_fillet_creation(self) -> None:
        box = Box("Base")
        self.doc.add_object(box)
        fillet = Fillet("Fillet1", box, radius=3, edges=[0, 1, 2])
        self.doc.add_object(fillet)
        self.assertEqual(fillet.get_property_value("radius"), 3)
        self.assertEqual(fillet.get_property_value("edge_count"), 3)

    def test_chamfer_creation(self) -> None:
        box = Box("Base")
        self.doc.add_object(box)
        chamfer = Chamfer("Chamfer1", box, size=4)
        self.doc.add_object(chamfer)
        self.assertEqual(chamfer.get_property_value("size"), 4)

    def test_shell_creation(self) -> None:
        box = Box("Base")
        self.doc.add_object(box)
        shell = Shell("Shell1", box, thickness=1.5)
        self.doc.add_object(shell)
        self.assertEqual(shell.get_property_value("thickness"), 1.5)

    def test_linear_pattern(self) -> None:
        pad = Pad("Pad1", self.sketch, height=10)
        self.doc.add_object(pad)
        pattern = LinearPattern("Pattern1", pad, count_x=3, count_y=2,
                                spacing_x=20, spacing_y=30)
        self.doc.add_object(pattern)
        self.assertEqual(pattern.get_property_value("count_x"), 3)
        self.assertEqual(pattern.get_property_value("count_y"), 2)
        self.assertEqual(pattern.get_property_value("spacing_x"), 20)
        self.assertEqual(pattern.get_property_value("spacing_y"), 30)

    def test_circular_pattern(self) -> None:
        pad = Pad("Pad1", self.sketch, height=10)
        self.doc.add_object(pad)
        pattern = CircularPattern("Pattern1", pad, count=8, angle=360)
        self.doc.add_object(pattern)
        self.assertEqual(pattern.get_property_value("count"), 8)
        self.assertEqual(pattern.get_property_value("angle"), 360)

    def test_mirror_feature(self) -> None:
        pad = Pad("Pad1", self.sketch, height=10)
        self.doc.add_object(pad)
        mirror = MirrorFeature("Mirror1", pad, mirror_plane="yz")
        self.doc.add_object(mirror)
        self.assertEqual(mirror.get_property_value("mirror_plane"), "yz")

    def test_all_features_clean_after_recompute(self) -> None:
        features = [
            Pad("Pad1", self.sketch, height=10),
            Pocket("Pkt1", self.sketch, depth=5),
            Revolve("Rev1", self.sketch, angle=180),
        ]
        for f in features:
            self.doc.add_object(f)
            self.assertTrue(f.is_dirty())
        self.doc.recompute()
        for f in features:
            self.assertFalse(f.is_dirty(), f"{f.name} is still dirty")

    def test_feature_base_string(self) -> None:
        pad = Pad("Pad1", self.sketch, height=10)
        self.doc.add_object(pad)
        base = pad.get_property_value("base")
        self.assertEqual(base, "Sketch1")

    def test_feature_no_base(self) -> None:
        """Feature without base should have empty base string."""
        from cad.part.features import Feature
        f = Feature("BaseFeature")
        self.doc.add_object(f)
        self.assertEqual(f.get_property_value("base"), "")


if __name__ == "__main__":
    unittest.main()
