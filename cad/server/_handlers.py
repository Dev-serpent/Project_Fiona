"""Request handler — maps JSON-RPC 2.0 methods to domain logic.

Every public method whose name starts with ``handle_`` corresponds to
an RPC method group (``document.*``, ``command.*``, ``export.*``,
``server.*``).
"""

from __future__ import annotations

import time
from typing import Any

from cad.commands.registry import CommandRegistry
from cad.server._command_executor import CommandExecutor
from cad.server._document_manager import DocumentManager
from cad.server._export_manager import ExportManager
from cad.server._protocol import (
    RpcRequest,
    RpcResponse,
    ServerEvent,
    encode_event,
    make_error_response,
    make_event,
    make_success_response,
    COMMAND_FAILED,
    COMMAND_NOT_FOUND,
    DOCUMENT_NOT_OPEN,
    EXPORT_FAILED,
    INTERNAL_ERROR,
    INVALID_PARAMS,
    METHOD_NOT_FOUND,
    NOTHING_TO_REDO,
    NOTHING_TO_UNDO,
)


class RequestHandler:
    """Routes JSON-RPC 2.0 requests to the appropriate handler method.

    Args:
        doc_manager: The document manager instance.
        cmd_executor: The command executor instance.
        export_manager: The export manager instance.
        registry: The command registry (for listing commands).
    """

    def __init__(
        self,
        doc_manager: DocumentManager,
        cmd_executor: CommandExecutor,
        export_manager: ExportManager,
        registry: CommandRegistry | None = None,
        ws_handler: Any | None = None,
    ) -> None:
        self._doc_manager = doc_manager
        self._cmd_executor = cmd_executor
        self._export_manager = export_manager
        self._registry = registry
        self._ws_handler = ws_handler
        self._plan_event_listeners: list = []
        # Metadata for capabilities
        self._start_time = time.time()
        self._capabilities = {
            "jsonrpc": "2.0",
            "version": "0.1.0",
            "server_name": "ficad",
            "protocol_version": "1.0",
            "methods": {
                "document": ["list", "create", "open", "save", "close", "get_state"],
                "command": ["execute", "undo", "redo", "can_undo", "can_redo", "list"],
                "export": ["formats", "run"],
                "server": ["health", "capabilities", "ping"],
                "system": ["handshake"],
            },
            "features": [
                "undo_redo",
                "snapshot_based_undo",
                "export_stl",
                "export_obj",
                "export_svg",
            ],
        }

        self._setup_approval_listener()

    # ------------------------------------------------------------------
    # Public dispatch
    # ------------------------------------------------------------------

    async def handle(self, request: RpcRequest) -> RpcResponse:
        """Route a request to the appropriate handler method.

        Args:
            request: The parsed JSON-RPC 2.0 request.

        Returns:
            A response (success or error).
        """
        method = request.method
        params = request.params or {}
        rid = request.id

        try:
            # Normalise params to dict
            params_dict: dict[str, Any] = {}
            if isinstance(params, dict):
                params_dict = params
            elif isinstance(params, list):
                # Positional params — convert to dict by index
                for i, val in enumerate(params):
                    params_dict[str(i)] = val

            # Dispatch by method group
            if method == "handshake":
                result = await self.handle_handshake(params_dict)
            elif method.startswith("document."):
                result = await self._dispatch_document(method, params_dict)
            elif method.startswith("command."):
                result = await self._dispatch_command(method, params_dict)
            elif method.startswith("export."):
                result = await self._dispatch_export(method, params_dict)
            elif method.startswith("server."):
                result = await self._dispatch_server(method, params_dict)
            elif method.startswith("approval."):
                result = await self._dispatch_approval(method, params_dict)
            else:
                return make_error_response(
                    rid, METHOD_NOT_FOUND,
                    f"Method not found: {method!r}",
                )

            return make_success_response(rid, result)

        except KeyError as exc:
            return make_error_response(rid, INVALID_PARAMS, str(exc))
        except Exception as exc:
            return make_error_response(rid, INTERNAL_ERROR, str(exc))

    # ------------------------------------------------------------------
    # Document methods
    # ------------------------------------------------------------------

    async def handle_document_list(self, params: dict[str, Any]) -> list[dict[str, Any]]:
        """List all open documents."""
        handles = self._doc_manager.list_documents()
        return [_handle_to_dict(h) for h in handles]

    async def handle_document_create(self, params: dict[str, Any]) -> dict[str, Any]:
        """Create a new document.

        Params:
            name: Optional document name (default ``"Untitled"``).
        """
        name = params.get("name", "Untitled")
        handle = self._doc_manager.create_document(name=name)
        return _handle_to_dict(handle)

    async def handle_document_open(self, params: dict[str, Any]) -> dict[str, Any]:
        """Open a document from a file.

        Params:
            path: Filesystem path to the ``.cad`` file.
        """
        path = params.get("path", "")
        if not path:
            raise KeyError("Missing required parameter: 'path'")
        handle = self._doc_manager.open_document(path)
        return _handle_to_dict(handle)

    async def handle_document_save(self, params: dict[str, Any]) -> dict[str, Any]:
        """Save a document.

        Params:
            doc_id: Document UUID.
            path: Optional output path (uses current path if omitted).
        """
        doc_id = params.get("doc_id", "")
        if not doc_id:
            raise KeyError("Missing required parameter: 'doc_id'")
        path = params.get("path")
        saved_path = self._doc_manager.save_document(doc_id, path)
        return {"path": saved_path}

    async def handle_document_close(self, params: dict[str, Any]) -> dict[str, Any]:
        """Close a document.

        Params:
            doc_id: Document UUID.
        """
        doc_id = params.get("doc_id", "")
        if not doc_id:
            raise KeyError("Missing required parameter: 'doc_id'")
        self._doc_manager.close_document(doc_id)
        return {"closed": True}

    async def handle_document_get_state(self, params: dict[str, Any]) -> dict[str, Any]:
        """Return the full document state as a serialised dict.

        Params:
            doc_id: Document UUID.
        """
        doc_id = params.get("doc_id", "")
        if not doc_id:
            raise KeyError("Missing required parameter: 'doc_id'")
        doc = self._doc_manager.get_document(doc_id)
        if doc is None:
            return {"error": "Document not open", "doc_id": doc_id}
        return doc.to_dict()

    # ------------------------------------------------------------------
    # Command methods
    # ------------------------------------------------------------------

    async def handle_command_execute(self, params: dict[str, Any]) -> dict[str, Any]:
        """Execute a named command on a document.

        Params:
            doc_id: Document UUID.
            name: Command name (e.g. ``'create_box'``).
            params: Command-specific keyword arguments (optional).
        """
        doc_id = params.get("doc_id", "")
        command_name = params.get("name", "")
        if not doc_id:
            raise KeyError("Missing required parameter: 'doc_id'")
        if not command_name:
            raise KeyError("Missing required parameter: 'name'")
        cmd_params = params.get("params", {})
        if not isinstance(cmd_params, dict):
            cmd_params = {}

        try:
            result = self._cmd_executor.execute(doc_id, command_name, **cmd_params)
        except Exception as exc:
            error_code = _classify_command_error(exc)
            raise _command_error_as_exception(error_code, str(exc)) from exc

        # Broadcast changes to all connected clients
        self._broadcast_document_updated(
            doc_id=doc_id,
            snapshot=getattr(result, "document_snapshot", None),
            created=getattr(result, "created_objects", None),
            modified=getattr(result, "modified_objects", None),
            deleted=getattr(result, "deleted_objects", None),
        )

        return _command_result_to_dict(result)

    async def handle_command_undo(self, params: dict[str, Any]) -> dict[str, Any]:
        """Undo the last command on a document.

        Params:
            doc_id: Document UUID.
        """
        doc_id = params.get("doc_id", "")
        if not doc_id:
            raise KeyError("Missing required parameter: 'doc_id'")
        try:
            snapshot = self._cmd_executor.undo(doc_id)
        except Exception as exc:
            raise _command_error_as_exception(NOTHING_TO_UNDO, str(exc)) from exc

        # Broadcast the new full state after undo
        self._broadcast_document_updated(doc_id=doc_id, snapshot=snapshot)

        return {"document_snapshot": snapshot}

    async def handle_command_redo(self, params: dict[str, Any]) -> dict[str, Any]:
        """Redo the last undone command on a document.

        Params:
            doc_id: Document UUID.
        """
        doc_id = params.get("doc_id", "")
        if not doc_id:
            raise KeyError("Missing required parameter: 'doc_id'")
        try:
            snapshot = self._cmd_executor.redo(doc_id)
        except Exception as exc:
            raise _command_error_as_exception(NOTHING_TO_REDO, str(exc)) from exc

        # Broadcast the new full state after redo
        self._broadcast_document_updated(doc_id=doc_id, snapshot=snapshot)

        return {"document_snapshot": snapshot}

    async def handle_command_can_undo(self, params: dict[str, Any]) -> dict[str, Any]:
        """Check if undo is available.

        Params:
            doc_id: Document UUID.
        """
        doc_id = params.get("doc_id", "")
        if not doc_id:
            raise KeyError("Missing required parameter: 'doc_id'")
        can_undo = self._cmd_executor.can_undo(doc_id)
        return {"can_undo": can_undo}

    async def handle_command_can_redo(self, params: dict[str, Any]) -> dict[str, Any]:
        """Check if redo is available.

        Params:
            doc_id: Document UUID.
        """
        doc_id = params.get("doc_id", "")
        if not doc_id:
            raise KeyError("Missing required parameter: 'doc_id'")
        can_redo = self._cmd_executor.can_redo(doc_id)
        return {"can_redo": can_redo}

    async def handle_command_list(self, params: dict[str, Any]) -> list[dict[str, Any]]:
        """List available commands from the registry."""
        if self._registry is None:
            return []
        return [
            {
                "name": cmd.name,
                "description": cmd.description,
                "aliases": cmd.aliases,
            }
            for cmd in self._registry.commands.values()
        ]

    # ------------------------------------------------------------------
    # Export methods
    # ------------------------------------------------------------------

    async def handle_export_formats(self, params: dict[str, Any]) -> list[dict[str, Any]]:
        """List available export formats."""
        return self._export_manager.list_formats()

    async def handle_export_run(self, params: dict[str, Any]) -> dict[str, Any]:
        """Export a document to a file.

        Params:
            doc_id: Document UUID.
            format: Export format (e.g. ``'stl'``).
            path: Output file path.
            options: Format-specific options (optional).
        """
        doc_id = params.get("doc_id", "")
        fmt = params.get("format", "")
        path = params.get("path", "")
        options = params.get("options", {})
        if not isinstance(options, dict):
            options = {}

        if not doc_id:
            raise KeyError("Missing required parameter: 'doc_id'")
        if not fmt:
            raise KeyError("Missing required parameter: 'format'")
        if not path:
            raise KeyError("Missing required parameter: 'path'")

        doc = self._doc_manager.get_document(doc_id)
        if doc is None:
            raise KeyError(f"Document not open: {doc_id}")

        try:
            result = self._export_manager.export(fmt, doc, path, **options)
        except Exception as exc:
            raise Exception(f"Export failed: {exc}") from exc

        return {
            "path": result.path,
            "format": result.format,
            "size_bytes": result.size_bytes,
            "duration_ms": result.duration_ms,
            "warnings": result.warnings,
        }

    # ------------------------------------------------------------------
    # Server methods
    # ------------------------------------------------------------------

    async def handle_server_health(self, params: dict[str, Any]) -> dict[str, Any]:
        """Return server health status."""
        docs = self._doc_manager.list_documents()
        return {
            "status": "ok",
            "uptime_seconds": time.time() - self._start_time,
            "open_documents": len(docs),
            "active_document": _handle_to_dict(docs[0]) if docs else None,
        }

    async def handle_server_capabilities(self, params: dict[str, Any]) -> dict[str, Any]:
        """Return server capabilities."""
        return dict(self._capabilities)

    async def handle_server_ping(self, params: dict[str, Any]) -> dict[str, Any]:
        """Ping the server."""
        return {"pong": True, "timestamp": time.time()}

    async def handle_handshake(self, params: dict[str, Any]) -> dict[str, Any]:
        """Perform a version-negotiation handshake.

        The client sends its protocol version and receives the server
        version and capabilities in return.
        """
        client_version = params.get("version", "unknown")
        return {
            "accepted": True,
            "server_version": self._capabilities["protocol_version"],
            "client_version": client_version,
            "server_name": self._capabilities["server_name"],
            "capabilities": self._capabilities,
        }

    # ------------------------------------------------------------------
    # Internal dispatch
    # ------------------------------------------------------------------

    async def _dispatch_document(
        self, method: str, params: dict[str, Any]
    ) -> Any:
        mapping = {
            "document.list": self.handle_document_list,
            "document.create": self.handle_document_create,
            "document.open": self.handle_document_open,
            "document.save": self.handle_document_save,
            "document.close": self.handle_document_close,
            "document.get_state": self.handle_document_get_state,
        }
        handler = mapping.get(method)
        if handler is None:
            raise KeyError(f"Unknown document method: {method}")
        return await handler(params)

    async def _dispatch_command(
        self, method: str, params: dict[str, Any]
    ) -> Any:
        mapping = {
            "command.execute": self.handle_command_execute,
            "command.undo": self.handle_command_undo,
            "command.redo": self.handle_command_redo,
            "command.can_undo": self.handle_command_can_undo,
            "command.can_redo": self.handle_command_can_redo,
            "command.list": self.handle_command_list,
        }
        handler = mapping.get(method)
        if handler is None:
            raise KeyError(f"Unknown command method: {method}")
        return await handler(params)

    async def _dispatch_export(
        self, method: str, params: dict[str, Any]
    ) -> Any:
        mapping = {
            "export.formats": self.handle_export_formats,
            "export.run": self.handle_export_run,
        }
        handler = mapping.get(method)
        if handler is None:
            raise KeyError(f"Unknown export method: {method}")
        return await handler(params)

    async def _dispatch_server(
        self, method: str, params: dict[str, Any]
    ) -> Any:
        # Strip "server." prefix
        sub = method[len("server."):]
        mapping = {
            "health": self.handle_server_health,
            "capabilities": self.handle_server_capabilities,
            "ping": self.handle_server_ping,
        }
        handler = mapping.get(sub)
        if handler is None:
            raise KeyError(f"Unknown server method: {method}")
        return await handler(params)

    # ------------------------------------------------------------------
    # Approval methods
    # ------------------------------------------------------------------

    async def _dispatch_approval(
        self, method: str, params: dict[str, Any]
    ) -> Any:
        handler_name = f"handle_{method.replace('.', '_')}"
        handler = getattr(self, handler_name, None)
        if handler is None:
            raise KeyError(f"Unknown approval method: {method}")
        return await handler(params)

    async def handle_approval_list(self, params):
        """List all plans (for history view)."""
        from FionaCore.approval import get_approval_manager
        manager = get_approval_manager()
        return {"plans": manager.get_all_plans()}

    async def handle_approval_pending(self, params):
        """List plans awaiting human decision."""
        from FionaCore.approval import get_approval_manager
        manager = get_approval_manager()
        return {"plans": manager.get_pending_plans()}

    async def handle_approval_approve(self, params):
        """Approve a pending plan."""
        plan_id = params.get("plan_id", "")
        from FionaCore.approval import get_approval_manager
        manager = get_approval_manager()
        success = manager.approve_plan(plan_id)
        if success:
            self._broadcast_event("plan_approved", {"plan_id": plan_id})
            return {"ok": True}
        return {"ok": False, "error": "Plan not found or not pending"}

    async def handle_approval_deny(self, params):
        """Deny a pending plan."""
        plan_id = params.get("plan_id", "")
        reason = params.get("reason", "")
        from FionaCore.approval import get_approval_manager
        manager = get_approval_manager()
        success = manager.deny_plan(plan_id, reason)
        if success:
            self._broadcast_event("plan_denied", {"plan_id": plan_id, "reason": reason})
            return {"ok": True}
        return {"ok": False, "error": "Plan not found or not pending"}

    async def handle_approval_thinking(self, params):
        """Stream agent thinking to all connected clients.

        The agent calls this periodically to broadcast its current
        thought process during plan generation or execution.
        """
        thought = params.get("thought") or params.get("message", "")
        if not thought:
            return {"ok": False, "error": "No thought provided"}
        self._broadcast_event("agent_thinking", {"thought": thought})
        return {"ok": True}

    def _setup_approval_listener(self) -> None:
        """Listen for plan changes and broadcast to all connected clients."""
        from FionaCore.approval import get_approval_manager
        manager = get_approval_manager()

        def on_plan_change(plan_id: str) -> None:
            plan = manager.get_plan(plan_id)
            if plan:
                self._broadcast_event("plan_updated", plan)

        manager.on_change(on_plan_change)

    def _broadcast_event(self, event_type: str, data: dict) -> None:
        """Broadcast event to all connected WebSocket clients."""
        event = make_event(event_type, data)
        if self._ws_handler is not None:
            self._ws_handler.broadcast_event(event)

    def _broadcast_document_updated(
        self,
        doc_id: str,
        snapshot: dict | None = None,
        created: list | None = None,
        modified: list | None = None,
        deleted: list | None = None,
    ) -> None:
        """Broadcast a document update to all connected clients.

        Sends an incremental change-set when individual object lists are
        available, falling back to the full snapshot otherwise.
        """
        payload: dict[str, Any] = {"doc_id": doc_id}

        if created is not None and modified is not None and deleted is not None:
            # Incremental changes — send only the diffs
            payload["changes"] = {
                "created": created,
                "modified": modified,
                "deleted": deleted,
            }
        elif snapshot is not None:
            # Full state snapshot
            payload["document"] = snapshot

        self._broadcast_event("document_updated", payload)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _handle_to_dict(handle: Any) -> dict[str, Any]:
    """Convert a DocumentHandle (or any data object) to a plain dict."""
    if hasattr(handle, "__dataclass_fields__"):
        return {
            field.name: getattr(handle, field.name)
            for field in handle.__dataclass_fields__.values()  # type: ignore[union-attr]
        }
    if isinstance(handle, dict):
        return handle
    return dict(handle)


