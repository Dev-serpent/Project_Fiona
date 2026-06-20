"""
CAD Platform — FreeCAD-Inspired Parametric Modeling System
===========================================================

Architecture:
    CAD Core  →  Geometry Kernel  →  Command System  →  GUI / CLI / API Frontends

Design Principles:
    - All CAD logic lives in the kernel, never in GUI code.
    - Every operation is scriptable and command-driven.
    - Parametric dependencies form a DAG; changes propagate automatically.
    - The GUI is a replaceable frontend.

Entry Points:
    >>> import cad
    >>> doc = cad.new_document()
    >>> box = doc.add_object("Box", width=10, height=20, depth=30)
    >>> doc.recompute()
"""

from cad.core.document import Document, new_document
from cad.core.object import CADObject
from cad.commands.registry import CommandRegistry
from cad.commands.builtins import register_builtin_commands

__all__ = [
    "Document",
    "CADObject",
    "CommandRegistry",
    "new_document",
]

__version__ = "0.1.0"
