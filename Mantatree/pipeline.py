from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List


@dataclass
class MantaMessage:
    topic: str
    payload: Any
    sender: str = "system"
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_json(self) -> str:
        return json.dumps({
            "topic": self.topic,
            "payload": self.payload,
            "sender": self.sender,
            "timestamp": self.timestamp
        })


class MantaTree:
    """
    Mantatree: A General communication pipeline for Fiona modules.
    Provides a central hub for inter-module messaging and state sharing.
    """
    def __init__(self):
        self._subscribers: Dict[str, List[Callable[[MantaMessage], None]]] = {}
        self._state: Dict[str, Any] = {}

    def publish(self, topic: str, payload: Any, sender: str = "system"):
        message = MantaMessage(topic=topic, payload=payload, sender=sender)
        
        # Update internal state if applicable
        self._state[topic] = payload
        
        # Notify subscribers
        if topic in self._subscribers:
            for callback in self._subscribers[topic]:
                try:
                    callback(message)
                except Exception as e:
                    print(f"Mantatree Error [Topic: {topic}]: {e}")
        
        # Also notify wildcard subscribers (if implemented later)
        return message

    def subscribe(self, topic: str, callback: Callable[[MantaMessage], None]):
        if topic not in self._subscribers:
            self._subscribers[topic] = []
        self._subscribers[topic].append(callback)

    def get_state(self, topic: str) -> Any:
        return self._state.get(topic)

    def dump_state(self) -> Dict[str, Any]:
        return self._state.copy()


# Global singleton for easy access across modules
_pipeline = MantaTree()


def get_pipeline() -> MantaTree:
    return _pipeline
