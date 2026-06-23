"""JSON-RPC 2.0 message types and codec for the CAD server.

Implements the JSON-RPC 2.0 specification (https://www.jsonrpc.org/specification)
with custom error codes for CAD-domain errors.
"""

from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass, field
from typing import Any


# ---------------------------------------------------------------------------
# JSON-RPC 2.0 Data Types
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RpcRequest:
    """A JSON-RPC 2.0 request object.

    Attributes:
        jsonrpc: Version string — always ``"2.0"``.
        id: Request identifier.  *None* for notifications.
        method: Name of the method to invoke.
        params: Parameters for the method (dict or list).
    """

    jsonrpc: str = "2.0"
    id: int | str | None = None
    method: str = ""
    params: dict[str, Any] | list[Any] | None = None


@dataclass(frozen=True)
class RpcError:
    """A JSON-RPC 2.0 error object.

    Attributes:
        code: Integer error code matching the spec or CAD extension range.
        message: Short human-readable summary.
        data: Additional error context (optional).
    """

    code: int
    message: str
    data: Any = None


@dataclass(frozen=True)
class RpcResponse:
    """A JSON-RPC 2.0 response object.

    Attributes:
        jsonrpc: Version string — always ``"2.0"``.
        id: Matches the request id, or *None* for batch responses.
        result: Successful result (mutually exclusive with *error*).
        error: Error object (mutually exclusive with *result*).
    """

    jsonrpc: str = "2.0"
    id: int | str | None = None
    result: Any = None
    error: RpcError | None = None


@dataclass(frozen=True)
class RpcNotification:
    """A JSON-RPC 2.0 notification (a request without an ``id``).

    Attributes:
        jsonrpc: Version string — always ``"2.0"``.
        method: Name of the method being notified about.
        params: Notification payload.
    """

    jsonrpc: str = "2.0"
    method: str = ""
    params: dict[str, Any] | None = None


@dataclass(frozen=True)
class ServerEvent:
    """A server-initiated event sent to connected clients.

    Attributes:
        type: Event type identifier (e.g. ``"document.modified"``).
        data: Event-specific payload.
        timestamp: Unix timestamp (seconds since epoch).
    """

    type: str = ""
    data: dict[str, Any] = field(default_factory=dict)
    timestamp: float = 0.0


# ---------------------------------------------------------------------------
# JSON-RPC 2.0 Error Codes
# ---------------------------------------------------------------------------

# Standard JSON-RPC errors (from the spec)
PARSE_ERROR = -32700
INVALID_REQUEST = -32600
METHOD_NOT_FOUND = -32601
INVALID_PARAMS = -32602
INTERNAL_ERROR = -32603

# CAD-domain error codes (extension range)
DOCUMENT_NOT_OPEN = -32000
COMMAND_NOT_FOUND = -32001
COMMAND_FAILED = -32002
NOTHING_TO_UNDO = -32003
NOTHING_TO_REDO = -32004
EXPORT_FAILED = -32005
VERSION_CONFLICT = -32008

_ERROR_MESSAGES: dict[int, str] = {
    PARSE_ERROR: "Parse error",
    INVALID_REQUEST: "Invalid Request",
    METHOD_NOT_FOUND: "Method not found",
    INVALID_PARAMS: "Invalid params",
    INTERNAL_ERROR: "Internal error",
    DOCUMENT_NOT_OPEN: "Document not open",
    COMMAND_NOT_FOUND: "Command not found",
    COMMAND_FAILED: "Command failed",
    NOTHING_TO_UNDO: "Nothing to undo",
    NOTHING_TO_REDO: "Nothing to redo",
    EXPORT_FAILED: "Export failed",
    VERSION_CONFLICT: "Version conflict",
}


def _default_error_message(code: int) -> str:
    """Return the standard message for an error code, or a generic fallback."""
    return _ERROR_MESSAGES.get(code, "Server error")


# ---------------------------------------------------------------------------
# Codec helpers
# ---------------------------------------------------------------------------


def decode_request(raw: str) -> RpcRequest:
    """Deserialize a JSON-RPC 2.0 request from a JSON string.

    Args:
        raw: The raw JSON string received from the client.

    Returns:
        An :class:`RpcRequest` instance.

    Raises:
        json.JSONDecodeError: The payload is not valid JSON.
        ValueError: The payload is not a valid JSON-RPC 2.0 request.
    """
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise ValueError("Request must be a JSON object")

    jsonrpc = data.get("jsonrpc", "")
    if jsonrpc != "2.0":
        raise ValueError(f"Unsupported JSON-RPC version: {jsonrpc!r}")

    method = data.get("method", "")
    if not isinstance(method, str) or not method:
        raise ValueError("Missing or invalid 'method' field")

    rid = data.get("id")
    params = data.get("params")

    return RpcRequest(jsonrpc=jsonrpc, id=rid, method=method, params=params)


def encode_response(response: RpcResponse) -> str:
    """Serialize a JSON-RPC 2.0 response to a JSON string.

    Args:
        response: The response to serialize.

    Returns:
        A JSON string ready to send over the wire.
    """
    obj: dict[str, Any] = {"jsonrpc": response.jsonrpc}
    if response.id is not None:
        obj["id"] = response.id
    if response.error is not None:
        obj["error"] = {
            "code": response.error.code,
            "message": response.error.message,
        }
        if response.error.data is not None:
            obj["error"]["data"] = response.error.data
    else:
        obj["result"] = response.result
    return json.dumps(obj, default=str)


def encode_event(event: ServerEvent) -> str:
    """Serialize a :class:`ServerEvent` to a JSON string.

    The event is wrapped in a JSON-RPC 2.0 notification-like envelope
    so the client can process it through the same message pipeline.

    Args:
        event: The event to serialize.

    Returns:
        A JSON string.
    """
    obj: dict[str, Any] = {
        "jsonrpc": "2.0",
        "method": "server.event",
        "params": {
            "type": event.type,
            "data": event.data,
            "timestamp": event.timestamp,
        },
    }
    return json.dumps(obj, default=str)


def make_error_response(
    request_id: int | str | None,
    code: int,
    message: str | None = None,
    data: Any = None,
) -> RpcResponse:
    """Build a JSON-RPC 2.0 error response.

    Args:
        request_id: The id from the original request (may be *None*).
        code: Numeric error code.
        message: Override the default error message.
        data: Optional extended error data.

    Returns:
        An :class:`RpcResponse` with the error field set.
    """
    return RpcResponse(
        id=request_id,
        error=RpcError(
            code=code,
            message=message or _default_error_message(code),
            data=data,
        ),
    )


def make_success_response(request_id: int | str | None, result: Any) -> RpcResponse:
    """Build a JSON-RPC 2.0 success response.

    Args:
        request_id: The id from the original request.
        result: The result payload.

    Returns:
        An :class:`RpcResponse` with the result field set.
    """
    return RpcResponse(id=request_id, result=result)


def make_event(event_type: str, data: dict[str, Any] | None = None) -> ServerEvent:
    """Build a :class:`ServerEvent` with the current timestamp.

    Args:
        event_type: Event type string.
        data: Optional event payload.

    Returns:
        A :class:`ServerEvent` instance.
    """
    return ServerEvent(
        type=event_type,
        data=data or {},
        timestamp=time.time(),
    )
