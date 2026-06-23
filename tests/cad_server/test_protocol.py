"""Tests for the JSON-RPC 2.0 protocol codec."""

from __future__ import annotations

import json
import time

import pytest

from cad.server._protocol import (
    RpcError,
    RpcNotification,
    RpcRequest,
    RpcResponse,
    ServerEvent,
    decode_request,
    encode_event,
    encode_response,
    make_error_response,
    make_event,
    make_success_response,
    PARSE_ERROR,
    INVALID_REQUEST,
    METHOD_NOT_FOUND,
    INVALID_PARAMS,
    INTERNAL_ERROR,
    DOCUMENT_NOT_OPEN,
    COMMAND_NOT_FOUND,
    COMMAND_FAILED,
    NOTHING_TO_UNDO,
    NOTHING_TO_REDO,
    EXPORT_FAILED,
    VERSION_CONFLICT,
)


class TestRpcDataTypes:
    """Verify the RPC data type dataclasses."""

    def test_request_defaults(self) -> None:
        req = RpcRequest(method="test")
        assert req.jsonrpc == "2.0"
        assert req.id is None
        assert req.method == "test"
        assert req.params is None

    def test_request_full(self) -> None:
        req = RpcRequest(
            id=42, method="document.create", params={"name": "test"}
        )
        assert req.id == 42
        assert req.method == "document.create"
        assert req.params == {"name": "test"}

    def test_response_defaults(self) -> None:
        resp = RpcResponse()
        assert resp.jsonrpc == "2.0"
        assert resp.id is None
        assert resp.result is None
        assert resp.error is None

    def test_response_with_result(self) -> None:
        resp = RpcResponse(id=1, result={"ok": True})
        assert resp.id == 1
        assert resp.result == {"ok": True}
        assert resp.error is None

    def test_response_with_error(self) -> None:
        err = RpcError(code=-32000, message="Document not open")
        resp = RpcResponse(id=1, error=err)
        assert resp.error.code == -32000
        assert resp.error.message == "Document not open"

    def test_notification(self) -> None:
        notif = RpcNotification(method="server.event", params={"type": "test"})
        assert notif.jsonrpc == "2.0"
        assert notif.method == "server.event"
        assert notif.params == {"type": "test"}

    def test_server_event(self) -> None:
        event = ServerEvent(
            type="document.modified",
            data={"doc_id": "abc"},
            timestamp=12345.0,
        )
        assert event.type == "document.modified"
        assert event.data == {"doc_id": "abc"}
        assert event.timestamp == 12345.0


class TestErrorCodes:
    """Verify error code values match the JSON-RPC 2.0 spec."""

    def test_standard_codes(self) -> None:
        assert PARSE_ERROR == -32700
        assert INVALID_REQUEST == -32600
        assert METHOD_NOT_FOUND == -32601
        assert INVALID_PARAMS == -32602
        assert INTERNAL_ERROR == -32603

    def test_cad_codes(self) -> None:
        assert DOCUMENT_NOT_OPEN == -32000
        assert COMMAND_NOT_FOUND == -32001
        assert COMMAND_FAILED == -32002
        assert NOTHING_TO_UNDO == -32003
        assert NOTHING_TO_REDO == -32004
        assert EXPORT_FAILED == -32005
        assert VERSION_CONFLICT == -32008


