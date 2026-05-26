from __future__ import annotations

from dataclasses import dataclass
from io import StringIO
from typing import Any

import numpy as np
import pandas as pd


DEFAULT_POINTS_TEXT = """id,x,y,z
A,-1,-1,-1
B,1,-1,-1
C,1,1,-1
D,-1,1,-1
E,-1,-1,1
F,1,-1,1
G,1,1,1
H,-1,1,1
"""

DEFAULT_EDGES_TEXT = """source,target
A,B
B,C
C,D
D,A
E,F
F,G
G,H
H,E
A,E
B,F
C,G
D,H
"""


class VseeModelError(ValueError):
    """Raised when a Vsee hologram model cannot be built."""


@dataclass(frozen=True)
class HologramModel:
    points: pd.DataFrame
    edges: pd.DataFrame

    @classmethod
    def from_text(cls, points_text: str, edges_text: str) -> HologramModel:
        points = _read_csv_text(points_text, required_columns=("id", "x", "y", "z"), name="points")
        edges = _read_csv_text(edges_text, required_columns=("source", "target"), name="edges")

        points = points.copy()
        points["id"] = points["id"].astype(str)
        for axis in ("x", "y", "z"):
            points[axis] = pd.to_numeric(points[axis], errors="raise")

        edges = edges.copy()
        edges["source"] = edges["source"].astype(str)
        edges["target"] = edges["target"].astype(str)

        duplicate_ids = points["id"][points["id"].duplicated()].tolist()
        if duplicate_ids:
            raise VseeModelError(f"duplicate point id(s): {', '.join(duplicate_ids)}")

        point_ids = set(points["id"])
        missing_ids = sorted((set(edges["source"]) | set(edges["target"])) - point_ids)
        if missing_ids:
            raise VseeModelError(f"edge references missing point id(s): {', '.join(missing_ids)}")

        return cls(points=points[["id", "x", "y", "z"]], edges=edges[["source", "target"]])

    @classmethod
    def cube(cls) -> HologramModel:
        return cls.from_text(DEFAULT_POINTS_TEXT, DEFAULT_EDGES_TEXT)

    def projected(
        self,
        *,
        width: int,
        height: int,
        rotation_x_degrees: float = 20.0,
        rotation_y_degrees: float = -30.0,
        scale: float = 130.0,
        camera_distance: float = 5.0,
    ) -> dict[str, Any]:
        vectors = self.points[["x", "y", "z"]].to_numpy(dtype=float)
        rotated = vectors @ _rotation_matrix(rotation_x_degrees, rotation_y_degrees).T
        z = rotated[:, 2]
        perspective = camera_distance / np.maximum(camera_distance + z, 0.2)
        x = width / 2 + rotated[:, 0] * scale * perspective
        y = height / 2 - rotated[:, 1] * scale * perspective

        points = {
            point_id: (float(x_pos), float(y_pos), float(z_pos))
            for point_id, x_pos, y_pos, z_pos in zip(self.points["id"], x, y, z, strict=True)
        }
        edges = [(str(edge.source), str(edge.target)) for edge in self.edges.itertuples(index=False)]
        return {"points": points, "edges": edges}


def _read_csv_text(text: str, *, required_columns: tuple[str, ...], name: str) -> pd.DataFrame:
    if not text.strip():
        raise VseeModelError(f"{name} table is empty")
    try:
        frame = pd.read_csv(StringIO(text.strip()))
    except Exception as exc:
        raise VseeModelError(f"could not parse {name} table: {exc}") from exc

    missing_columns = [column for column in required_columns if column not in frame.columns]
    if missing_columns:
        raise VseeModelError(f"{name} table missing column(s): {', '.join(missing_columns)}")
    return frame


def _rotation_matrix(rotation_x_degrees: float, rotation_y_degrees: float) -> np.ndarray:
    rx = np.deg2rad(rotation_x_degrees)
    ry = np.deg2rad(rotation_y_degrees)

    x_matrix = np.array(
        [
            [1.0, 0.0, 0.0],
            [0.0, np.cos(rx), -np.sin(rx)],
            [0.0, np.sin(rx), np.cos(rx)],
        ]
    )
    y_matrix = np.array(
        [
            [np.cos(ry), 0.0, np.sin(ry)],
            [0.0, 1.0, 0.0],
            [-np.sin(ry), 0.0, np.cos(ry)],
        ]
    )
    return y_matrix @ x_matrix
