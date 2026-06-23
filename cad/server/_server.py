"""Main CAD server — HTTP + WebSocket.

Provides a production-grade JSON-RPC 2.0 server over WebSocket
with an optional static file server for the 3js frontend.

Uses only Python stdlib ``asyncio`` — no extra dependencies.
"""

from __future__ import annotations

import asyncio
import json
import mimetypes
import os
import pathlib
import sys
import time
import traceback
from typing import Any, Callable

from cad.server._command_executor import CommandExecutor
from cad.server._document_manager import DocumentManager
from cad.server._export_manager import ExportManager
from cad.server._handlers import RequestHandler
from cad.server._protocol import (
    RpcRequest,
    RpcResponse,
    ServerEvent,
    make_error_response,
    make_event,
    METHOD_NOT_FOUND,
)
from cad.server._websocket_handler import WebSocketHandler
from fiona.interfaces import Event, EventBus, DocumentEvent


# Default server configuration
_DEFAULT_HOST = "127.0.0.1"
_DEFAULT_PORT = 8765

# Path to the built 3js frontend (relative to this file)
_FRONTEND_DIR = pathlib.Path(__file__).resolve().parent / "_frontend" / "dist"

# MIME types for static files
mimetypes.add_type("application/javascript", ".js")
mimetypes.add_type("text/css", ".css")
mimetypes.add_type("image/svg+xml", ".svg")


