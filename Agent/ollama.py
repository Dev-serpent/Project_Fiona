from __future__ import annotations

import json
import base64
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.error import URLError
from urllib.request import Request, urlopen


DEFAULT_OLLAMA_BASE_URL = "http://localhost:11434/api"


class OllamaError(RuntimeError):
    """Raised when Fiona cannot talk to the Ollama local server."""


# ---------------------------------------------------------------------------
# Tool-call model types
#
# ``ToolCall`` is imported from the canonical ``fiona.tools.models`` module.
# ``ChatResponse`` is specific to the Ollama API and lives here.
# ---------------------------------------------------------------------------

from fiona.tools.models import ToolCall


@dataclass(frozen=True)
class ChatResponse:
    """Structured response from a model invocation that may include tool calls."""

    content: str | None
    tool_calls: list[ToolCall] | None
    finish_reason: str  # "stop" | "tool_calls" | "length"
    usage: dict[str, Any] | None = None

    @classmethod
    def from_api_response(cls, data: dict) -> ChatResponse:
        """Parse an Ollama ``/api/chat`` JSON response into a ``ChatResponse``."""
        message: dict = data.get("message") or {}
        content: str | None = message.get("content")

        raw_tool_calls: list[dict] | None = message.get("tool_calls")
        tool_calls: list[ToolCall] | None = None
        if raw_tool_calls:
            tool_calls = []
            for tc in raw_tool_calls:
                func: dict = tc.get("function") or {}
                raw_args = func.get("arguments", "{}")
                if isinstance(raw_args, str):
                    try:
                        parsed_args: dict[str, Any] = json.loads(raw_args)
                    except json.JSONDecodeError:
                        parsed_args = {}
                else:
                    parsed_args = raw_args  # already a dict
                tool_calls.append(
                    ToolCall(
                        id=tc.get("id", ""),
                        function_name=func.get("name", ""),
                        arguments=parsed_args,
                    )
                )

        finish_reason: str = data.get("finish_reason", "stop")
        usage: dict[str, Any] | None = data.get("usage")

        return cls(
            content=content,
            tool_calls=tool_calls,
            finish_reason=finish_reason,
            usage=usage,
        )


# Sentinel used to detect when *system_prompt* is not explicitly passed
# to ``ask()`` so we can fall back to the personality's default.
_ASK_SENTINEL = object()


@dataclass(frozen=True)
class OllamaClient:
    base_url: str = DEFAULT_OLLAMA_BASE_URL
    model: str = "qwen3:8b-en"
    timeout_seconds: float = 120.0
    personality: Any | None = None  # Agent.personality.Personality | None

    def __post_init__(self) -> None:
        """Apply personality overrides after initialisation.

        When a personality with a *model_override* is provided, the client's
        *model* field is updated accordingly.
        """
        if self.personality is not None:
            if self.personality.model_override is not None:
                object.__setattr__(self, "model", self.personality.model_override)

    def health(self) -> dict[str, Any]:
        return self._request("GET", "/tags")

    def ask(
        self,
        prompt: str,
        *,
        system_prompt: Any = _ASK_SENTINEL,  # str — sentinel detects "not passed"
        image_path: str | Path | None = None,
        temperature: float = 0.3,
        max_tokens: int = 2048,
    ) -> str:
        # Resolve system prompt from personality when caller didn't pass one.
        if system_prompt is _ASK_SENTINEL:
            if self.personality is not None:
                system_prompt = self.personality.system_prompt
            else:
                system_prompt = "You are Fiona, a local workstation control assistant."

        messages = []
        # Ollama /api/chat doesn't always handle 'system' role the same way across all models,
        # but for LLaVA/Moondream it's usually better to just prepended to the prompt if needed,
        # however let's try the standard message format first.
        
        user_message: dict[str, Any] = {"role": "user", "content": prompt}
        
        if image_path:
            image_path = Path(image_path)
            if not image_path.exists():
                raise OllamaError(f"image path does not exist: {image_path}")
            
            with open(image_path, "rb") as f:
                encoded_image = base64.b64encode(f.read()).decode("utf-8")
            
            user_message["images"] = [encoded_image]

        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                user_message
            ],
            "stream": False,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
            }
        }
        
        response = self._request("POST", "/chat", payload)
        try:
            return str(response["message"]["content"])
        except (KeyError, IndexError, TypeError) as exc:
            raise OllamaError(f"unexpected Ollama response: {response}") from exc

    def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        temperature: float = 0.3,
        max_tokens: int = 2048,
    ) -> ChatResponse:
        """Send a multi-message conversation to Ollama, optionally with tool definitions.

        Parameters
        ----------
        messages:
            A list of message dicts, each with ``role`` and ``content`` keys
            (and optionally ``images`` for vision models).
        tools:
            An optional list of tool definitions in the JSON Schema format
            that Ollama's ``/api/chat`` endpoint expects.
            When ``None`` or empty the request is identical to ``ask()``
            (no tool definitions are sent).
        temperature:
            Sampling temperature (default 0.3).
        max_tokens:
            Maximum number of tokens to generate (default 2048).

        Returns
        -------
        ChatResponse
            A structured response containing the model's text reply, any tool
            calls, the finish reason, and optional usage metadata.
        """
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
            },
        }
        if tools:
            payload["tools"] = tools

        response = self._request("POST", "/chat", payload)
        try:
            return ChatResponse.from_api_response(response)
        except (KeyError, TypeError, ValueError) as exc:
            raise OllamaError(f"unexpected Ollama response: {response}") from exc

    def _request(self, method: str, path: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        url = self.base_url.rstrip("/") + path
        body = json.dumps(payload).encode("utf-8") if payload is not None else None
        request = Request(
            url,
            data=body,
            method=method,
            headers={
                "Content-Type": "application/json",
            },
        )
        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:
                data = json.loads(response.read().decode("utf-8"))
        except (OSError, URLError, json.JSONDecodeError) as exc:
            raise OllamaError(f"could not reach Ollama at {url}: {exc}") from exc
        if not isinstance(data, dict):
            raise OllamaError(f"Ollama returned non-object JSON: {data!r}")
        return data
