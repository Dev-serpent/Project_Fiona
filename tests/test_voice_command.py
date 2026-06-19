"""Tests for FionaCore.voice — voice command parsing.

Extends coverage beyond what test_fiona_core.py provides for parse_voice_command.
"""

from __future__ import annotations

import unittest
import re

from FionaCore.voice import (
    VOICE_PATTERNS,
    VoiceCommand,
    parse_voice_command,
)


class VoiceCommandDataclassTests(unittest.TestCase):
    def test_to_dict(self):
        cmd = VoiceCommand(text="show host status", action="host.status", confidence=0.9)
        d = cmd.to_dict()
        self.assertEqual(d["text"], "show host status")
        self.assertEqual(d["action"], "host.status")
        self.assertEqual(d["confidence"], 0.9)

    def test_to_dict_types(self):
        cmd = VoiceCommand(text="t", action="a", confidence=0.5)
        d = cmd.to_dict()
        self.assertIsInstance(d["text"], str)
        self.assertIsInstance(d["action"], str)
        self.assertIsInstance(d["confidence"], float)


class ParseVoiceCommandTests(unittest.TestCase):
    def test_parse_show_host_status(self):
        cmd = parse_voice_command("show host status")
        self.assertIsNotNone(cmd)
        self.assertEqual(cmd.action, "host.status")
        self.assertEqual(cmd.text, "show host status")

    def test_parse_open_host_status(self):
        cmd = parse_voice_command("open host status")
        self.assertIsNotNone(cmd)
        self.assertEqual(cmd.action, "host.status")

    def test_parse_show_the_host_status(self):
        cmd = parse_voice_command("show the host status")
        self.assertIsNotNone(cmd)
        self.assertEqual(cmd.action, "host.status")

    def test_parse_fat_status(self):
        cmd = parse_voice_command("show fat")
        self.assertIsNotNone(cmd)
        self.assertEqual(cmd.action, "fat.status")

    def test_parse_terminal_dashboard(self):
        cmd = parse_voice_command("terminal dashboard")
        self.assertIsNotNone(cmd)
        self.assertEqual(cmd.action, "fat.status")

    def test_parse_camcoms_smoke(self):
        cmd = parse_voice_command("camcoms smoke")
        self.assertIsNotNone(cmd)
        self.assertEqual(cmd.action, "camcoms.smoke")

    def test_parse_camcoms_test(self):
        cmd = parse_voice_command("camcoms test")
        self.assertIsNotNone(cmd)
        self.assertEqual(cmd.action, "camcoms.smoke")

    def test_parse_encryption_test(self):
        cmd = parse_voice_command("encryption test")
        self.assertIsNotNone(cmd)
        self.assertEqual(cmd.action, "camcoms.smoke")

    def test_parse_show_camcoms_paths(self):
        cmd = parse_voice_command("show camcoms paths")
        self.assertIsNotNone(cmd)
        self.assertEqual(cmd.action, "camcoms.paths")

    def test_parse_open_camcoms_paths(self):
        cmd = parse_voice_command("open camcoms paths")
        self.assertIsNotNone(cmd)
        self.assertEqual(cmd.action, "camcoms.paths")

    def test_parse_show_bindings(self):
        cmd = parse_voice_command("show bindings")
        self.assertIsNotNone(cmd)
        self.assertEqual(cmd.action, "quiktieper.list")

    def test_parse_list_shortcuts(self):
        cmd = parse_voice_command("list shortcuts")
        self.assertIsNotNone(cmd)
        self.assertEqual(cmd.action, "quiktieper.list")

    def test_parse_desktop_status(self):
        cmd = parse_voice_command("desktop status")
        self.assertIsNotNone(cmd)
        self.assertEqual(cmd.action, "seeondesk.status")

    def test_parse_what_is_open(self):
        cmd = parse_voice_command("what is open")
        self.assertIsNotNone(cmd)
        self.assertEqual(cmd.action, "seeondesk.status")

    def test_parse_eye_control_status(self):
        cmd = parse_voice_command("eye control status")
        self.assertIsNotNone(cmd)
        self.assertEqual(cmd.action, "eyecontrol.status")

    def test_parse_eyecontrol_status(self):
        cmd = parse_voice_command("eyecontrol status")
        self.assertIsNotNone(cmd)
        self.assertEqual(cmd.action, "eyecontrol.status")

    def test_parse_agent_status(self):
        cmd = parse_voice_command("agent status")
        self.assertIsNotNone(cmd)
        self.assertEqual(cmd.action, "agent.status")

    def test_parse_lm_studio_status(self):
        cmd = parse_voice_command("lm studio status")
        self.assertIsNotNone(cmd)
        self.assertEqual(cmd.action, "agent.status")

    def test_parse_empty_string(self):
        cmd = parse_voice_command("")
        self.assertIsNone(cmd)

    def test_parse_whitespace_only(self):
        cmd = parse_voice_command("   ")
        self.assertIsNone(cmd)

    def test_parse_unknown_command(self):
        cmd = parse_voice_command("do something random")
        self.assertIsNone(cmd)

    def test_parse_partial_match_in_longer_text(self):
        """Pattern should match even when embedded in longer text."""
        cmd = parse_voice_command("can you please show host status now")
        self.assertIsNotNone(cmd)
        self.assertEqual(cmd.action, "host.status")

    def test_parse_case_insensitive(self):
        cmd = parse_voice_command("SHOW HOST STATUS")
        self.assertIsNotNone(cmd)
        self.assertEqual(cmd.action, "host.status")

    def test_parse_mixed_case(self):
        cmd = parse_voice_command("Show Host Status")
        self.assertIsNotNone(cmd)
        self.assertEqual(cmd.action, "host.status")

    def test_all_confidence_is_0_9(self):
        for text in ["show host status", "show fat", "open camcoms paths", "desktop status"]:
            with self.subTest(text=text):
                cmd = parse_voice_command(text)
                self.assertIsNotNone(cmd, msg=f"'{text}' should match")
                self.assertEqual(cmd.confidence, 0.9)

    def test_confidence_value(self):
        cmd = parse_voice_command("show host status")
        self.assertEqual(cmd.confidence, 0.9)


class VoicePatternsTests(unittest.TestCase):
    def test_all_patterns_are_compiled_regex(self):
        for pattern, _ in VOICE_PATTERNS:
            self.assertIsInstance(pattern, re.Pattern)

    def test_all_patterns_have_string_action(self):
        for _, action in VOICE_PATTERNS:
            self.assertIsInstance(action, str)
            self.assertIn(".", action)

    def test_no_overlapping_identical_patterns(self):
        patterns = [p.pattern for p, _ in VOICE_PATTERNS]
        self.assertEqual(len(patterns), len(set(patterns)))


if __name__ == "__main__":
    unittest.main()
