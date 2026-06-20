"""Part design — features like Pad, Pocket, Revolve, Fillet, Chamfer, etc."""

from cad.part.features import (
    Pad, Pocket, Revolve, Loft, Sweep,
    Fillet, Chamfer, Shell,
    LinearPattern, CircularPattern, MirrorFeature,
)

__all__ = [
    "Pad", "Pocket", "Revolve", "Loft", "Sweep",
    "Fillet", "Chamfer", "Shell",
    "LinearPattern", "CircularPattern", "MirrorFeature",
]
