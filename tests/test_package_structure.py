from __future__ import annotations

import importlib
import unittest


class PackageStructureTests(unittest.TestCase):
    def test_fiona_exposes_subsystems(self) -> None:
        import fiona

        self.assertIs(importlib.import_module("fiona.QuikTieper"), fiona.QuikTieper)
        self.assertIs(importlib.import_module("fiona.CamComs"), fiona.CamComs)
        self.assertIs(importlib.import_module("fiona.Vsee"), fiona.Vsee)
        self.assertIs(importlib.import_module("fiona.FionaAgent"), fiona.FionaAgent)
        self.assertIs(importlib.import_module("fiona.PhiConnect"), fiona.PhiConnect)
        self.assertIs(importlib.import_module("fiona.SeeOnDesk"), fiona.SeeOnDesk)

    def test_subsystems_are_directly_importable(self) -> None:
        import CamComs
        import FionaAgent
        import PhiConnect
        import QuikTieper
        import SeeOnDesk
        import Vsee

        self.assertTrue(hasattr(CamComs, "encrypt_message"))
        self.assertTrue(hasattr(CamComs, "CamComsHttpClient"))
        self.assertTrue(hasattr(QuikTieper, "AppLauncher"))
        self.assertIn("ChordListener", QuikTieper.__all__)
        self.assertTrue(hasattr(Vsee, "HologramModel"))
        self.assertTrue(hasattr(FionaAgent, "LMStudioClient"))
        self.assertTrue(hasattr(PhiConnect, "send_chat_message"))
        self.assertTrue(hasattr(SeeOnDesk, "desktop_snapshot"))


if __name__ == "__main__":
    unittest.main()
