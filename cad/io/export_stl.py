"""STL export — tessellated triangle mesh output."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from cad.core.document import Document
from cad.geometry.primitives import Box, Cylinder, Sphere


def export_stl(doc: Document, path: str | Path,
               solid_name: str = "CADModel") -> None:
    """Export document solids to STL (ASCII format).

    Creates a simple tessellated representation of each solid.
    For production, this would use a proper mesh generation library.
    """
    lines: list[str] = [f"solid {solid_name}"]

    for obj in doc.objects:
        if isinstance(obj, Box):
            _write_box_stl(obj, lines)
        elif isinstance(obj, Cylinder):
            _write_cylinder_stl(obj, lines)
        elif isinstance(obj, Sphere):
            _write_sphere_stl(obj, lines)

    lines.append(f"endsolid {solid_name}")
    Path(path).write_text("\n".join(lines), encoding="utf-8")


def _facet(nx: float, ny: float, nz: float,
           v: list[tuple[float, float, float]], lines: list[str]) -> None:
    lines.append(f"  facet normal {nx:.6f} {ny:.6f} {nz:.6f}")
    lines.append("    outer loop")
    for x, y, z in v:
        lines.append(f"      vertex {x:.6f} {y:.6f} {z:.6f}")
    lines.append("    endloop")
    lines.append("  endfacet")


def _write_box_stl(box: Box, lines: list[str]) -> None:
    w = box.get_property_value("width") / 2
    h = box.get_property_value("height") / 2
    d = box.get_property_value("depth") / 2
    cx = box.get_property_value("x")
    cy = box.get_property_value("y")
    cz = box.get_property_value("z")

    v = [
        (cx-w, cy-h, cz-d), (cx+w, cy-h, cz-d),
        (cx+w, cy+h, cz-d), (cx-w, cy+h, cz-d),
        (cx-w, cy-h, cz+d), (cx+w, cy-h, cz+d),
        (cx+w, cy+h, cz+d), (cx-w, cy+h, cz+d),
    ]

    # 6 faces, 2 triangles each
    faces = [
        (0,1,2,3), (4,5,6,7),  # front, back
        (0,4,7,3), (1,5,6,2),  # left, right
        (0,1,5,4), (3,2,6,7),  # bottom, top
    ]
    norms = [
        (0,0,-1), (0,0,1),
        (-1,0,0), (1,0,0),
        (0,-1,0), (0,1,0),
    ]
    for (i,j,k,l), (nx,ny,nz) in zip(faces, norms):
        _facet(nx, ny, nz, [v[i], v[j], v[k]], lines)
        _facet(nx, ny, nz, [v[i], v[k], v[l]], lines)


def _write_cylinder_stl(cyl: Cylinder, lines: list[str]) -> None:
    r = cyl.get_property_value("radius")
    h = cyl.get_property_value("height")
    cx = cyl.get_property_value("x")
    cy = cyl.get_property_value("y")
    cz = cyl.get_property_value("z")
    seg = 24

    top = [(cx + r * math.cos(2*math.pi*i/seg),
            cy + r * math.sin(2*math.pi*i/seg),
            cz + h/2) for i in range(seg)]
    bot = [(cx + r * math.cos(2*math.pi*i/seg),
            cy + r * math.sin(2*math.pi*i/seg),
            cz - h/2) for i in range(seg)]

    # Side triangles
    for i in range(seg):
        j = (i + 1) % seg
        _facet(0, 0, 1, [top[i], bot[j], bot[i]], lines)
        _facet(0, 0, 1, [top[i], top[j], bot[j]], lines)

    # Top and bottom caps
    for i in range(seg):
        j = (i + 1) % seg
        _facet(0, 0, 1, [(cx, cy, cz+h/2), top[j], top[i]], lines)
        _facet(0, 0, -1, [(cx, cy, cz-h/2), bot[i], bot[j]], lines)


def _write_sphere_stl(sph: Sphere, lines: list[str]) -> None:
    r = sph.get_property_value("radius")
    cx = sph.get_property_value("x")
    cy = sph.get_property_value("y")
    cz = sph.get_property_value("z")
    seg = 20

    verts = []
    for i in range(seg + 1):
        theta = math.pi * i / seg
        for j in range(seg):
            phi = 2 * math.pi * j / seg
            verts.append((
                cx + r * math.sin(theta) * math.cos(phi),
                cy + r * math.sin(theta) * math.sin(phi),
                cz + r * math.cos(theta),
            ))

    for i in range(seg):
        for j in range(seg):
            a = i * seg + j
            b = (i + 1) * seg + j
            c = i * seg + (j + 1) % seg
            d = (i + 1) * seg + (j + 1) % seg
            lst = [verts[a], verts[b], verts[d]]
            _facet(0, 0, 1, lst, lines)
            _facet(0, 0, 1, [verts[a], verts[d], verts[c]], lines)


import math  # noqa: E402
