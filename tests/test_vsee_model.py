from __future__ import annotations

import unittest

from Vsee import DEFAULT_EDGES_TEXT, DEFAULT_POINTS_TEXT, HologramModel, VseeModelError


class VseeModelTests(unittest.TestCase):
    def test_cube_model_projects_points_and_edges(self) -> None:
        model = HologramModel.from_text(DEFAULT_POINTS_TEXT, DEFAULT_EDGES_TEXT)

        projected = model.projected(width=640, height=480)

        self.assertEqual(len(projected["points"]), 8)
        self.assertEqual(len(projected["edges"]), 12)
        self.assertIn("A", projected["points"])

    def test_rejects_edge_with_missing_point(self) -> None:
        with self.assertRaises(VseeModelError):
            HologramModel.from_text("id,x,y,z\nA,0,0,0\n", "source,target\nA,B\n")

    def test_rejects_duplicate_point_ids(self) -> None:
        with self.assertRaises(VseeModelError):
            HologramModel.from_text("id,x,y,z\nA,0,0,0\nA,1,0,0\n", "source,target\nA,A\n")


if __name__ == "__main__":
    unittest.main()
