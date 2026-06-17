from __future__ import annotations

import json
import unittest
from unittest.mock import patch

from Agent import OllamaClient


class OllamaClientTests(unittest.TestCase):
    def test_ask_uses_ollama_chat_api(self) -> None:
        captured_payloads: list[dict] = []

        class FakeResponse:
            def __enter__(self) -> FakeResponse:
                return self

            def __exit__(self, *_args: object) -> None:
                return None

            def read(self) -> bytes:
                return json.dumps({"message": {"content": "agent ready"}}).encode("utf-8")

        def fake_urlopen(request: object, timeout: float) -> FakeResponse:
            del timeout
            captured_payloads.append(json.loads(request.data.decode("utf-8")))
            return FakeResponse()

        with patch("Agent.ollama.urlopen", fake_urlopen):
            client = OllamaClient(base_url="http://127.0.0.1:11434/api", model="test-model")
            self.assertEqual(client.ask("status"), "agent ready")

        self.assertEqual(captured_payloads[0]["model"], "test-model")
        self.assertEqual(captured_payloads[0]["messages"][-1]["content"], "status")


if __name__ == "__main__":
    unittest.main()
