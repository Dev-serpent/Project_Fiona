"""Converts canonical ToolSpec objects into Ollama /api/chat tool format."""

import json

from fiona.tools.models import ToolCall, ToolSpec


def tool_spec_to_ollama(spec: ToolSpec) -> dict:
    """Convert a ToolSpec to an Ollama-compatible tool definition dict.

    Returns::

        {
            "type": "function",
            "function": {
                "name": spec.name,
                "description": spec.description,
                "parameters": spec.input_schema
            }
        }
    """
    return {
        "type": "function",
        "function": {
            "name": spec.name,
            "description": spec.description,
            "parameters": spec.input_schema,
        },
    }


def ollama_tool_call_to_model(raw: dict) -> ToolCall:
    """Parse a raw Ollama tool_call dict into a canonical ToolCall.

    Handles the case where *arguments* is a JSON string (Ollama format)
    versus already a ``dict``.
    """
    func = raw.get("function", {})
    raw_args = func.get("arguments", "{}")
    if isinstance(raw_args, str):
        try:
            args = json.loads(raw_args)
        except json.JSONDecodeError:
            args = {}
    else:
        args = raw_args

    return ToolCall(
        id=raw.get("id", ""),
        function_name=func.get("name", ""),
        arguments=args,
    )
