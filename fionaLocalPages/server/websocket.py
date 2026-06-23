"""WebSocket connection manager for the Fiona API server.

Provides broadcast and directed-message capabilities with
automatic cleanup of disconnected peers.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Any, Callable, Coroutine

from aiohttp import web

logger = logging.getLogger(__name__)

# Type alias for a WS message handler
WSHandler = Callable[[dict[str, Any]], Coroutine[Any, Any, None]]


class WebSocketManager:
    """Manages a pool of WebSocket connections.

    Supports:
      - Broadcast to all connected peers.
      - Send to a specific peer.
      - JSON-RPC style notifications (event, params).
      - Periodic heartbeat to detect stale connections.
      - Graceful cleanup on disconnect.
    """

    def __init__(self, heartbeat_interval: float = 30.0) -> None:
        self._peers: dict[int, web.WebSocketResponse] = {}
        self._peer_id_counter: int = 0
        self._heartbeat_interval = heartbeat_interval
        self._handlers: dict[str, WSHandler] = {}
        self._background_tasks: list[asyncio.Task[None]] = []

    # ------------------------------------------------------------------
    # Registration / lifecycle
    # ------------------------------------------------------------------

    async def register(
        self, ws: web.WebSocketResponse, handlers: dict[str, WSHandler] | None = None
    ) -> int:
        """Register a new WebSocket peer.

        Returns a unique peer ID.
        """
        self._peer_id_counter += 1
        peer_id = self._peer_id_counter
        self._peers[peer_id] = ws

        if handlers:
            self._handlers.update(handlers)

        logger.info("WS peer %d connected (%d total)", peer_id, len(self._peers))
        return peer_id

    async def unregister(self, peer_id: int) -> None:
        """Remove a peer from the pool."""
        self._peers.pop(peer_id, None)
        logger.info("WS peer %d disconnected (%d remaining)", peer_id, len(self._peers))

    def peer_count(self) -> int:
        return len(self._peers)

    # ------------------------------------------------------------------
    # Send helpers
    # ------------------------------------------------------------------

    async def send_json(
        self, peer_id: int, data: dict[str, Any]
    ) -> bool:
        """Send a JSON message to a specific peer.

        Returns True if the message was sent, False if the peer is gone.
        """
        ws = self._peers.get(peer_id)
        if ws is None or ws.closed:
            return False
        try:
            await ws.send_json(data)
            return True
        except ConnectionResetError:
            await self.unregister(peer_id)
            return False
        except Exception:
            logger.exception("Error sending WS message to peer %d", peer_id)
            return False

    async def broadcast(self, data: dict[str, Any]) -> int:
        """Send a JSON message to all connected peers.

        Returns the number of successful sends.
        """
        sent = 0
        dead: list[int] = []
        for peer_id, ws in list(self._peers.items()):
            if ws.closed:
                dead.append(peer_id)
                continue
            try:
                await ws.send_json(data)
                sent += 1
            except ConnectionResetError:
                dead.append(peer_id)
            except Exception:
                logger.exception("Error broadcasting to peer %d", peer_id)
                dead.append(peer_id)

        for peer_id in dead:
            await self.unregister(peer_id)
        return sent

    async def notify(self, event: str, params: dict[str, Any] | None = None) -> int:
        """Broadcast a JSON-RPC style notification.

        The payload will be ``{"event": event, "params": params}``.
        """
        return await self.broadcast({"event": event, "params": params or {}})

    # ------------------------------------------------------------------
    # Message handler dispatch
    # ------------------------------------------------------------------

    async def handle_message(
        self, peer_id: int, raw: str | bytes
    ) -> None:
        """Parse an incoming WS message and dispatch it to a registered handler.

        Expects a JSON object with a ``method`` field, and optionally
        ``params`` and ``id`` fields (JSON-RPC 2.0 style).
        """
        try:
            data = json.loads(raw) if isinstance(raw, (str, bytes)) else raw
        except json.JSONDecodeError:
            await self.send_json(peer_id, {
                "jsonrpc": "2.0",
                "error": {"code": -32700, "message": "Parse error"},
                "id": None,
            })
            return

        if not isinstance(data, dict):
            await self.send_json(peer_id, {
                "jsonrpc": "2.0",
                "error": {"code": -32600, "message": "Invalid Request: not an object"},
                "id": None,
            })
            return

        method = data.get("method", "")
        params = data.get("params", {})
        msg_id = data.get("id")

        handler = self._handlers.get(method)
        if handler is None:
            if msg_id is not None:
                await self.send_json(peer_id, {
                    "jsonrpc": "2.0",
                    "error": {"code": -32601, "message": f"Method not found: {method}"},
                    "id": msg_id,
                })
            return

        try:
            result = await handler(params)
            if msg_id is not None:
                await self.send_json(peer_id, {
                    "jsonrpc": "2.0",
                    "result": result,
                    "id": msg_id,
                })
        except Exception as exc:
            logger.exception("WS handler error for %s", method)
            if msg_id is not None:
                await self.send_json(peer_id, {
                    "jsonrpc": "2.0",
                    "error": {"code": -32000, "message": str(exc)},
                    "id": msg_id,
                })

    # ------------------------------------------------------------------
    # Periodic push tasks
    # ------------------------------------------------------------------

    async def start_periodic_push(
        self,
        interval: float,
        factory: Callable[[], Awaitable[dict[str, Any]]],
        event_name: str,
    ) -> asyncio.Task[None]:
        """Start a background task that pushes data to all peers on an interval.

        The *factory* coroutine is called each tick. Its return value is
        broadcast as ``{"event": event_name, "params": data}``.
        """
        async def _pusher() -> None:
            while True:
                try:
                    await asyncio.sleep(interval)
                    if self.peer_count() == 0:
                        continue
                    data = await factory()
                    await self.notify(event_name, data)
                except asyncio.CancelledError:
                    break
                except Exception:
                    logger.exception("Periodic push error for %s", event_name)

        task = asyncio.create_task(_pusher())
        self._background_tasks.append(task)
        return task

    async def stop_periodic_pushes(self) -> None:
        """Cancel all background push tasks."""
        for task in self._background_tasks:
            task.cancel()
        if self._background_tasks:
            await asyncio.gather(*self._background_tasks, return_exceptions=True)
        self._background_tasks.clear()
