from __future__ import annotations

import shutil
import subprocess
from typing import Literal

def speak(text: str, mode: Literal["speech-dispatcher", "dummy"] = "speech-dispatcher") -> bool:
    """
    Speak text using the available system TTS engine.
    Currently supports speech-dispatcher (spd-say).
    """
    if mode == "dummy":
        return True

    spd_say = shutil.which("spd-say")
    if not spd_say:
        return False

    try:
        subprocess.run(
            [spd_say, text],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=True
        )
        return True
    except subprocess.SubprocessError:
        return False
