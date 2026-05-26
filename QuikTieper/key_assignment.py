from __future__ import annotations

import itertools
import re
from collections.abc import Iterable


SAFE_LAUNCH_LETTERS = "abcgijklmnoruvxyz"
DEFAULT_PRESERVED_APP_NAMES = frozenset({"brave", "vs-code", "terminal", "files"})


def assign_missing_launch_keys(
    config: dict,
    *,
    alphabet: str = SAFE_LAUNCH_LETTERS,
    reassign: bool = False,
    preserved_app_names: frozenset[str] = DEFAULT_PRESERVED_APP_NAMES,
) -> tuple[dict, int]:
    assigned = {"apps": [dict(app) for app in config.get("apps", [])]}
    used = set()
    if not reassign:
        used = {_key_identity(app.get("launch", {}).get("keys", [])) for app in assigned["apps"]}
        used.discard(frozenset())
    else:
        for app in assigned["apps"]:
            if str(app.get("name", "")).strip().lower() in preserved_app_names:
                identity = _key_identity(app.get("launch", {}).get("keys", []))
                if identity:
                    used.add(identity)
    candidates = _candidate_stream(alphabet)
    changed = 0

    for app in assigned["apps"]:
        launch = dict(app.get("launch", {}))
        app_name = str(app.get("name", "")).strip()
        if launch.get("keys") and not (reassign and app_name.lower() not in preserved_app_names):
            continue
        keys = _next_keys(str(app.get("name", "")), used, candidates, alphabet)
        launch["keys"] = list(keys)
        app["launch"] = launch
        used.add(_key_identity(keys))
        changed += 1

    return assigned, changed


def _next_keys(
    name: str,
    used: set[frozenset[str]],
    candidates: Iterable[tuple[str, ...]],
    alphabet: str,
) -> tuple[str, ...]:
    mnemonic = _mnemonic_candidate(name, alphabet)
    if _key_identity(mnemonic) not in used:
        return mnemonic
    for candidate in candidates:
        if _key_identity(candidate) not in used:
            return candidate
    raise ValueError("ran out of launch key combinations")


def _mnemonic_candidate(name: str, alphabet: str) -> tuple[str, ...]:
    letters = []
    for char in re.sub(r"[^a-zA-Z]", "", name).lower():
        if char in alphabet and char not in letters:
            letters.append(char)
    while len(letters) < 3:
        for char in alphabet:
            if char not in letters:
                letters.append(char)
                break
    return ("alt", *letters[:3])


def _candidate_stream(alphabet: str) -> Iterable[tuple[str, ...]]:
    for chars in itertools.combinations(alphabet, 3):
        yield ("alt", *chars)


def _key_identity(keys: list[str] | tuple[str, ...]) -> frozenset[str]:
    return frozenset(str(key).strip().lower() for key in keys if str(key).strip())
