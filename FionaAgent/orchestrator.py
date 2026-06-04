from __future__ import annotations

import json
from typing import Any

from Agent.lmstudio import LMStudioClient, LMStudioError
from FionaCore.actions import ActionRouter
from FionaCore.speech import speak
from RecallVault.vault import search_recall
from .tools import get_fiona_tool_schemas

class FionaOrchestrator:
    def __init__(
        self,
        client: LMStudioClient | None = None,
        router: ActionRouter | None = None,
        system_prompt: str | None = None
    ) -> None:
        self.client = client or LMStudioClient()
        self.router = router or ActionRouter()
        self.system_prompt = system_prompt or (
            "You are JARVIS, a sophisticated workstation assistant. "
            "You have access to local tools to control the host. "
            "Be concise, professional, and proactive."
        )
        self.tools = get_fiona_tool_schemas()

    def chat(self, user_input: str) -> str:
        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": user_input}
        ]

        try:
            # First turn: Ask LLM for initial response/tool calls
            response = self._get_completion(messages)
            
            # Handle tool calls in a loop (up to 5 iterations for safety)
            for _ in range(5):
                if not response.get("tool_calls"):
                    break
                
                messages.append(response)
                
                for tool_call in response["tool_calls"]:
                    name = tool_call["function"]["name"]
                    arguments = json.loads(tool_call["function"]["arguments"])
                    
                    result_data = self._execute_tool(name, arguments)
                    
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call["id"],
                        "name": name,
                        "content": json.dumps(result_data)
                    })
                
                response = self._get_completion(messages)

            return str(response.get("content", "I am unable to process that request."))

        except (LMStudioError, Exception) as exc:
            return f"System Error: {exc}"

    def _get_completion(self, messages: list[dict[str, Any]]) -> dict[str, Any]:
        payload = {
            "model": self.client.model,
            "messages": messages,
            "tools": self.tools,
            "tool_choice": "auto"
        }
        resp = self.client._request("POST", "/chat/completions", payload)
        return resp["choices"][0]["message"]

    def _execute_tool(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        if name == "recall.search":
            results = search_recall(arguments.get("query", ""))
            return {"results": [r.to_dict() for r in results]}
        
        if name == "speech.speak":
            success = speak(arguments.get("text", ""))
            return {"success": success}

        # Route to FionaCore actions
        try:
            result = self.router.run(name)
            return result.to_dict()
        except ValueError:
            return {"error": f"Tool {name} not found."}
