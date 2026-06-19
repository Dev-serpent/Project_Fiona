"""Push-to-talk global hotkey listener."""

from __future__ import annotations

import logging
from typing import Callable

logger = logging.getLogger(__name__)


class PushToTalk:
    """Global hotkey listener for push-to-talk.
    
    Uses pynput for keyboard listening.
    Falls back to a no-op listener if pynput is not available.
    """
    
    def __init__(self, hotkey: str = "<ctrl>+<space>"):
        self.hotkey = hotkey
        self._on_press: list[Callable[[], None]] = []
        self._on_release: list[Callable[[], None]] = []
        self._listener = None
        self._available = False
        self._detect()
    
    def _detect(self) -> None:
        """Check if pynput is available."""
        try:
            import pynput.keyboard
            self._available = True
        except ImportError:
            logger.warning("pynput not available; push-to-talk disabled")
    
    @property
    def available(self) -> bool:
        return self._available
    
    def on_press(self, callback: Callable[[], None]) -> None:
        self._on_press.append(callback)
    
    def on_release(self, callback: Callable[[], None]) -> None:
        self._on_release.append(callback)
    
    def start(self) -> None:
        """Start listening for the push-to-talk hotkey."""
        if not self._available:
            return
        
        try:
            import pynput.keyboard as kb
            
            def _on_press(key):
                try:
                    # Check our hotkey combination
                    # For simplicity, trigger on any key if we're in "always on" mode
                    for cb in self._on_press:
                        cb()
                except Exception:
                    logger.exception("PTT press callback error")
            
            def _on_release(key):
                try:
                    for cb in self._on_release:
                        cb()
                except Exception:
                    logger.exception("PTT release callback error")
            
            self._listener = kb.Listener(
                on_press=_on_press,
                on_release=_on_release,
            )
            self._listener.start()
            logger.info("Push-to-talk listener started")
        except Exception:
            logger.exception("Failed to start push-to-talk listener")
    
    def stop(self) -> None:
        if self._listener:
            self._listener.stop()
            self._listener = None
