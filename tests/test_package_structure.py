from __future__ import annotations

import importlib
import unittest


class PackageStructureTests(unittest.TestCase):
    def test_fiona_exposes_subsystems(self) -> None:
        import fiona

        self.assertIs(importlib.import_module("fiona.QuikTieper"), fiona.QuikTieper)
        self.assertIs(importlib.import_module("fiona.CamComs"), fiona.CamComs)
        self.assertIs(importlib.import_module("fiona.Vsee"), fiona.Vsee)
        self.assertIs(importlib.import_module("fiona.Agent"), fiona.Agent)
        self.assertIs(importlib.import_module("fiona.PhiConnect"), fiona.PhiConnect)
        self.assertIs(importlib.import_module("fiona.SeeOnDesk"), fiona.SeeOnDesk)
        self.assertIs(importlib.import_module("fiona.DataClient"), fiona.DataClient)
        self.assertIs(importlib.import_module("fiona.EyeControl"), fiona.EyeControl)
        self.assertIs(importlib.import_module("fiona.TerminalAssist"), fiona.TerminalAssist)

    def test_subsystems_are_directly_importable(self) -> None:
        import Agent
        import CamComs
        import DataClient
        import EyeControl
        import PhiConnect
        import QuikTieper
        import SeeOnDesk
        import TerminalAssist
        import Vsee

        self.assertTrue(hasattr(CamComs, "encrypt_message"))
        self.assertTrue(hasattr(CamComs, "CamComsHttpClient"))
        self.assertTrue(hasattr(QuikTieper, "AppLauncher"))
        self.assertIn("ChordListener", QuikTieper.__all__)
        self.assertTrue(hasattr(Vsee, "HologramModel"))
        self.assertTrue(hasattr(Agent, "LMStudioClient"))
        self.assertTrue(hasattr(DataClient, "mine_topic"))
        self.assertTrue(hasattr(EyeControl, "dependency_status"))
        self.assertTrue(hasattr(PhiConnect, "send_chat_message"))
        self.assertTrue(hasattr(SeeOnDesk, "desktop_snapshot"))
        self.assertTrue(hasattr(TerminalAssist, "build_dashboard"))


if __name__ == "__main__":
    unittest.main()
