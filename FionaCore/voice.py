from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class VoiceCommand:
    text: str
    action: str
    confidence: float

    def to_dict(self) -> dict[str, object]:
        return {"text": self.text, "action": self.action, "confidence": self.confidence}


VOICE_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"\b(show|open)\s+(the\s+)?host\s+status\b"), "host.status"),
    (re.compile(r"\b(show|open)\s+(the\s+)?fat\b|\bterminal\s+dashboard\b"), "fat.status"),
    (re.compile(r"\bcam\s*coms\s+(smoke|test)\b|\bencryption\s+test\b"), "camcoms.smoke"),
    (re.compile(r"\b(show|open)\s+(cam\s*coms\s+)?paths\b"), "camcoms.paths"),
    (re.compile(r"\b(show|list)\s+(bindings|shortcuts)\b"), "quiktieper.list"),
    (re.compile(r"\bdesktop\s+status\b|\bwhat\s+is\s+open\b"), "seeondesk.status"),
    (re.compile(r"\beye\s*control\s+status\b"), "eyecontrol.status"),
    (re.compile(r"\bagent\s+status\b|\blm\s+studio\s+status\b"), "agent.status"),
)


def parse_voice_command(text: str) -> VoiceCommand | None:
    normalized = " ".join(text.strip().lower().split())
    if not normalized:
        return None
    for pattern, action in VOICE_PATTERNS:
        if pattern.search(normalized):
            return VoiceCommand(text=text, action=action, confidence=0.9)
    return None
