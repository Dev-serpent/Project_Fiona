from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any
from urllib.error import URLError
from urllib.request import Request, urlopen


DEFAULT_LM_STUDIO_BASE_URL = "http://localhost:1234/v1"


class LMStudioError(RuntimeError):
    """Raised when Fiona cannot talk to the LM Studio local server."""


@dataclass(frozen=True)
class LMStudioClient:
    base_url: str = DEFAULT_LM_STUDIO_BASE_URL
    model: str = "local-model"
    api_key: str = "lm-studio"
    timeout_seconds: float = 30.0

    def health(self) -> dict[str, Any]:
        return self._request("GET", "/models")

    def ask(
        self,
        prompt: str,
        *,
        system_prompt: str = "You are Fiona, a local workstation control assistant.",
        temperature: float = 0.3,
        max_tokens: int = 512,
    ) -> str:
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt},
            ],
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        response = self._request("POST", "/chat/completions", payload)
        try:
            return str(response["choices"][0]["message"]["content"])
        except (KeyError, IndexError, TypeError) as exc:
            raise LMStudioError(f"unexpected LM Studio response: {response}") from exc

    def _request(self, method: str, path: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        url = self.base_url.rstrip("/") + path
        body = json.dumps(payload).encode("utf-8") if payload is not None else None
        request = Request(
            url,
            data=body,
            method=method,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
        )
        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:
                data = json.loads(response.read().decode("utf-8"))
        except (OSError, URLError, json.JSONDecodeError) as exc:
            raise LMStudioError(f"could not reach LM Studio at {url}: {exc}") from exc
        if not isinstance(data, dict):
            raise LMStudioError(f"LM Studio returned non-object JSON: {data!r}")
        return data
