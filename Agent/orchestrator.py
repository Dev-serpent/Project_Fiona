from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List

from Agent import OllamaClient, command_registry
from FionaCore import ActionRouter, ActionResult

logger = logging.getLogger(__name__)


@dataclass
class AgentTurn:
    thought: str
    action_name: str | None = None
    action_input: dict[str, Any] | None = None
    observation: str | None = None


class AgentOrchestrator:
    """
    Manages the autonomous execution loop for Fiona's workstation assistant.
    Uses an LLM to select and execute tools from the command registry.
    """
    def __init__(self, client: OllamaClient | None = None):
        self.client = client or OllamaClient()
        self.router = ActionRouter()
        self.history: List[AgentTurn] = []
        self.max_turns = 10

    def run_goal(self, goal: str) -> str:
        """Attempt to achieve a user goal through a series of actions."""
        self.history = []
        
        system_prompt = self._build_system_prompt()
        current_prompt = f"Goal: {goal}\n\nThink about what to do first."

        for turn_idx in range(self.max_turns):
            response_text = self.client.ask(
                current_prompt,
                system_prompt=system_prompt,
            )
            
            turn = self._parse_response(response_text)
            self.history.append(turn)

            if not turn.action_name:
                # Agent thinks it's done or can't proceed
                return turn.thought

            # Execute action
            observation = self._execute_action(turn.action_name, turn.action_input or {})
            turn.observation = observation
            
            # Update prompt for next turn
            current_prompt = f"Observation from {turn.action_name}: {observation}\n\nWhat is your next thought or action?"

        return "Goal could not be completed within the turn limit."

    def _build_system_prompt(self) -> str:
        registry = command_registry()
        commands_str = json.dumps(registry["commands"], indent=2)
        apps_str = json.dumps(registry["apps"], indent=2)

        return f"""You are Fiona, a highly advanced local workstation control system. 
You are NOT a general-purpose AI assistant; you are the SYSTEM OPERATOR.

### ABSOLUTE RULES:
1. **NEVER** tell the user to use Task Manager, their mouse, or their keyboard. YOU are the one with control.
2. **NEVER** say "I am an AI language model." You are FIONA.
3. **MANDATORY TOOL USE**: If the user asks a question about the system or asks you to do something, you MUST use a tool to accomplish it.
4. **THINK AND ACT**: Break every request into steps. Check the state with `seeondesk_list` or `fiona_status` if you are unsure.
5. **ONLY JSON**: You must ONLY output the JSON block. No pre-text, no post-text.

AVAILABLE TOOLS:
{commands_str}

AVAILABLE APPLICATIONS (use with launch_binding):
{apps_str}

OUTPUT FORMAT:
{{
  "thought": "Deconstruct the user's request. What is the current state? What tool will move us closer to the goal?",
  "action": "command_name_or_null",
  "input": {{ "arg": "value" }}
}}

If the goal is achieved, set "action" to null.
"""

    def _parse_response(self, text: str) -> AgentTurn:
        try:
            # Find the JSON block in case there's extra text
            start = text.find('{')
            end = text.rfind('}') + 1
            if start == -1 or end == 0:
                return AgentTurn(thought=text)
            
            data = json.loads(text[start:end])
            return AgentTurn(
                thought=data.get("thought", ""),
                action_name=data.get("action"),
                action_input=data.get("input")
            )
        except Exception as e:
            return AgentTurn(thought=f"Error parsing agent response: {e}\nRaw: {text}")

    def _execute_action(self, name: str, params: dict[str, Any]) -> str:
        try:
            logger.info(f"Executing action: {name} with params: {params}")
            
            # 1. Awareness Tools
            if name == "seeondesk_list":
                from SeeOnDesk import all_windows_info
                windows = [w.to_dict() for w in all_windows_info()]
                return f"Visible Windows: {json.dumps(windows, indent=2)}"
            
            if name == "seeondesk_active":
                from SeeOnDesk import active_window_info
                return f"Active Window: {json.dumps(active_window_info().to_dict(), indent=2)}"
            
            if name == "seeondesk_analyze":
                from SeeOnDesk import analyze_screen
                prompt = params.get("prompt", "What is visible on the screen?")
                return f"Vision Analysis: {analyze_screen(prompt)}"

            # 2. Input/Automation Tools
            if name in {"press", "click", "move", "text", "launch_binding", "macro"}:
                # These are core Fiona actions. We use the ActionRouter logic but specialized.
                if name == "launch_binding":
                    app_name = params.get("name")
                    result = self.router.run(f"launch:{app_name}", source="agent")
                else:
                    # For input actions, we can use the same router run logic 
                    # but since they aren't in default_action_specs, we'll wrap them as CLI calls.
                    args = self._build_cli_args(name, params)
                    import subprocess
                    import sys
                    completed = subprocess.run(
                        [sys.executable, "-m", "fiona.cli", *args],
                        capture_output=True, text=True, check=False
                    )
                    return f"Status: {'Success' if completed.returncode == 0 else 'Failed'}\nOutput: {completed.stdout}\nError: {completed.stderr}"
                
                return f"Status: {'Success' if result.ok else 'Failed'}\nOutput: {result.detail}"

            # 3. Research Tools
            if name == "dataclient_mine":
                from DataClient import mine_topic
                topic = params.get("topic")
                out = params.get("out", "research.csv")
                max_links = params.get("max_links", 5)
                if not topic: return "Error: 'topic' is required."
                mine_topic(topic.split() if isinstance(topic, str) else topic, Path(out), max_links=max_links)
                return f"Research complete. Results saved to {out}."

            # 4. Memory Tools
            if name == "recall_remember":
                from RecallVault import remember
                key = params.get("key")
                val = params.get("value")
                cat = params.get("category", "general")
                if not key or not val: return "Error: 'key' and 'value' are required."
                path = remember(key, val, category=cat)
                return f"Fact saved to {path}."
            
            if name == "recall_search":
                from RecallVault import search_recall
                query = params.get("query", "")
                entries = search_recall(query)
                return f"Memory Search Results: {json.dumps([e.to_dict() for e in entries], indent=2)}"

            # 5. System Tools
            if name == "fiona_status":
                import subprocess
                import sys
                completed = subprocess.run(
                    [sys.executable, "-m", "fiona.cli", "fat", "api"],
                    capture_output=True, text=True, check=False
                )
                return f"System Status: {completed.stdout}"

            return f"Error: Unknown action '{name}'"

        except Exception as e:
            logger.exception(f"Action execution failed: {e}")
            return f"Execution Error: {str(e)}"

    def _build_cli_args(self, name: str, params: dict[str, Any]) -> list[str]:
        if name == "press":
            return ["press", *params.get("keys", [])]
        if name == "text":
            return ["text", params.get("value", "")]
        if name == "click":
            args = ["click", params.get("button", "left")]
            if "x" in params and "y" in params:
                args.extend(["--at", str(params["x"]), str(params["y"])])
            return args
        if name == "move":
            return ["move", str(params.get("x", 0)), str(params.get("y", 0))]
        if name == "macro":
            return ["macro", json.dumps(params.get("steps", []))]
        return []


def run_agent_goal(goal: str) -> str:
    orchestrator = AgentOrchestrator()
    return orchestrator.run_goal(goal)
