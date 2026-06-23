"""Application builder — wires together the CAD server components.

Provides factory functions and a convenience builder that registers
all services in a :class:`FionaContainer`.
"""

from __future__ import annotations

from cad.commands.builtins import register_builtin_commands
from cad.commands.registry import CommandRegistry
from cad.server._command_executor import CommandExecutor
from cad.server._document_manager import DocumentManager
from cad.server._export_manager import (
    ExportManager,
    ObjExportProvider,
    StlExportProvider,
    SvgExportProvider,
)
from cad.server._server import CadServer
from fiona.di import FionaContainer
from fiona.interfaces import EventBus


def create_app_container() -> FionaContainer:
    """Build a fully wired production container for the CAD server.

    Returns:
        A :class:`FionaContainer` with all services registered::

            - ``event_bus`` — :class:`EventBus` instance
            - ``command_registry`` — pre-populated :class:`CommandRegistry`
            - ``document_manager`` — :class:`DocumentManager` singleton
            - ``command_executor`` — :class:`CommandExecutor` singleton
            - ``export_manager`` — :class:`ExportManager` with built-in providers
            - ``cad_server`` — :class:`CadServer` singleton
    """
    container = FionaContainer()

    # Event bus
    event_bus = EventBus()
    container.register_instance("event_bus", event_bus)

    # Command registry with built-in commands
    registry = CommandRegistry()
    register_builtin_commands(registry)
    container.register_instance("command_registry", registry)

    # Document manager (wired to EventBus)
    doc_manager = DocumentManager(event_bus=event_bus)
    container.register_instance("document_manager", doc_manager)

    # Command executor
    cmd_executor = CommandExecutor(registry=registry, doc_manager=doc_manager)
    container.register_instance("command_executor", cmd_executor)

    # Export manager with built-in providers
    export_manager = build_export_manager()
    container.register_instance("export_manager", export_manager)

    return container


def build_export_manager() -> ExportManager:
    """Create an :class:`ExportManager` with built-in export providers.

    Registers STL, OBJ, and SVG providers.

    Returns:
        A fully configured :class:`ExportManager`.
    """
    manager = ExportManager()
    manager.register(StlExportProvider())
    manager.register(ObjExportProvider())
    manager.register(SvgExportProvider())
    return manager


def run_server(
    host: str = "127.0.0.1",
    port: int = 8765,
    open_browser: bool = False,
    frontend_dir: str | None = None,
) -> None:
    """Create and start the CAD server (blocking).

    This is a convenience entry point for the CLI and scripts.

    Args:
        host: Host address to bind to.
        port: TCP port to listen on.
        open_browser: If True, open the frontend in a browser.
        frontend_dir: Path to the built 3js frontend (optional).
    """
    container = create_app_container()
    doc_manager = container.resolve("document_manager")
    cmd_executor = container.resolve("command_executor")
    export_manager = container.resolve("export_manager")

    event_bus = container.resolve("event_bus")

    server = CadServer(
        doc_manager=doc_manager,
        cmd_executor=cmd_executor,
        export_manager=export_manager,
        host=host,
        port=port,
        frontend_dir=frontend_dir,
        open_browser=open_browser,
        event_bus=event_bus,
    )
    server.run()
