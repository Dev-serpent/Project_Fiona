from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from CamComs.encryption import CamComsCryptoError
from CamComs.paths import DEFAULT_CAMCOMS_DIR


DEFAULT_REPLAY_PATH = DEFAULT_CAMCOMS_DIR / "seen_messages.json"


class ReplayGuard:
    def __init__(self, path: Path = DEFAULT_REPLAY_PATH, *, max_age_seconds: int = 300) -> None:
        self.path = path
        self.max_age_seconds = max_age_seconds

    def check_and_record(self, envelope: dict[str, Any], *, now: int | None = None) -> None:
        current_time = int(time.time()) if now is None else now
        message_id = envelope.get("message_id")
        created_at = envelope.get("created_at")
        if not isinstance(message_id, str) or not message_id:
            raise CamComsCryptoError("message_id is required for replay protection")
        if not isinstance(created_at, int):
            raise CamComsCryptoError("created_at must be an integer timestamp")
        if abs(current_time - created_at) > self.max_age_seconds:
            raise CamComsCryptoError("message timestamp is outside the allowed replay window")

        seen = self._load_seen()
        self._prune_seen(seen, current_time)
        if message_id in seen:
            raise CamComsCryptoError("message_id has already been seen")
        seen[message_id] = created_at
        self._write_seen(seen)

    def _load_seen(self) -> dict[str, int]:
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return {}
        if not isinstance(raw, dict):
            return {}
        return {str(key): int(value) for key, value in raw.items()}

    def _write_seen(self, seen: dict[str, int]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(seen, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    def _prune_seen(self, seen: dict[str, int], now: int) -> None:
        cutoff = now - self.max_age_seconds
        for message_id, created_at in list(seen.items()):
            if created_at < cutoff:
                del seen[message_id]
