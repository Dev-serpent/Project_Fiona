from __future__ import annotations

import os
import shutil
import subprocess
from typing import Literal


def speak(text: str, mode: Literal["speech-dispatcher", "dummy", "auto"] = "auto") -> bool:
    """
    Speak text using the available system TTS engine.

    Backend selection (auto-pick order):
      1. Windows: ``pyttsx3`` (SAPI5)
      2. Linux:   ``spd-say`` (speech-dispatcher)

    Args:
        text: The text to speak.
        mode:
          - ``"auto"``: pick the best backend for the current OS.
          - ``"speech-dispatcher"``: force Linux ``spd-say``.
          - ``"dummy"``: no-op, returns ``True``.

    Returns:
        ``True`` if the text was spoken successfully.
    """
    if mode == "dummy":
        return True

    # --- Windows (SAPI5 via pyttsx3) ---
    if os.name == "nt" or mode == "auto":
        try:
            import pyttsx3
            engine = pyttsx3.init(driverName="sapi5")
            engine.say(text)
            engine.runAndWait()
            return True
        except ImportError:
            if mode == "speech-dispatcher":
                pass  # fall through to Linux path
        except Exception:
            pass

    # --- Linux (speech-dispatcher) ---
    if mode in ("speech-dispatcher", "auto"):
        spd_say = shutil.which("spd-say")
        if spd_say:
            try:
                subprocess.run(
                    [spd_say, text],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    check=True,
                )
                return True
            except subprocess.SubprocessError:
                pass

    return False
