"""CLI entry point — run CAD operations from the terminal.

Usage:
    cadcli create_box --width 10 --height 20 --depth 30
    cadcli create_cylinder --radius 5 --height 15
    cadcli extrude --sketch Sketch1 --height 25
    cadcli export model.stl
    cadcli run script.py
    cadcli list
    cadcli gui          # Launch the GUI
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

from cad.core.document import Document, new_document
from cad.commands.registry import CommandRegistry
from cad.commands.builtins import register_builtin_commands
from cad.io.native_format import CadSerializer


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="cadcli",
        description="CAD Platform CLI — parametric 3D modeling from the terminal",
    )
    parser.add_argument("--doc", default=None,
                        help="Load existing .cad document")

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # gui
    subparsers.add_parser("gui", help="Launch the CAD GUI")

    # create_box
    box_p = subparsers.add_parser("create_box", aliases=["box"],
                                   help="Create a box primitive")
    box_p.add_argument("--width", "-W", type=float, default=10.0)
    box_p.add_argument("--height", "-H", type=float, default=10.0)
    box_p.add_argument("--depth", "-D", type=float, default=10.0)
    box_p.add_argument("--name", "-n", default="Box")

    # create_cylinder
    cyl_p = subparsers.add_parser("create_cylinder", aliases=["cylinder"],
                                   help="Create a cylinder")
    cyl_p.add_argument("--radius", "-r", type=float, default=5.0)
    cyl_p.add_argument("--height", "-H", type=float, default=15.0)
    cyl_p.add_argument("--name", "-n", default="Cylinder")

    # create_sphere
    sph_p = subparsers.add_parser("create_sphere", aliases=["sphere"],
                                   help="Create a sphere")
    sph_p.add_argument("--radius", "-r", type=float, default=10.0)
    sph_p.add_argument("--name", "-n", default="Sphere")

    # extrude
    ext_p = subparsers.add_parser("extrude", help="Extrude a sketch")
    ext_p.add_argument("--sketch", "-s", required=True)
    ext_p.add_argument("--height", "-H", type=float, default=10.0)

    # export
    export_p = subparsers.add_parser("export", help="Export document")
    export_p.add_argument("path", help="Output file path (.stl, .obj, .svg, .cad)")

    # list
    subparsers.add_parser("list", aliases=["ls"],
                           help="List all objects in the document")

    # save
    save_p = subparsers.add_parser("save", help="Save document to .cad file")
    save_p.add_argument("path", nargs="?", default=None,
                        help="Output path (default: document name)")

    # run
    run_p = subparsers.add_parser("run", help="Execute a Python CAD script")
    run_p.add_argument("script", help="Path to .py script file")

    # info
    subparsers.add_parser("info", help="Show document info")

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    registry = CommandRegistry()
    register_builtin_commands(registry)

    # Load or create document
    if args.doc:
        doc_path = Path(args.doc)
        if doc_path.exists():
            doc = CadSerializer.deserialize_from_file(str(doc_path))
        else:
            doc = new_document(doc_path.stem)
            doc._file_path = str(doc_path)  # remember where to save
    else:
        doc = new_document()

    if args.command is None:
        parser.print_help()
        return 0

    try:
        if args.command == "gui":
            from cad.gui.main_window import CadMainWindow
            app = CadMainWindow()
            app.run()

        elif args.command in ("create_box", "box"):
            result = registry.execute("create_box", doc,
                                       width=args.width, height=args.height,
                                       depth=args.depth, name=args.name)
            doc.recompute()
            print(f"Created {result}")

        elif args.command in ("create_cylinder", "cylinder"):
            result = registry.execute("create_cylinder", doc,
                                       radius=args.radius, height=args.height,
                                       name=args.name)
            doc.recompute()
            print(f"Created {result}")

        elif args.command in ("create_sphere", "sphere"):
            result = registry.execute("create_sphere", doc,
                                       radius=args.radius, name=args.name)
            doc.recompute()
            print(f"Created {result}")

        elif args.command == "extrude":
            result = registry.execute("extrude", doc,
                                       sketch=args.sketch, height=args.height)
            doc.recompute()
            print(f"Created {result}")

        elif args.command == "export":
            path = args.path
            ext = Path(path).suffix.lower()
            if ext == ".stl":
                from cad.io.export_stl import export_stl
                export_stl(doc, path)
            elif ext == ".obj":
                from cad.io.export_obj import export_obj
                export_obj(doc, path)
            elif ext == ".svg":
                from cad.io.export_svg import export_svg
                export_svg(doc, path)
            elif ext == ".cad":
                CadSerializer.serialize_to_file(doc, path)
            else:
                print(f"Unknown export format: {ext}")
                return 1
            print(f"Exported to {path}")

        elif args.command in ("list", "ls"):
            for obj in doc.objects:
                print(f"  {obj.name:20s} {type(obj).__name__}")

        elif args.command == "save":
            path = args.path or f"{doc.name}.cad"
            CadSerializer.serialize_to_file(doc, path)
            print(f"Saved to {path}")

        elif args.command == "run":
            from cad.scripting.console import execute_script
            output = execute_script(args.script, registry, doc)
            print(output)

        elif args.command == "info":
            print(f"Document: {doc.name}")
            print(f"Objects:  {doc.object_count}")
            print(f"Commands: {len(registry.commands)}")
            print(f"Path:     {args.doc or '(new)'}")

    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    # Auto-save after mutation commands when --doc is specified
    if args.doc and args.command in ("create_box", "box", "create_cylinder", "cylinder",
                                      "create_sphere", "sphere", "extrude",
                                      "revolve", "add_constraint", "save"):
        doc_path = Path(args.doc)
        if args.command != "save":  # don't double-save
            CadSerializer.serialize_to_file(doc, str(doc_path))

    return 0


if __name__ == "__main__":
    sys.exit(main())
