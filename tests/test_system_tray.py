"""Tests for the system tray icon (QuikTieper/system_tray.py).

Tests graceful degradation when pystray is missing, TrayState defaults,
_create_image() returns PIL Image, _build_menu() creates menu items,
and start/stop lifecycle behavior.
"""

from __future__ import annotations

import importlib
import logging
import sys
import types
import unittest
from unittest.mock import MagicMock, PropertyMock, patch

logging.disable(logging.CRITICAL)


def _reload_with_pystray() -> None:
    """Reload QuikTieper.system_tray with mocked pystray & PIL in sys.modules."""
    import QuikTieper.system_tray as mod

    # Ensure PIL is accessible (it's actually installed)
    import PIL
    from PIL import Image, ImageDraw  # noqa: F401

    # Mock pystray (not installed on this system)
    mock_pystray = types.ModuleType("pystray")
    mock_pystray.Menu = MagicMock()
    mock_pystray.MenuItem = MagicMock()
    mock_pystray.Menu.SEPARATOR = "---"
    mock_pystray.Icon = MagicMock()

    sys.modules["pystray"] = mock_pystray
    importlib.reload(mod)


def _reload_without_pystray() -> None:
    """Reload QuikTieper.system_tray without pystray (natural state)."""
    import QuikTieper.system_tray as mod
    # Remove pystray from sys.modules if present
    sys.modules.pop("pystray", None)
    importlib.reload(mod)


class SystemTrayAvailabilityTests(unittest.TestCase):
    """SystemTrayIcon.available — with/without pystray."""

    @classmethod
    def setUpClass(cls) -> None:
        _reload_without_pystray()

    def test_available_false_when_pystray_not_imported(self) -> None:
        from QuikTieper.system_tray import SystemTrayIcon
        icon = SystemTrayIcon()
        self.assertFalse(icon.available)

    def test_start_is_noop_when_unavailable(self) -> None:
        from QuikTieper.system_tray import SystemTrayIcon
        icon = SystemTrayIcon()
        icon.start()
        self.assertIsNone(icon._icon)


class TrayStateTests(unittest.TestCase):
    """TrayState dataclass defaults."""

    def setUp(self) -> None:
        from QuikTieper.system_tray import TrayState
        self.TrayState = TrayState

    def test_default_service_running_false(self) -> None:
        state = self.TrayState()
        self.assertFalse(state.service_running)

    def test_default_listening_false(self) -> None:
        state = self.TrayState()
        self.assertFalse(state.listening)

    def test_default_paired_devices_zero(self) -> None:
        state = self.TrayState()
        self.assertEqual(state.paired_devices, 0)

    def test_default_active_macro_none(self) -> None:
        state = self.TrayState()
        self.assertIsNone(state.active_macro)

    def test_mutable_fields(self) -> None:
        state = self.TrayState()
        state.service_running = True
        state.listening = True
        state.paired_devices = 3
        state.active_macro = "test_macro"
        self.assertTrue(state.service_running)
        self.assertTrue(state.listening)
        self.assertEqual(state.paired_devices, 3)
        self.assertEqual(state.active_macro, "test_macro")


class SystemTrayCreateImageTests(unittest.TestCase):
    """SystemTrayIcon._create_image() returns a PIL Image."""

    @classmethod
    def setUpClass(cls) -> None:
        _reload_with_pystray()

    def setUp(self) -> None:
        from QuikTieper.system_tray import SystemTrayIcon
        self.SystemTrayIcon = SystemTrayIcon

    def test_create_image_returns_image(self) -> None:
        """_create_image() returns a PIL Image."""
        icon = self.SystemTrayIcon()
        image = icon._create_image()
        from PIL import Image
        self.assertIsInstance(image, Image.Image)

    def test_create_image_green_when_running_and_listening(self) -> None:
        icon = self.SystemTrayIcon()
        icon._state.service_running = True
        icon._state.listening = True
        image = icon._create_image()
        self.assertIsNotNone(image)

    def test_create_image_yellow_when_running_not_listening(self) -> None:
        icon = self.SystemTrayIcon()
        icon._state.service_running = True
        icon._state.listening = False
        image = icon._create_image()
        self.assertIsNotNone(image)

    def test_create_image_red_when_not_running(self) -> None:
        icon = self.SystemTrayIcon()
        icon._state.service_running = False
        icon._state.listening = False
        image = icon._create_image()
        self.assertIsNotNone(image)


