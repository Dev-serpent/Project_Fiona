from __future__ import annotations

import json
from typing import Any


INSTRUCTION_VERSION = 1
ALLOWED_TYPES = {"press", "click", "move", "launch_binding", "text", "macro"}
ALLOWED_BUTTONS = {"left", "right", "middle"}


class CamComsInstructionError(ValueError):
    """Raised when a remote instruction does not match the CamComs schema."""


def press_instruction(keys: list[str]) -> dict[str, Any]:
    instruction = {
        "version": INSTRUCTION_VERSION,
        "type": "press",
        "keys": keys,
    }
    validate_instruction(instruction)
    return instruction


def validate_instruction(instruction: dict[str, Any]) -> dict[str, Any]:
    if instruction.get("version") != INSTRUCTION_VERSION:
        raise CamComsInstructionError("instruction version must be 1")

    instruction_type = instruction.get("type")
    if instruction_type not in ALLOWED_TYPES:
        raise CamComsInstructionError(f"instruction type must be one of: {', '.join(sorted(ALLOWED_TYPES))}")

    if instruction_type == "press":
        keys = instruction.get("keys")
        if not isinstance(keys, list) or not keys:
            raise CamComsInstructionError("press instruction requires a non-empty keys list")
        if not all(isinstance(key, str) and key.strip() for key in keys):
            raise CamComsInstructionError("press instruction keys must be non-empty strings")

    elif instruction_type == "click":
        button = instruction.get("button")
        if button not in ALLOWED_BUTTONS:
            raise CamComsInstructionError(f"click button must be one of: {', '.join(sorted(ALLOWED_BUTTONS))}")
        _validate_optional_int(instruction, "x")
        _validate_optional_int(instruction, "y")

    elif instruction_type == "move":
        _validate_required_int(instruction, "x")
        _validate_required_int(instruction, "y")

    elif instruction_type == "launch_binding":
        name = instruction.get("name")
        if not isinstance(name, str) or not name.strip():
            raise CamComsInstructionError("launch_binding instruction requires a non-empty name")

    elif instruction_type == "text":
        value = instruction.get("value")
        if not isinstance(value, str):
            raise CamComsInstructionError("text instruction requires a string value")

    elif instruction_type == "macro":
        steps = instruction.get("steps")
        if not isinstance(steps, list) or not steps:
            raise CamComsInstructionError("macro instruction requires a non-empty steps list")
        for step in steps:
            if not isinstance(step, dict):
                raise CamComsInstructionError("macro steps must be instruction objects")
            validate_instruction(step)

    return instruction


def instruction_to_text(instruction: dict[str, Any]) -> str:
    return json.dumps(validate_instruction(instruction), sort_keys=True, separators=(",", ":"))


def instruction_from_text(raw: str) -> dict[str, Any]:
    try:
        instruction = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise CamComsInstructionError("instruction must be JSON") from exc
    if not isinstance(instruction, dict):
        raise CamComsInstructionError("instruction must be a JSON object")
    return validate_instruction(instruction)


def _validate_required_int(instruction: dict[str, Any], key: str) -> None:
    if not isinstance(instruction.get(key), int):
        raise CamComsInstructionError(f"{instruction.get('type')} instruction requires integer {key}")


def _validate_optional_int(instruction: dict[str, Any], key: str) -> None:
    if key in instruction and not isinstance(instruction[key], int):
        raise CamComsInstructionError(f"{instruction.get('type')} instruction {key} must be an integer")
