"""SVG export — 2D vector output of sketches and drawings."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from cad.core.document import Document
from cad.sketch.workspace import Sketch


def export_svg(doc: Document, path: str | Path,
               width: int = 800, height: int = 600) -> None:
    """Export sketch geometry to SVG.

    Looks for Sketch objects in the document and renders them as 2D SVG paths.
    """
    lines: list[str] = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'width="{width}" height="{height}" '
        f'viewBox="{-width/2} {-height/2} {width} {height}">',
        f'  <rect x="{-width/2}" y="{-height/2}" '
        f'width="{width}" height="{height}" fill="#05070a"/>',
    ]

    for obj in doc.objects:
        if not isinstance(obj, Sketch):
            continue

        for entity in obj.entities:
            etype = type(entity).__name__
            if etype == "Line":
                x1 = entity.get_property_value("x1")
                y1 = entity.get_property_value("y1")
                x2 = entity.get_property_value("x2")
                y2 = entity.get_property_value("y2")
                lines.append(
                    f'  <line x1="{x1:.3f}" y1="{-y1:.3f}" '
                    f'x2="{x2:.3f}" y2="{-y2:.3f}" '
                    f'stroke="#2fffd3" stroke-width="2"/>'
                )
            elif etype == "Circle":
                cx = entity.get_property_value("cx")
                cy = entity.get_property_value("cy")
                r = entity.get_property_value("radius")
                lines.append(
                    f'  <circle cx="{cx:.3f}" cy="{-cy:.3f}" '
                    f'r="{r:.3f}" stroke="#35a7ff" '
                    f'stroke-width="2" fill="none"/>'
                )

    lines.append("</svg>")
    Path(path).write_text("\n".join(lines), encoding="utf-8")