class SystemTrayCreateImageColorsTests(unittest.TestCase):
    """Verify the color logic in _create_image() by patching ImageDraw."""

    @classmethod
    def setUpClass(cls) -> None:
        _reload_with_pystray()

    def setUp(self) -> None:
        from QuikTieper.system_tray import SystemTrayIcon
        self.SystemTrayIcon = SystemTrayIcon
        # We will patch ImageDraw to intercept color values
        self.image_draw_patch = patch("QuikTieper.system_tray.ImageDraw")
        self.mock_ImageDraw = self.image_draw_patch.start()
        self.mock_draw = MagicMock()
        self.mock_ImageDraw.Draw.return_value = self.mock_draw

    def tearDown(self) -> None:
        self.image_draw_patch.stop()

    def test_green_when_running_and_listening(self) -> None:
        icon = self.SystemTrayIcon()
        icon._state.service_running = True
        icon._state.listening = True
        icon._create_image()
        color_arg = self.mock_draw.ellipse.call_args[1]["fill"]
        self.assertEqual(color_arg, (34, 197, 94, 255))

    def test_yellow_when_running_not_listening(self) -> None:
        icon = self.SystemTrayIcon()
        icon._state.service_running = True
        icon._state.listening = False
        icon._create_image()
        color_arg = self.mock_draw.ellipse.call_args[1]["fill"]
        self.assertEqual(color_arg, (234, 179, 8, 255))

    def test_red_when_not_running(self) -> None:
        icon = self.SystemTrayIcon()
        icon._state.service_running = False
        icon._state.listening = False
        icon._create_image()
        color_arg = self.mock_draw.ellipse.call_args[1]["fill"]
        self.assertEqual(color_arg, (239, 68, 68, 255))


class SystemTrayBuildMenuTests(unittest.TestCase):
    """SystemTrayIcon._build_menu() creates pystray.Menu items."""

    @classmethod
    def setUpClass(cls) -> None:
        _reload_with_pystray()

    def setUp(self) -> None:
        import QuikTieper.system_tray as mod
        # Mock pystray module attributes for menu building
        self.mock_MenuItem = MagicMock()
        self.mock_Menu = MagicMock()
        self.mock_Menu.SEPARATOR = "---"

        self.patch_menu = patch.object(mod.pystray, "Menu", self.mock_Menu)
        self.patch_item = patch.object(mod.pystray, "MenuItem", self.mock_MenuItem)
        self.patch_sep = patch.object(mod.pystray.Menu, "SEPARATOR", "---")
        self.patch_menu.start()
        self.patch_item.start()
        self.patch_sep.start()

        from QuikTieper.system_tray import SystemTrayIcon
        self.SystemTrayIcon = SystemTrayIcon

    def tearDown(self) -> None:
        self.patch_menu.stop()
        self.patch_item.stop()
        self.patch_sep.stop()

    def test_build_menu_returns_menu(self) -> None:
        icon = self.SystemTrayIcon()
        menu = icon._build_menu()
        self.assertIsNotNone(menu)

    def test_build_menu_includes_show_option(self) -> None:
        icon = self.SystemTrayIcon()
        icon._build_menu()
        show_calls = [
            call for call in self.mock_MenuItem.call_args_list
            if "Show Fiona" in str(call)
        ]
        self.assertGreaterEqual(len(show_calls), 1)

    def test_build_menu_includes_quit_option(self) -> None:
        icon = self.SystemTrayIcon()
        icon._build_menu()
        quit_calls = [
            call for call in self.mock_MenuItem.call_args_list
            if "Quit" in str(call)
        ]
        self.assertGreaterEqual(len(quit_calls), 1)

    def test_build_menu_shows_paired_devices(self) -> None:
        icon = self.SystemTrayIcon()
        icon._state.paired_devices = 2
        icon._build_menu()
        paired_calls = [
            call for call in self.mock_MenuItem.call_args_list
            if "Paired: 2" in str(call)
        ]
        self.assertGreaterEqual(len(paired_calls), 1)

    def test_build_menu_hides_paired_devices_when_zero(self) -> None:
        icon = self.SystemTrayIcon()
        icon._state.paired_devices = 0
        icon._build_menu()
        zero_paired_calls = [
            call for call in self.mock_MenuItem.call_args_list
            if "Paired: 0" in str(call)
        ]
        self.assertEqual(len(zero_paired_calls), 0)

    def test_build_menu_shows_active_macro(self) -> None:
        icon = self.SystemTrayIcon()
        icon._state.active_macro = "my_macro"
        icon._build_menu()
        macro_calls = [
            call for call in self.mock_MenuItem.call_args_list
            if "Macro: my_macro" in str(call)
        ]
        self.assertGreaterEqual(len(macro_calls), 1)

    def test_build_menu_hides_active_macro_when_none(self) -> None:
        icon = self.SystemTrayIcon()
        icon._state.active_macro = None
        icon._build_menu()
        none_calls = [
            call for call in self.mock_MenuItem.call_args_list
            if "Macro: None" in str(call)
        ]
        self.assertEqual(len(none_calls), 0)


