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
