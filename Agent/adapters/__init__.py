"""Adapters for converting between canonical tool models and LLM-specific formats."""

from Agent.adapters.ollama_adapter import (
    ollama_tool_call_to_model,
    tool_spec_to_ollama,
)


class OllamaToolAdapter:
    """Convenience namespace wrapping Ollama adapter functions.

    Usage::

        from Agent.adapters import OllamaToolAdapter

        ollama_def = OllamaToolAdapter.tool_spec_to_ollama(spec)
        tool_call = OllamaToolAdapter.ollama_tool_call_to_model(raw)
    """

    tool_spec_to_ollama = staticmethod(tool_spec_to_ollama)
    ollama_tool_call_to_model = staticmethod(ollama_tool_call_to_model)


__all__ = [
    "OllamaToolAdapter",
    "ollama_tool_call_to_model",
    "tool_spec_to_ollama",
]
