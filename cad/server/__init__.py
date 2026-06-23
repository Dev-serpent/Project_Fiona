"""CAD server — JSON-RPC 2.0 over WebSocket + HTTP.

Provides the server-side infrastructure for the Fiona CAD platform's
future 3js frontend.  The server exposes the CAD kernel (documents,
commands, undo/redo, export) through a WebSocket-based JSON-RPC 2.0
protocol.

Quick-start::

    from cad.server import run_server
    run_server(host="127.0.0.1", port=8765)
"""

from cad.server._app_builder import create_app_container, build_export_manager, run_server
from cad.server._command_executor import CommandExecutor
from cad.server._document_manager import DocumentManager
from cad.server._export_manager import ExportManager
from cad.server._server import CadServer

__all__ = [
    "CadServer",
    "DocumentManager",
    "CommandExecutor",
    "ExportManager",
    "create_app_container",
    "build_export_manager",
    "run_server",
]
