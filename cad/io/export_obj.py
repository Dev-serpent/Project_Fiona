"""OBJ export — Wavefront OBJ format."""

from __future__ import annotations

from pathlib import Path

from cad.core.document import Document


def export_obj(doc: Document, path: str | Path) -> None:
    """Export document to Wavefront OBJ format.

    Creates a simple vertex/face representation of all solid objects.
    """
    lines: list[str] = [
        "# Exported from CAD Platform",
        f"# Document: {doc.name}",
        f"# Objects: {doc.object_count}",
        "o CADModel",
    ]

    vertex_offset = 1
    for obj in doc.objects:
        obj_type = type(obj).__name__
        lines.append(f"g {obj.name}")

        if obj_type == "Box":
            w = obj.get_property_value("width") / 2
            h = obj.get_property_value("height") / 2
            d = obj.get_property_value("depth") / 2
            cx = obj.get_property_value("x")
            cy = obj.get_property_value("y")
            cz = obj.get_property_value("z")
            verts = [
                (cx-w, cy-h, cz-d), (cx+w, cy-h, cz-d),
                (cx+w, cy+h, cz-d), (cx-w, cy+h, cz-d),
                (cx-w, cy-h, cz+d), (cx+w, cy-h, cz+d),
                (cx+w, cy+h, cz+d), (cx-w, cy+h, cz+d),
            ]
            faces = [
                (1,2,3,4), (5,6,7,8), (1,5,8,4),
                (2,6,7,3), (1,2,6,5), (4,3,7,8),
            ]
            for vx, vy, vz in verts:
                lines.append(f"v {vx:.6f} {vy:.6f} {vz:.6f}")
            for f in faces:
                f_str = " ".join(str(vertex_offset + i - 1) for i in f)
                lines.append(f"f {f_str}")
            vertex_offset += len(verts)

    Path(path).write_text("\n".join(lines), encoding="utf-8")
