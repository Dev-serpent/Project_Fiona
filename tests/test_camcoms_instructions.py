from __future__ import annotations

import unittest

from CamComs import (
    CamComsInstructionError,
    instruction_from_text,
    instruction_to_text,
    press_instruction,
    private_key_path,
    public_key_path,
)


class CamComsInstructionTests(unittest.TestCase):
    def test_press_instruction_round_trip(self) -> None:
        instruction = press_instruction(["alt", "s"])
        text = instruction_to_text(instruction)

        self.assertEqual(text, '{"keys":["alt","s"],"type":"press","version":1}')
        self.assertEqual(instruction_from_text(text), instruction)

    def test_rejects_plain_string_instruction(self) -> None:
        with self.assertRaises(CamComsInstructionError):
            instruction_from_text("press:alt+s")

    def test_macro_instruction_round_trip(self) -> None:
        instruction = {
            "version": 1,
            "type": "macro",
            "steps": [
                {"version": 1, "type": "press", "keys": ["alt", "s"]},
                {"version": 1, "type": "text", "value": "ready"},
            ],
        }

        self.assertEqual(instruction_from_text(instruction_to_text(instruction)), instruction)

    def test_rejects_empty_macro(self) -> None:
        with self.assertRaises(CamComsInstructionError):
            instruction_from_text('{"version":1,"type":"macro","steps":[]}')

    def test_default_key_paths_are_visible(self) -> None:
        self.assertEqual(private_key_path("host").name, "host.private.json")
        self.assertEqual(public_key_path("esp32").name, "esp32.public.json")


if __name__ == "__main__":
    unittest.main()
