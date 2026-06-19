"""Wake word detection engine with pluggable backends."""

from __future__ import annotations

import logging
import time
import subprocess
from pathlib import Path
from typing import Callable

logger = logging.getLogger(__name__)

# Backend priorities: faster-whisper > whisper > vosk > pocketphinx
WAKE_WORD_DETECTORS: dict[str, str] = {
    "porcupine": "pvporcupine",  # Picovoice Porcupine (offline, fast)
    "snowboy": "snowboy",         # Snowboy hotword detection
    "precise": "mycroft_precise", # MyCroft Precise
}


class WakeWordEngine:
    """Simple wake word engine that attempts multiple detection backends.
    
    If no backend is installed, logs a warning and provides a manual
    trigger mechanism for push-to-talk.
    """
    
    def __init__(self, wake_word: str = "fiona"):
        self.wake_word = wake_word.lower()
        self._on_wake: list[Callable[[], None]] = []
        self._running = False
        self._backend = None
        self._detect_backend()
    
    def _detect_backend(self) -> str | None:
        """Detect available wake word detection library.
        
        Returns the backend name or None if none available.
        """
        # Try Porcupine first (best quality)
        try:
            import pvporcupine
            self._backend = "porcupine"
            logger.info("Using Porcupine wake word engine")
            return self._backend
        except ImportError:
            pass
        
        # Try snowboy
        try:
            import snowboy
            self._backend = "snowboy"
            logger.info("Using Snowboy wake word engine")
            return self._backend
        except ImportError:
            pass
        
        # Try MyCroft Precise
        try:
            import mycroft_precise
            self._backend = "precise"
            logger.info("Using MyCroft Precise wake word engine")
            return self._backend
        except ImportError:
            pass
        
        logger.warning("No wake word detection library found. Install pvporcupine or snowboy.")
        return None
    
    @property
    def available(self) -> bool:
        return self._backend is not None
    
    def on_wake(self, callback: Callable[[], None]) -> None:
        self._on_wake.append(callback)
    
    def trigger(self) -> None:
        """Manually trigger the wake event (for push-to-talk fallback)."""
        for cb in self._on_wake:
            try:
                cb()
            except Exception:
                logger.exception("Wake callback error")
    
    def start(self) -> None:
        """Start listening for wake word."""
        if not self._backend:
            logger.info("No wake word backend; use push-to-talk or manual trigger")
            return
        self._running = True
        logger.info("Wake word engine started (backend: %s)", self._backend)
    
    def stop(self) -> None:
        self._running = False
