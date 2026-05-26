from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import QuikTieper.gui as gui_module
from QuikTieper.gui import ConfigEditorApp


class FakeText:
    def __init__(self) -> None:
        self.value = ""

    def delete(self, _start: str, _end: str) -> None:
        self.value = ""

    def insert(self, _index: str, value: str) -> None:
        self.value = value

    def get(self, _start: str, _end: str) -> str:
        return self.value


class FakeStatus:
    def __init__(self) -> None:
        self.value = ""

    def get(self) -> str:
        return self.value

    def set(self, value: str) -> None:
        self.value = value


class GuiHandlerTests(unittest.TestCase):
    def test_camcoms_smoke_test_handler(self) -> None:
        app = object.__new__(ConfigEditorApp)
        app.cam_output_text = FakeText()
        app.status_var = FakeStatus()

        app.camcoms_smoke_test()

        self.assertEqual(app.cam_output_text.value, '{"keys":["alt","s"],"type":"press","version":1}')
        self.assertEqual(app.status_var.value, "CamComs smoke test passed")

    def test_debug_path_restriction_allows_only_project_debug_dirs(self) -> None:
        app = object.__new__(ConfigEditorApp)

        allowed = gui_module.PROJECT_ROOT / "CamComs" / "receiver.py"
        blocked_project_file = gui_module.PROJECT_ROOT / "README.md"
        blocked_outside_file = Path("/tmp/outside.py")

        self.assertTrue(app._debug_path_allowed(allowed.resolve()))
        self.assertFalse(app._debug_path_allowed(blocked_project_file.resolve()))
        self.assertFalse(app._debug_path_allowed(blocked_outside_file.resolve()))

    def test_debug_save_current_writes_allowed_text_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            allowed_dir = root / "tests"
            allowed_dir.mkdir()
            target = allowed_dir / "sample.py"
            target.write_text("old\n", encoding="utf-8")

            app = object.__new__(ConfigEditorApp)
            app.debug_path_var = FakeStatus()
            app.debug_path_var.set("tests/sample.py")
            app.debug_text = FakeText()
            app.debug_text.value = "new\n"
            app.status_var = FakeStatus()

            with (
                patch.object(gui_module, "PROJECT_ROOT", root),
                patch.object(gui_module, "DEBUG_ALLOWED_DIRS", (allowed_dir,)),
            ):
                app.debug_save_current()

            self.assertEqual(target.read_text(encoding="utf-8"), "new\n")
            self.assertEqual(app.status_var.value, "Saved tests/sample.py")


if __name__ == "__main__":
    unittest.main()
