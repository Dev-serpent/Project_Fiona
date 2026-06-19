"""System tray icon with state indicators and quick action menus."""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass
from typing import Callable

logger = logging.getLogger(__name__)

# Try to import pystray; if not available, degrade gracefully
try:
    import pystray
    from PIL import Image, ImageDraw

    _HAS_PYSTRAY = True
except ImportError:
    _HAS_PYSTRAY = False
    logger.warning(
        "pystray not available; system tray disabled. Install with: pip install pystray Pillow"
    )


@dataclass
class TrayState:
    """Current state indicators shown in the tray icon."""

    service_running: bool = False
    listening: bool = False
    paired_devices: int = 0
    active_macro: str | None = None


class SystemTrayIcon:
    """System tray icon for Fiona.

    Provides a status icon with color-coded state and right-click menu.
    Falls back to a no-op if pystray is not installed.
    """

    def __init__(
        self,
        on_show: Callable | None = None,
        on_quit: Callable | None = None,
    ) -> None:
        self._on_show = on_show
        self._on_quit = on_quit
        self._icon: pystray.Icon | None = None
        self._thread: threading.Thread | None = None
        self._state = TrayState()
        self._available = _HAS_PYSTRAY

    @property
    def available(self) -> bool:
        """Whether pystray is available and the icon can run."""
        return self._available

    def _create_image(self) -> Image.Image:
        """Create a simple colored circle icon.

        Color codes:
        - Green: service running and listening
        - Yellow: service running but not listening
        - Red: service not running
        - Gray: unknown state
        """
        size = 64
        image = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(image)

        if self._state.service_running and self._state.listening:
            color = (34, 197, 94, 255)  # green
        elif self._state.service_running:
            color = (234, 179, 8, 255)  # yellow
        elif not self._state.service_running:
            color = (239, 68, 68, 255)  # red
        else:
            color = (156, 163, 175, 255)  # gray

        # Draw a filled circle with "F" letter
        draw.ellipse([8, 8, 56, 56], fill=color)
        draw.text((22, 16), "F", fill=(255, 255, 255, 255), font_size=28)

        return image

    def _build_menu(self) -> pystray.Menu:
        """Build the right-click menu based on current state."""
        menu_items = []

        # Show/Hide main window
        menu_items.append(
            pystray.MenuItem(
                "Show Fiona",
                self._on_show or (lambda: None),
                default=True,
            )
        )
        menu_items.append(pystray.Menu.SEPARATOR)

        # Status indicators (read-only)
        status = self._state
        menu_items.append(
            pystray.MenuItem(
                f"Service: {'Running' if status.service_running else 'Stopped'}",
                None,
                enabled=False,
            )
        )
        menu_items.append(
            pystray.MenuItem(
                f"Voice: {'Listening' if status.listening else 'Idle'}",
                None,
                enabled=False,
            )
        )
        if status.paired_devices > 0:
            menu_items.append(
                pystray.MenuItem(
                    f"Paired: {status.paired_devices} device(s)",
                    None,
                    enabled=False,
                )
            )
        if status.active_macro:
            menu_items.append(
                pystray.MenuItem(
                    f"Macro: {status.active_macro}",
                    None,
                    enabled=False,
                )
            )

        menu_items.append(pystray.Menu.SEPARATOR)
        menu_items.append(
            pystray.MenuItem("Quit Fiona", self._on_quit or (lambda: None))
        )

        return pystray.Menu(*menu_items)

    def start(self) -> None:
        """Start the system tray icon in a background thread."""
        if not self._available:
            logger.info("System tray not available")
            return

        if self._icon is not None:
            return  # Already running

        self._icon = pystray.Icon(
            "fiona",
            self._create_image(),
            "Fiona Workstation Assistant",
            menu=self._build_menu(),
        )
        self._thread = threading.Thread(target=self._icon.run, daemon=True)
        self._thread.start()
        logger.info("System tray icon started")

    def stop(self) -> None:
        """Stop the system tray icon."""
        if self._icon:
            self._icon.stop()
            self._icon = None
        logger.info("System tray icon stopped")

    def update(self, state: TrayState | None = None, **kwargs) -> None:
        """Update the tray icon state and refresh menu/image.

        Can be called with a TrayState object or keyword arguments.
        """
        if state:
            self._state = state
        else:
            for key, value in kwargs.items():
                if hasattr(self._state, key):
                    setattr(self._state, key, value)

        if self._icon:
            self._icon.icon = self._create_image()
            self._icon.menu = self._build_menu()