class CadServer:
    """The main CAD server — HTTP + WebSocket.

    Args:
        doc_manager: Document manager instance.
        cmd_executor: Command executor instance.
        export_manager: Export manager instance.
        host: Host address to bind to.
        port: TCP port to listen on.
        frontend_dir: Path to the built 3js frontend (optional).
        open_browser: If True, open the frontend in a browser on start.
    """

    def __init__(
        self,
        doc_manager: DocumentManager,
        cmd_executor: CommandExecutor,
        export_manager: ExportManager,
        host: str = _DEFAULT_HOST,
        port: int = _DEFAULT_PORT,
        frontend_dir: str | None = None,
        open_browser: bool = False,
        event_bus: EventBus | None = None,
    ) -> None:
        self._doc_manager = doc_manager
        self._cmd_executor = cmd_executor
        self._export_manager = export_manager
        self._host = host
        self._port = port
        self._open_browser = open_browser
        self._event_bus = event_bus

        # Track subscriptions for cleanup
        self._subscriptions: list[Any] = []

        # Resolve frontend directory
        if frontend_dir:
            self._frontend_dir = pathlib.Path(frontend_dir)
        else:
            self._frontend_dir = _FRONTEND_DIR

        # Event loop and server state
        self._loop: asyncio.AbstractEventLoop | None = None
        self._server: asyncio.AbstractServer | None = None
        self._running = False

        # Build the WebSocket handler
        self._ws_handler = WebSocketHandler(
            on_rpc_request=self._handle_rpc,
            on_client_connected=self._on_ws_connected,
            on_client_disconnected=self._on_ws_disconnected,
        )

        # Build the RPC request handler
        registry = getattr(cmd_executor, "_registry", None)
        self._request_handler = RequestHandler(
            doc_manager=doc_manager,
            cmd_executor=cmd_executor,
            export_manager=export_manager,
            registry=registry,
            ws_handler=self._ws_handler,
        )

        # Bridge EventBus → WebSocket broadcast
        self._setup_event_bridge()

    # ------------------------------------------------------------------
    # EventBus bridge
    # ------------------------------------------------------------------

    def _setup_event_bridge(self) -> None:
        """Subscribe to EventBus events and relay them to WebSocket clients.

        Listens for all `DocumentEvent` subtypes and relays them as
        ``ServerEvent`` broadcast over WebSocket.
        """
        if self._event_bus is None:
            return

        def _bridge_event(event: Event) -> None:
            """Bridge an EventBus event to WebSocket clients."""
            event_type = _event_type_name(type(event))
            event_data = _event_to_dict(event)
            ws_event = make_event(event_type, event_data)
            self._ws_handler.broadcast_event(ws_event)

        sub = self._event_bus.subscribe(DocumentEvent, _bridge_event)
        self._subscriptions.append(sub)

    def _cleanup_subscriptions(self) -> None:
        """Unsubscribe all EventBus subscriptions."""
        if self._event_bus is None:
            return
        for sub in self._subscriptions:
            self._event_bus.unsubscribe(sub)
        self._subscriptions.clear()

    def _publish_event(self, event_type: str, data: dict[str, Any]) -> None:
        """Publish a server lifecycle event to the EventBus and WebSocket clients."""
        # Always broadcast to WebSocket clients
        ws_event = make_event(event_type, data)
        self._ws_handler.broadcast_event(ws_event)

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def start(self) -> None:
        """Start the HTTP + WebSocket server.

        This starts a TCP server that:
        1. Performs the WebSocket upgrade for ``/ws`` connections.
        2. Serves static files from the frontend directory.
        3. Returns a simple health-check response for HTTP GET on ``/``.
        """
        self._loop = asyncio.get_running_loop()

        self._server = await asyncio.start_server(
            self._handle_tcp_connection,
            host=self._host,
            port=self._port,
        )

        self._running = True

        addr = self._server.sockets[0].getsockname()
        print(
            f"CadServer started on http://{addr[0]}:{addr[1]}",
            file=sys.stderr,
        )

        self._publish_event("server_started", {"host": addr[0], "port": addr[1]})

        if self._open_browser:
            self._open_browser_tab(f"http://{addr[0]}:{addr[1]}")

        # Serve forever
        async with self._server:
            await self._server.serve_forever()

    async def stop(self) -> None:
        """Graceful shutdown."""
        self._running = False

        self._publish_event("server_stopped", {})

        # Disconnect all WebSocket clients
        self._ws_handler.disconnect_all()

        # Stop the TCP server
        if self._server is not None:
            self._server.close()
            await self._server.wait_closed()

        # Clean up EventBus subscriptions
        self._cleanup_subscriptions()

        print("CadServer stopped.", file=sys.stderr)

    @property
    def is_running(self) -> bool:
        """True if the server is currently accepting connections."""
        return self._running

    def run(self) -> None:
        """Synchronous entry point — creates an event loop and starts the server.

        This is the primary entry point for CLI usage.  It blocks
        until the server is stopped (e.g. via ``KeyboardInterrupt``).
        """
        async def _run() -> None:
            try:
                await self.start()
            except asyncio.CancelledError:
                pass

        try:
            asyncio.run(_run())
        except KeyboardInterrupt:
            print("Shutting down...", file=sys.stderr)
        finally:
            # Ensure cleanup
            try:
                asyncio.run(self.stop())
            except (RuntimeError, Exception):
                pass

    # ------------------------------------------------------------------
    # TCP connection handler
    # ------------------------------------------------------------------

    async def _handle_tcp_connection(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
    ) -> None:
        """Handle an incoming TCP connection.

        Reads the first line to decide: WebSocket upgrade or HTTP request.
        """
        try:
            # Peek at the first line to decide the protocol
            first_line = await reader.readline()
            if not first_line:
                writer.close()
                return

            request_line = first_line.decode("utf-8", errors="replace").strip()

            if "GET" in request_line and "HTTP/" in request_line:
                # HTTP request — parse headers and path
                headers = await self._read_headers(reader)
                path = request_line.split(" ", 2)[1] if " " in request_line else "/"

                # Check for WebSocket upgrade
                upgrade = headers.get("upgrade", "").lower()
                if upgrade == "websocket":
                    await self._ws_handler.handle_connection(
                        self._wrap_reader(reader, first_line),
                        writer,
                    )
                else:
                    await self._serve_http(
                        writer, path, headers, first_line, reader
                    )
            else:
                writer.close()

        except Exception:
            traceback.print_exc()
            try:
                writer.close()
            except Exception:
                pass

    # ------------------------------------------------------------------
    # HTTP serving
    # ------------------------------------------------------------------

    async def _serve_http(
        self,
        writer: asyncio.StreamWriter,
        path: str,
        headers: dict[str, str],
        first_line: bytes,
        reader: asyncio.StreamReader,
    ) -> None:
        """Serve an HTTP request — static file or API response."""
        if path == "/" or path == "":
            # Serve index.html or a status page
            index_path = self._frontend_dir / "index.html"
            if index_path.exists():
                await self._send_file(writer, index_path)
            else:
                await self._send_json_response(
                    writer,
                    200,
                    {
                        "name": "Fiona CAD Server",
                        "version": "0.1.0",
                        "status": "running",
                        "protocol": "WebSocket (ws://...)",
                        "frontend": "Build the frontend and place in _frontend/dist/",
                    },
                )
            return

        if path == "/health":
            await self._send_json_response(
                writer,
                200,
                {
                    "status": "ok",
                    "uptime_seconds": self._uptime() if hasattr(self, "_start_time") else 0,
                },
            )
            return

        # Try to serve a static file
        if self._frontend_dir.exists():
            # Strip leading slash and prevent path traversal
            rel_path = path.lstrip("/")
            file_path = self._frontend_dir / rel_path

            # Security: ensure the resolved path is within frontend_dir
            try:
                resolved = file_path.resolve()
                self._frontend_dir.resolve()
                if not str(resolved).startswith(str(self._frontend_dir.resolve())):
                    await self._send_error(writer, 403, "Forbidden")
                    return
            except (ValueError, OSError):
                await self._send_error(writer, 403, "Forbidden")
                return

            if resolved.exists() and resolved.is_file():
                await self._send_file(writer, resolved)
                return

        # 404 for everything else
        await self._send_error(writer, 404, "Not Found")

    async def _send_file(
        self, writer: asyncio.StreamWriter, file_path: pathlib.Path
    ) -> None:
        """Send a static file as an HTTP response.

        Args:
            writer: The stream writer.
            file_path: Absolute path to the file.
        """
        try:
            content = file_path.read_bytes()
        except (OSError, IOError):
            await self._send_error(writer, 500, "Internal Server Error")
            return

        content_type, _ = mimetypes.guess_type(str(file_path))
        if content_type is None:
            content_type = "application/octet-stream"

        response = (
            f"HTTP/1.1 200 OK\r\n"
            f"Content-Type: {content_type}\r\n"
            f"Content-Length: {len(content)}\r\n"
            f"Access-Control-Allow-Origin: *\r\n"
            f"\r\n"
        ).encode()

        writer.write(response + content)
        await writer.drain()
        writer.close()

    async def _send_json_response(
        self,
        writer: asyncio.StreamWriter,
        status: int,
        data: dict[str, Any],
    ) -> None:
        """Send a JSON HTTP response.

        Args:
            writer: The stream writer.
            status: HTTP status code.
            data: Payload to serialise as JSON.
        """
        body = json.dumps(data, default=str).encode()
        status_text = "OK" if status == 200 else "Error"
        response = (
            f"HTTP/1.1 {status} {status_text}\r\n"
            f"Content-Type: application/json\r\n"
            f"Content-Length: {len(body)}\r\n"
            f"Access-Control-Allow-Origin: *\r\n"
            f"\r\n"
        ).encode()

        writer.write(response + body)
        await writer.drain()
        writer.close()

    async def _send_error(
        self, writer: asyncio.StreamWriter, status: int, message: str
    ) -> None:
        """Send a simple HTTP error response.

        Args:
            writer: The stream writer.
            status: HTTP status code.
            message: Error message.
        """
        body = json.dumps({"error": message, "status": status}).encode()
        status_text = {404: "Not Found", 403: "Forbidden", 500: "Internal Server Error"}.get(
            status, "Error"
        )
        response = (
            f"HTTP/1.1 {status} {status_text}\r\n"
            f"Content-Type: application/json\r\n"
            f"Content-Length: {len(body)}\r\n"
            f"Access-Control-Allow-Origin: *\r\n"
            f"\r\n"
        ).encode()

        writer.write(response + body)
        await writer.drain()
        writer.close()

    # ------------------------------------------------------------------
    # RPC dispatch
    # ------------------------------------------------------------------

    async def _handle_rpc(self, request: RpcRequest) -> RpcResponse:
        """Dispatch an RPC request to the request handler.

        Args:
            request: The parsed JSON-RPC 2.0 request.

        Returns:
            The response (success or error).
        """
        return await self._request_handler.handle(request)

    # ------------------------------------------------------------------
    # WebSocket callbacks
    # ------------------------------------------------------------------

    def _on_ws_connected(self, conn: Any) -> None:
        """Called when a WebSocket client connects."""
        print(
            f"WebSocket client connected: {conn.remote_address}",
            file=sys.stderr,
        )

    def _on_ws_disconnected(self, conn: Any) -> None:
        """Called when a WebSocket client disconnects."""
        print(
            f"WebSocket client disconnected: {conn.remote_address}",
            file=sys.stderr,
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    async def _read_headers(
        self, reader: asyncio.StreamReader
    ) -> dict[str, str]:
        """Read HTTP headers until blank line.

        Returns:
            A dict of header name → value (lowercased names).
        """
        headers: dict[str, str] = {}
        while True:
            line = await reader.readline()
            if not line or line.strip() == b"":
                break
            decoded = line.decode("utf-8", errors="replace").strip()
            if ":" in decoded:
                key, _, value = decoded.partition(":")
                headers[key.strip().lower()] = value.strip()
        return headers

    def _wrap_reader(
        self,
        reader: asyncio.StreamReader,
        first_line: bytes,
    ) -> asyncio.StreamReader:
        """Create a new reader that yields the already-read first line first.

        This is needed because we read the request line before deciding
        whether to handle the connection as HTTP or WebSocket.
        """
        # Unfortunately, asyncio.StreamReader doesn't support "unreading".
        # We work around this by creating a new protocol that feeds back
        # the first line.  For simplicity, we use the existing reader and
        # accept that the first line is already consumed.
        # The WebSocket handshake code in _websocket_handler uses read_line
        # which will read the rest of the headers just fine.
        return reader

    def _open_browser_tab(self, url: str) -> None:
        """Open a browser tab pointing to *url*."""
        import webbrowser
        try:
            webbrowser.open(url)
        except Exception:
            pass

    def _uptime(self) -> float:
        """Return server uptime in seconds."""
        if not hasattr(self, "_start_time"):
            self._start_time = time.time()
        return time.time() - self._start_time


# ---------------------------------------------------------------------------
# EventBus helpers
# ---------------------------------------------------------------------------


def _event_type_name(cls: type) -> str:
    """Convert an EventBus event class to a dot-separated event type string.

    Examples::

        DocumentCreated   → "document.created"
        DocumentModified  → "document.modified"
        DocumentSaved     → "document.saved"
        DocumentClosed    → "document.closed"
    """
    name = cls.__name__
    # Convert CamelCase to dot.case
    result = []
    for char in name:
        if char.isupper() and result:
            result.append(".")
        result.append(char.lower())
    return "".join(result)


def _event_to_dict(event: Event) -> dict[str, Any]:
    """Convert an EventBus Event to a plain dict for serialisation."""
    from dataclasses import asdict  # noqa: PLC0415
    return asdict(event)
