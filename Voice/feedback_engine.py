"""Feedback engine providing audio/visual feedback for voice commands."""

from __future__ import annotations

import logging
import subprocess
import os
from pathlib import Path
from typing import Literal

logger = logging.getLogger(__name__)


class FeedbackEngine:
    """Provides feedback for voice command execution.
    
    Supports audio (play a sound file), visual (notify-send),
    and status bar (text output) feedback channels.
    """
    
    def __init__(self, sound_dir: Path | None = None):
        self.sound_dir = sound_dir or Path.home() / ".config" / "fiona" / "sounds"
        self.sound_dir.mkdir(parents=True, exist_ok=True)
    
    def play_sound(self, sound_name: str = "ack") -> bool:
        """Play a sound file from the sounds directory.
        
        Supported formats: .wav, .mp3, .ogg
        Uses aplay (preferred), paplay, or ffplay.
        Returns True if sound was played, False otherwise.
        """
        for ext in [".wav", ".mp3", ".ogg"]:
            sound_path = self.sound_dir / f"{sound_name}{ext}"
            if sound_path.exists():
                try:
                    # Try aplay first (ALSA)
                    subprocess.run(
                        ["aplay", "-q", str(sound_path)],
                        capture_output=True, timeout=5
                    )
                    return True
                except (FileNotFoundError, subprocess.TimeoutExpired):
                    pass
                
                try:
                    # Try paplay (PulseAudio)
                    subprocess.run(
                        ["paplay", str(sound_path)],
                        capture_output=True, timeout=5
                    )
                    return True
                except (FileNotFoundError, subprocess.TimeoutExpired):
                    pass
        
        logger.debug("Sound '%s' not found in %s", sound_name, self.sound_dir)
        return False
    
    def notify(self, title: str, message: str, urgency: Literal["low", "normal", "critical"] = "normal") -> bool:
        """Send a desktop notification."""
        try:
            subprocess.run(
                ["notify-send", f"--urgency={urgency}", title, message],
                capture_output=True, timeout=5
            )
            return True
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return False
    
    def acknowledge(self) -> None:
        """Play acknowledgment sound and show notification."""
        self.play_sound("ack")
        self.notify("Fiona", "Listening...", urgency="low")
    
    def error(self, message: str) -> None:
        """Play error sound and show error notification."""
        self.play_sound("error")
        self.notify("Fiona Error", message, urgency="critical")
    
    def success(self, message: str) -> None:
        """Play success sound and show success notification."""
        self.play_sound("success")
        self.notify("Fiona", message, urgency="normal")