def _command_result_to_dict(result: Any) -> dict[str, Any]:
    """Convert a CommandResult to a plain dict."""
    if hasattr(result, "__dataclass_fields__"):
        return {
            field.name: getattr(result, field.name)
            for field in result.__dataclass_fields__.values()  # type: ignore[union-attr]
        }
    if isinstance(result, dict):
        return result
    return {"success": bool(result), "message": str(result)}


def _classify_command_error(exc: Exception) -> int:
    """Map exception types to JSON-RPC error codes."""
    from fiona.interfaces import (
        CommandNotFound,
        DocumentNotOpen,
        InvalidArguments,
        NothingToRedo,
        NothingToUndo,
    )

    if isinstance(exc, DocumentNotOpen):
        return DOCUMENT_NOT_OPEN
    if isinstance(exc, CommandNotFound):
        return COMMAND_NOT_FOUND
    if isinstance(exc, InvalidArguments):
        return COMMAND_FAILED
    if isinstance(exc, NothingToUndo):
        return NOTHING_TO_UNDO
    if isinstance(exc, NothingToRedo):
        return NOTHING_TO_REDO
    return COMMAND_FAILED


def _command_error_as_exception(code: int, message: str) -> Exception:
    """Wrap a JSON-RPC error code as a Python exception for propagation."""
    return Exception(f"[{code}] {message}")