class TestDecodeRequest:
    """Tests for ``decode_request()``."""

    def test_valid_request(self) -> None:
        raw = '{"jsonrpc":"2.0","id":1,"method":"document.list","params":{}}'
        req = decode_request(raw)
        assert req.jsonrpc == "2.0"
        assert req.id == 1
        assert req.method == "document.list"
        assert req.params == {}

    def test_valid_request_no_params(self) -> None:
        raw = '{"jsonrpc":"2.0","id":2,"method":"server.ping"}'
        req = decode_request(raw)
        assert req.method == "server.ping"
        assert req.params is None

    def test_notification_no_id(self) -> None:
        raw = '{"jsonrpc":"2.0","method":"server.event","params":{"type":"test"}}'
        req = decode_request(raw)
        assert req.id is None
        assert req.method == "server.event"

    def test_invalid_json_raises(self) -> None:
        with pytest.raises(json.JSONDecodeError):
            decode_request("not valid json")

    def test_missing_method_raises(self) -> None:
        raw = '{"jsonrpc":"2.0","id":1}'
        with pytest.raises(ValueError, match="Missing.*method"):
            decode_request(raw)

    def test_wrong_version_raises(self) -> None:
        raw = '{"jsonrpc":"1.0","id":1,"method":"test"}'
        with pytest.raises(ValueError, match="Unsupported.*version"):
            decode_request(raw)

    def test_empty_method_raises(self) -> None:
        raw = '{"jsonrpc":"2.0","id":1,"method":""}'
        with pytest.raises(ValueError, match="Missing.*method"):
            decode_request(raw)

    def test_non_dict_payload_raises(self) -> None:
        raw = '["not a dict"]'
        with pytest.raises(ValueError, match="must be a JSON object"):
            decode_request(raw)


class TestEncodeResponse:
    """Tests for ``encode_response()``."""

    def test_success_response(self) -> None:
        resp = make_success_response(1, {"result": "ok"})
        raw = encode_response(resp)
        parsed = json.loads(raw)
        assert parsed["jsonrpc"] == "2.0"
        assert parsed["id"] == 1
        assert parsed["result"] == {"result": "ok"}
        assert "error" not in parsed

    def test_error_response(self) -> None:
        resp = make_error_response(1, METHOD_NOT_FOUND, "Method not found")
        raw = encode_response(resp)
        parsed = json.loads(raw)
        assert parsed["id"] == 1
        assert parsed["error"]["code"] == METHOD_NOT_FOUND
        assert parsed["error"]["message"] == "Method not found"
        assert "result" not in parsed

    def test_response_with_data(self) -> None:
        resp = make_error_response(
            1, COMMAND_FAILED, "Failed", data={"detail": "something"}
        )
        raw = encode_response(resp)
        parsed = json.loads(raw)
        assert parsed["error"]["data"] == {"detail": "something"}

    def test_notification_no_response_id(self) -> None:
        # Notifications should still encode ok even with None id
        resp = make_success_response(None, None)
        raw = encode_response(resp)
        parsed = json.loads(raw)
        # No "id" field or null id
        assert "id" not in parsed or parsed["id"] is None


class TestEncodeEvent:
    """Tests for ``encode_event()``."""

    def test_event_encoding(self) -> None:
        event = ServerEvent(
            type="document.modified",
            data={"doc_id": "abc-123"},
            timestamp=1000.0,
        )
        raw = encode_event(event)
        parsed = json.loads(raw)
        assert parsed["jsonrpc"] == "2.0"
        assert parsed["method"] == "server.event"
        assert parsed["params"]["type"] == "document.modified"
        assert parsed["params"]["data"] == {"doc_id": "abc-123"}
        assert parsed["params"]["timestamp"] == 1000.0

    def test_make_event(self) -> None:
        event = make_event("test.event", {"key": "value"})
        assert event.type == "test.event"
        assert event.data == {"key": "value"}
        assert isinstance(event.timestamp, float)
        assert event.timestamp > 0


class TestMakeResponses:
    """Tests for response and event factory functions."""

    def test_make_success(self) -> None:
        resp = make_success_response(5, {"data": [1, 2, 3]})
        assert resp.id == 5
        assert resp.result == {"data": [1, 2, 3]}
        assert resp.error is None

    def test_make_error(self) -> None:
        resp = make_error_response(5, DOCUMENT_NOT_OPEN)
        assert resp.id == 5
        assert resp.error is not None
        assert resp.error.code == DOCUMENT_NOT_OPEN
        assert resp.error.message == "Document not open"
        assert resp.result is None

    def test_make_error_custom_message(self) -> None:
        resp = make_error_response(5, DOCUMENT_NOT_OPEN, "Custom message")
        assert resp.error.message == "Custom message"

    def test_make_error_with_data(self) -> None:
        resp = make_error_response(5, COMMAND_FAILED, "fail", data={"reason": "test"})
        assert resp.error.data == {"reason": "test"}
