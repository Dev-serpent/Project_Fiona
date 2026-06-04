from __future__ import annotations

from typing import Any
from FionaCore.actions import default_action_specs

def get_fiona_tool_schemas() -> list[dict[str, Any]]:
    """
    Return a list of tool schemas for FionaCore actions, 
    formatted for OpenAI-compatible tool calling.
    """
    tools = []
    for spec in default_action_specs():
        tools.append({
            "type": "function",
            "function": {
                "name": spec.name,
                "description": spec.description,
                "parameters": {
                    "type": "object",
                    "properties": {},
                    "required": [],
                },
            },
        })
    
    # Add specialized tools with parameters
    tools.append({
        "type": "function",
        "function": {
            "name": "recall.search",
            "description": "Search for remembrances in the RecallVault.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The search query (keyword or phrase)."
                    }
                },
                "required": ["query"],
            },
        },
    })
    
    tools.append({
        "type": "function",
        "function": {
            "name": "speech.speak",
            "description": "Speak text aloud using the system TTS.",
            "parameters": {
                "type": "object",
                "properties": {
                    "text": {
                        "type": "string",
                        "description": "The text to speak."
                    }
                },
                "required": ["text"],
            },
        },
    })

    return tools
