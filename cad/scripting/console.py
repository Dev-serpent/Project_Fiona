"""Python scripting console for interactive CAD automation."""

from __future__ import annotations

import sys
import traceback
from io import StringIO
from typing import Any

from cad.core.document import Document, active_document
from cad.commands.registry import CommandRegistry


class ScriptingConsole:
    """Interactive Python scripting console for CAD automation.

    Users can execute arbitrary Python code against the CAD API.
    The console exposes 'doc' (active document), 'cmd' (command registry),
    and all CAD geometry primitives as built-in names.
    """

    def __init__(self, registry: CommandRegistry,
                 doc: Document | None = None) -> None:
        self.registry = registry
        self._doc = doc if doc is not None else active_document()
        self._locals: dict[str, Any] = self._build_environment()
        self._history: list[str] = []
        self._output: list[str] = []

    def _build_environment(self) -> dict[str, Any]:
        """Build the scripting environment with CAD API names."""
        env = {
            "doc": self._doc,
            "cmd": self.registry,
            "Document": Document,
            "__builtins__": __builtins__,
        }

        # Expose geometry primitives
        from cad.geometry.primitives import (
            Box, Cylinder, Cone, Sphere, Torus,
            Line, Circle, Arc, Point2D, Point3D, Polygon,
        )
        for cls in (Box, Cylinder, Cone, Sphere, Torus,
                    Line, Circle, Arc, Point2D, Point3D, Polygon):
            env[cls.__name__] = cls

        # Expose part features
        from cad.part.features import Pad, Pocket, Revolve, Fillet, Chamfer
        for cls in (Pad, Pocket, Revolve, Fillet, Chamfer):
            env[cls.__name__] = cls

        # Expose useful math
        from cad.geometry.math import Vector2, Vector3, Matrix4, Plane
        env["Vector2"] = Vector2
        env["Vector3"] = Vector3
        env["Matrix4"] = Matrix4
        env["Plane"] = Plane

        # Expose all registered commands as callables
        # Each command becomes a function that calls cmd.execute()
        def _make_command_fn(cmd_name: str):
            def _fn(**kwargs):
                return self.registry.execute(cmd_name, self._doc, **kwargs)
            _fn.__name__ = cmd_name
            _fn.__doc__ = self.registry.get(cmd_name).description if self.registry.get(cmd_name) else ""
            return _fn

        for cmd_name in self.registry.list_names():
            fn = _make_command_fn(cmd_name)
            env[cmd_name] = fn

        # Add a general-purpose `recompute()` function
        def _recompute() -> None:
            if self._doc:
                self._doc.recompute()
        env["recompute"] = _recompute

        return env

    @property
    def output(self) -> list[str]:
        return list(self._output)

    @property
    def history(self) -> list[str]:
        return list(self._history)

    def execute(self, code: str) -> str:
        """Execute a Python statement or expression.

        Returns output text (stdout capture + return value).
        """
        self._history.append(code)
        old_stdout = sys.stdout
        captured = StringIO()
        sys.stdout = captured

        result_text = ""
        try:
            # Try as expression first
            compiled = compile(code, "<cad_console>", "single")
            exec(compiled, self._locals)
            output = captured.getvalue()
            if output:
                result_text = output.rstrip()
        except SyntaxError:
            # Try as statement block
            try:
                compiled = compile(code, "<cad_console>", "exec")
                exec(compiled, self._locals)
                output = captured.getvalue()
                if output:
                    result_text = output.rstrip()
            except Exception as exc:
                result_text = f"Error: {traceback.format_exc()}"
        except Exception as exc:
            result_text = f"Error: {traceback.format_exc()}"
        finally:
            sys.stdout = old_stdout

        if result_text:
            self._output.append(result_text)
        return result_text

    def execute_file(self, path: str) -> str:
        """Execute a Python script file in the console environment."""
        with open(path) as f:
            code = f.read()
        return self.execute(code)

    def get_var(self, name: str) -> Any:
        return self._locals.get(name)

    def clear_output(self) -> None:
        self._output.clear()

    def reset_environment(self) -> None:
        self._locals = self._build_environment()


def execute_script(script_path: str, registry: CommandRegistry,
                   doc: Document) -> str:
    """Execute a CAD script file and return output."""
    console = ScriptingConsole(registry, doc)
    return console.execute_file(script_path)