class SystemTrayLifecycleTests(unittest.TestCase):
    """SystemTrayIcon start/stop lifecycle with mocked pystray."""

    @classmethod
    def setUpClass(cls) -> None:
        _reload_with_pystray()

    def setUp(self) -> None:
        import QuikTieper.system_tray as mod
        self.mock_icon_instance = MagicMock()
        # Patch pystray.Icon
        self.icon_patch = patch.object(mod.pystray, "Icon", return_value=self.mock_icon_instance)
        self.icon_patch.start()

        from QuikTieper.system_tray import SystemTrayIcon
        from QuikTieper.system_tray import TrayState
        self.SystemTrayIcon = SystemTrayIcon
        self.TrayState = TrayState

    def tearDown(self) -> None:
        self.icon_patch.stop()

    def test_start_creates_icon_and_runs(self) -> None:
        icon = self.SystemTrayIcon()
        icon.start()
        self.assertIsNotNone(icon._icon)
        self.mock_icon_instance.run.assert_called_once()

    def test_double_start_does_not_create_second_icon(self) -> None:
        icon = self.SystemTrayIcon()
        icon.start()
        icon.start()  # Second call should be no-op
        self.mock_icon_instance.run.assert_called_once()

    def test_stop_stops_icon(self) -> None:
        icon = self.SystemTrayIcon()
        icon.start()
        icon.stop()
        self.mock_icon_instance.stop.assert_called_once()
        self.assertIsNone(icon._icon)

    def test_stop_when_not_started(self) -> None:
        icon = self.SystemTrayIcon()
        icon.stop()  # Should not raise

    def test_update_with_kwargs_updates_state(self) -> None:
        icon = self.SystemTrayIcon()
        icon._icon = self.mock_icon_instance
        icon.update(listening=True)
        self.assertTrue(icon._state.listening)

    def test_update_with_state_object(self) -> None:
        icon = self.SystemTrayIcon()
        new_state = self.TrayState(service_running=True, listening=True, paired_devices=1)
        icon._icon = self.mock_icon_instance
        icon.update(state=new_state)
        self.assertTrue(icon._state.service_running)
        self.assertTrue(icon._state.listening)
        self.assertEqual(icon._state.paired_devices, 1)

    def test_update_unknown_kwargs_ignored(self) -> None:
        icon = self.SystemTrayIcon()
        icon._icon = self.mock_icon_instance
        icon.update(unknown_field="value")  # should not raise


if __name__ == "__main__":
    unittest.main()
