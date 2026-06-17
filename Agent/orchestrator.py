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
        self.max_turns = 5

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

        return f"""You are Fiona, a high-performance workstation control assistant.
Your goal is to help the user manage their system using the tools provided.

AVAILABLE COMMANDS:
{commands_str}

AVAILABLE APPLICATIONS:
{apps_str}

OUTPUT FORMAT:
You must output a JSON object with the following structure:
{{
  "thought": "Your reasoning about what to do next",
  "action": "command_name_or_null",
  "input": {{ "arg": "value" }}
}}

If you have completed the task or cannot proceed, set "action" to null.
Be concise. Focus on efficient workstation management.
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
            # Special case for launch_binding which might need mapping
            if name == "launch_binding":
                app_name = params.get("name")
                result = self.router.run(f"launch:{app_name}", source="agent")
            else:
                # Generic action mapping (simplified for now)
                # In a real implementation, we'd map registry names to ActionRouter methods
                result = self.router.run(f"{name}:{json.dumps(params)}", source="agent")
            
            return f"Status: {'Success' if result.ok else 'Failed'}\nOutput: {result.message}"
        except Exception as e:
            return f"Execution Error: {e}"


def run_agent_goal(goal: str) -> str:
    orchestrator = AgentOrchestrator()
    return orchestrator.run_goal(goal)
