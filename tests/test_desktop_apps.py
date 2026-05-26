from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from QuikTieper.bindings import parse_bindings
from QuikTieper.desktop_apps import clean_desktop_exec, desktop_app_from_file, discover_desktop_apps, merge_desktop_apps


class DesktopAppsTests(unittest.TestCase):
    def test_parses_desktop_application_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            desktop_file = Path(tmp) / "sample.desktop"
            desktop_file.write_text(
                "\n".join(
                    [
                        "[Desktop Entry]",
                        "Type=Application",
                        "Name=Sample App",
                        "Exec=sample-app --open %U",
                        "StartupWMClass=sample-window",
                    ]
                ),
                encoding="utf-8",
            )

            app = desktop_app_from_file(desktop_file)

            self.assertIsNotNone(app)
            assert app is not None
            self.assertEqual(app.name, "Sample App")
            self.assertEqual(app.command, "sample-app --open")
            self.assertEqual(app.window_match, "sample-window")

    def test_discovers_and_merges_desktop_apps_without_hotkeys(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            app_dir = Path(tmp)
            (app_dir / "one.desktop").write_text(
                "[Desktop Entry]\nType=Application\nName=One\nExec=one %f\n",
                encoding="utf-8",
            )
            (app_dir / "konsole.desktop").write_text(
                "[Desktop Entry]\nType=Application\nName=Konsole\nExec=konsole\n",
                encoding="utf-8",
            )
            (app_dir / "ktouch.desktop").write_text(
                "[Desktop Entry]\nType=Application\nName=KTouch\nExec=ktouch\n",
                encoding="utf-8",
            )
            (app_dir / "hidden.desktop").write_text(
                "[Desktop Entry]\nType=Application\nName=Hidden\nExec=hidden\nNoDisplay=true\n",
                encoding="utf-8",
            )
            (app_dir / "chess.desktop").write_text(
                "[Desktop Entry]\nType=Application\nName=Chess\nExec=chess\nCategories=Game;BoardGame;\n",
                encoding="utf-8",
            )
            (app_dir / "settings.desktop").write_text(
                "[Desktop Entry]\nType=Application\nName=Settings Helper\nExec=settings-helper\nCategories=Settings;\n",
                encoding="utf-8",
            )
            (app_dir / "monitor.desktop").write_text(
                "[Desktop Entry]\nType=Application\nName=System Monitor\nExec=system-monitor\nCategories=System;Monitor;\n",
                encoding="utf-8",
            )

            desktop_apps = discover_desktop_apps((app_dir,))
            merged, added = merge_desktop_apps({"apps": []}, desktop_apps)

            self.assertEqual([app.name for app in desktop_apps], ["Konsole", "One", "System Monitor"])
            self.assertEqual(added, 3)
            self.assertEqual(merged["apps"][0]["name"], "Konsole")
            self.assertEqual(merged["apps"][0]["launch"]["cmd"], "konsole")
            self.assertEqual(merged["apps"][0]["launch"]["keys"], [])
            self.assertEqual(parse_bindings(merged["apps"]), [])

    def test_can_include_all_k_apps(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            app_dir = Path(tmp)
            (app_dir / "ktouch.desktop").write_text(
                "[Desktop Entry]\nType=Application\nName=KTouch\nExec=ktouch\n",
                encoding="utf-8",
            )

            desktop_apps = discover_desktop_apps((app_dir,), skip_unapproved_k_apps=False)

            self.assertEqual([app.name for app in desktop_apps], ["KTouch"])

    def test_can_include_low_value_apps(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            app_dir = Path(tmp)
            (app_dir / "chess.desktop").write_text(
                "[Desktop Entry]\nType=Application\nName=Chess\nExec=chess\nCategories=Game;BoardGame;\n",
                encoding="utf-8",
            )

            desktop_apps = discover_desktop_apps((app_dir,), skip_low_value_apps=False)

            self.assertEqual([app.name for app in desktop_apps], ["Chess"])

    def test_clean_desktop_exec_removes_placeholders(self) -> None:
        self.assertEqual(clean_desktop_exec("app --new-window %U"), "app --new-window")


if __name__ == "__main__":
    unittest.main()
