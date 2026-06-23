"""WebSocket handler for the CAD server.

Implements the WebSocket protocol (RFC 6455) using only stdlib asyncio
primitives.  Handles the HTTP upgrade handshake, frame parsing/generation,
heartbeat pings, and connection lifecycle management.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import struct
import time
from base64 import b64encode
from enum import Enum
from typing import Any, Callable

from cad.server._protocol import (
    RpcRequest,
    RpcResponse,
    ServerEvent,
    decode_request,
    encode_event,
    encode_response,
    make_error_response,
    PARSE_ERROR,
    INTERNAL_ERROR,
)


# ---------------------------------------------------------------------------
# Connection lifecycle states
# ---------------------------------------------------------------------------


class ConnectionState(Enum):
    CONNECTING = "CONNECTING"
    CONNECTED = "CONNECTED"
    RECONNECTING = "RECONNECTING"
    DISCONNECTED = "DISCONNECTED"


# ---------------------------------------------------------------------------
# WebSocket constants
# ---------------------------------------------------------------------------

_WS_MAGIC = b"258EAFA5-E914-47DA-95CA-C5AB0DC85B11"
_HEARTBEAT_INTERVAL = 30  # seconds
_MAX_FRAME_SIZE = 2 ** 20  # 1 MiB

# Opcodes
OP_CONTINUATION = 0x0
OP_TEXT = 0x1
OP_BINARY = 0x2
OP_CLOSE = 0x8
OP_PING = 0x9
OP_PONG = 0xA


# ---------------------------------------------------------------------------
# WebSocket connection
# ---------------------------------------------------------------------------


class WebSocketConnection:
    """Represents a single WebSocket connection.

    Handles the HTTP upgrade, frame I/O, and lifecycle callbacks.
    """

    def __init__(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
        on_message: Callable[[WebSocketConnection, str], None] | None = None,
        on_close: Callable[[WebSocketConnection], None] | None = None,
    ) -> None:
        self._reader = reader
        self._writer = writer
        self._on_message = on_message
        self._on_close = on_close
        self.state = ConnectionState.CONNECTING
        self._close_reason: str = ""
        self._last_pong = time.time()

    # ------------------------------------------------------------------
    # HTTP upgrade
    # ------------------------------------------------------------------

    async def perform_handshake(self) -> bool:
        """Read the HTTP upgrade request and send the WebSocket handshake response.

        Returns:
            True if the handshake succeeded and the connection is upgraded.
        """
        try:
            request_line = await self._read_line()
            if not request_line:
                return False

            headers = await self._read_headers()

            # Validate the upgrade headers
            key = headers.get("Sec-WebSocket-Key", "")
            if not key:
                return False

            # Build the accept key
            accept = b64encode(
                hashlib.sha1(key.encode() + _WS_MAGIC).digest()
            ).decode()

            # Send the upgrade response
            response = (
                "HTTP/1.1 101 Switching Protocols\r\n"
                "Upgrade: websocket\r\n"
                "Connection: Upgrade\r\n"
                f"Sec-WebSocket-Accept: {accept}\r\n"
                "\r\n"
            )
            self._writer.write(response.encode())
            await self._writer.drain()

            self.state = ConnectionState.CONNECTED
            return True

        except Exception:
            self.state = ConnectionState.DISCONNECTED
            return False

    # ------------------------------------------------------------------
    # Frame I/O
    # ------------------------------------------------------------------

    async def send_text(self, payload: str) -> None:
        """Send a text frame.

        Args:
            payload: UTF-8 encoded text string.
        """
        data = payload.encode("utf-8")
        await self._send_frame(OP_TEXT, data)

    async def send_bytes(self, data: bytes) -> None:
        """Send a binary frame.

        Args:
            data: Raw binary data.
        """
        await self._send_frame(OP_BINARY, data)

    async def send_close(self, code: int = 1000, reason: str = "") -> None:
        """Send a close frame.

        Args:
            code: WebSocket close code.
            reason: Human-readable close reason.
        """
        payload = struct.pack("!H", code) + reason.encode("utf-8")
        await self._send_frame(OP_CLOSE, payload)
        self.state = ConnectionState.DISCONNECTED

    async def send_ping(self) -> None:
        """Send a ping frame."""
        await self._send_frame(OP_PING, b"")

    async def recv_frame(self) -> tuple[int, bytes]:
        """Receive a single WebSocket frame.

        Returns:
            A tuple of ``(opcode, payload)``.

        Raises:
            ConnectionError: The connection is closed or the frame is invalid.
        """
        try:
            # Read the frame header (2 bytes minimum)
            header = await self._reader.readexactly(2)
        except (asyncio.IncompleteReadError, ConnectionError):
            raise ConnectionError("Connection closed") from None

        b0, b1 = header[0], header[1]
        opcode = b0 & 0x0F
        masked = (b1 & 0x80) != 0
        length = b1 & 0x7F

        # Extended payload length
        if length == 126:
            raw = await self._reader.readexactly(2)
            length = struct.unpack("!H", raw)[0]
        elif length == 127:
            raw = await self._reader.readexactly(8)
            length = struct.unpack("!Q", raw)[0]

        if length > _MAX_FRAME_SIZE:
            raise ConnectionError(f"Frame too large: {length} > {_MAX_FRAME_SIZE}")

        # Masking key (if present)
        mask_key: bytes | None = None
        if masked:
            mask_key = await self._reader.readexactly(4)

        # Payload
        payload = b""
        if length > 0:
            payload = await self._reader.readexactly(length)

        # Unmask if needed
        if mask_key is not None and payload:
            payload = bytes(b ^ mask_key[i % 4] for i, b in enumerate(payload))

        return opcode, payload

    # ------------------------------------------------------------------
    # Message loop
    # ------------------------------------------------------------------

    async def read_messages(self) -> None:
        """Continuously read frames from the connection.

        Dispatches text/binary messages to ``on_message`` and handles
        control frames (ping/pong/close) automatically.
        """
        try:
            while self.state == ConnectionState.CONNECTED:
                opcode, payload = await self.recv_frame()

                if opcode == OP_TEXT:
                    text = payload.decode("utf-8")
                    if self._on_message:
                        self._on_message(self, text)

                elif opcode == OP_BINARY:
                    if self._on_message:
                        self._on_message(self, payload.decode("utf-8", errors="replace"))

                elif opcode == OP_CLOSE:
                    code = 1000
                    reason = ""
                    if len(payload) >= 2:
                        code = struct.unpack("!H", payload[:2])[0]
                        reason = payload[2:].decode("utf-8", errors="replace")
                    self._close_reason = reason
                    await self.send_close(code, reason)
                    break

                elif opcode == OP_PING:
                    await self._send_frame(OP_PONG, payload)

                elif opcode == OP_PONG:
                    self._last_pong = time.time()

        except (ConnectionError, asyncio.CancelledError):
            pass
        finally:
            self.state = ConnectionState.DISCONNECTED
            if self._on_close:
                self._on_close(self)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    async def _send_frame(self, opcode: int, payload: bytes) -> None:
        """Send a WebSocket frame.

        Args:
            opcode: Frame opcode.
            payload: Frame payload bytes.
        """
        if self.state == ConnectionState.DISCONNECTED:
            raise ConnectionError("Connection is closed")

        try:
            # First byte: FIN + opcode
            header = bytearray()
            header.append(0x80 | opcode)  # FIN flag set

            # Payload length (unmasked from server → client)
            length = len(payload)
            if length < 126:
                header.append(length)
            elif length < 65536:
                header.append(126)
                header.extend(struct.pack("!H", length))
            else:
                header.append(127)
                header.extend(struct.pack("!Q", length))

            self._writer.write(bytes(header) + payload)
            await self._writer.drain()

        except (ConnectionError, OSError):
            self.state = ConnectionState.DISCONNECTED
            raise ConnectionError("Connection lost") from None

    async def _read_line(self) -> bytes:
        """Read a single CRLF-terminated line."""
        line = await self._reader.readline()
        return line.strip()

    async def _read_headers(self) -> dict[str, str]:
        """Read HTTP headers until blank line.

        Returns:
            A dict of header name → value (lowercased names).
        """
        headers: dict[str, str] = {}
        while True:
            line = await self._read_line()
            if not line:
                break
            if ":" in line.decode(errors="replace"):
                key, _, value = line.decode(errors="replace").partition(":")
                headers[key.strip().lower()] = value.strip()
        return headers

    @property
    def remote_address(self) -> str:
        """Return the remote peer address."""
        try:
            addr = self._writer.get_extra_info("peername")
            return f"{addr[0]}:{addr[1]}" if addr else "unknown"
        except Exception:
            return "unknown"

    def close(self) -> None:
        """Forcefully close the connection."""
        self.state = ConnectionState.DISCONNECTED
        try:
            self._writer.close()
        except Exception:
            pass


# ---------------------------------------------------------------------------
# WebSocket handler (server-side integration)
# ---------------------------------------------------------------------------


class WebSocketHandler:
    """Accepts WebSocket connections, authenticates, and routes messages.

    This handler is designed to be used by :class:`CadServer` which
    provides the underlying TCP listener.

    Args:
        on_rpc_request: Async callback ``(RpcRequest) -> RpcResponse``.
        on_client_connected: Optional callback ``(WebSocketConnection)``.
        on_client_disconnected: Optional callback ``(WebSocketConnection)``.
    """

    def __init__(
        self,
        on_rpc_request: Callable[[RpcRequest], RpcResponse] | None = None,
        on_client_connected: Callable[[WebSocketConnection], None] | None = None,
        on_client_disconnected: Callable[[WebSocketConnection], None] | None = None,
    ) -> None:
        self._on_rpc_request = on_rpc_request
        self._on_client_connected = on_client_connected
        self._on_client_disconnected = on_client_disconnected
        self._connections: list[WebSocketConnection] = []
        self._heartbeat_task: asyncio.Task | None = None

    async def handle_connection(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
    ) -> None:
        """Handle an incoming TCP connection — attempt WebSocket upgrade.

        Args:
            reader: Stream reader.
            writer: Stream writer.
        """
        conn = WebSocketConnection(
            reader=reader,
            writer=writer,
            on_message=self._on_message_received,
            on_close=self._on_connection_closed,
        )

        # Perform the HTTP → WebSocket upgrade
        success = await conn.perform_handshake()
        if not success:
            writer.close()
            return

        self._connections.append(conn)

        if self._on_client_connected:
            self._on_client_connected(conn)

        # Start the heartbeat if this is the first connection
        if self._heartbeat_task is None:
            self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())

        # Read messages until disconnect
        await conn.read_messages()

    def broadcast_event(self, event: ServerEvent) -> None:
        """Send a :class:`ServerEvent` to all connected clients.

        Args:
            event: The event to broadcast.
        """
        payload = encode_event(event)
        for conn in self._connections[:]:
            if conn.state == ConnectionState.CONNECTED:
                try:
                    # Schedule the send in the event loop
                    asyncio.create_task(conn.send_text(payload))
                except Exception:
                    pass

    def disconnect_all(self) -> None:
        """Close all connections gracefully."""
        for conn in self._connections[:]:
            try:
                asyncio.create_task(conn.send_close(1001, "Server shutting down"))
            except Exception:
                conn.close()
        self._connections.clear()

    @property
    def connection_count(self) -> int:
        """Return the number of active connections."""
        return len(self._connections)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _on_message_received(self, conn: WebSocketConnection, text: str) -> None:
        """Handle an incoming WebSocket text message.

        Parses the JSON-RPC 2.0 request, dispatches it, and sends the
        response back over the same connection.
        """
        if self._on_rpc_request is None:
            return

        # Parse the RPC request
        try:
            request = decode_request(text)
        except (json.JSONDecodeError, ValueError) as exc:
            response = make_error_response(None, PARSE_ERROR, str(exc))
            asyncio.create_task(conn.send_text(encode_response(response)))
            return

        # The request may be a notification (no id) — skip response
        is_notification = request.id is None

        # Dispatch
        try:
            # We need to run the async handler synchronously here since
            # on_message is called from the read_messages loop.
            # Instead, we schedule the handler as a task.
            fut = asyncio.ensure_future(self._dispatch_rpc(request))
            fut.add_done_callback(
                lambda f: self._send_response(conn, f, is_notification)
            )
        except Exception as exc:
            response = make_error_response(request.id, INTERNAL_ERROR, str(exc))
            if not is_notification:
                asyncio.create_task(conn.send_text(encode_response(response)))

    async def _dispatch_rpc(self, request: RpcRequest) -> RpcResponse:
        """Dispatch an RPC request and return the response."""
        if self._on_rpc_request is None:
            return make_error_response(request.id, INTERNAL_ERROR, "No handler registered")
        return await self._on_rpc_request(request)

    def _send_response(
        self,
        conn: WebSocketConnection,
        future: asyncio.Future,
        is_notification: bool,
    ) -> None:
        """Send the RPC response back to the client."""
        if is_notification:
            return
        try:
            response = future.result()
        except Exception as exc:
            response = make_error_response(None, INTERNAL_ERROR, str(exc))
        try:
            asyncio.create_task(conn.send_text(encode_response(response)))
        except Exception:
            pass

    def _on_connection_closed(self, conn: WebSocketConnection) -> None:
        """Remove a closed connection from the list."""
        if conn in self._connections:
            self._connections.remove(conn)
        if self._on_client_disconnected:
            self._on_client_disconnected(conn)

    async def _heartbeat_loop(self) -> None:
        """Periodically send pings to all connected clients."""
        while True:
            await asyncio.sleep(_HEARTBEAT_INTERVAL)
            active = [
                c for c in self._connections
                if c.state == ConnectionState.CONNECTED
            ]
            if not active:
                # No active connections — stop the heartbeat
                break
            for conn in active:
                try:
                    await conn.send_ping()
                except Exception:
                    pass
        self._heartbeat_task = None
