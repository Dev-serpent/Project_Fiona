"""Tests for FionaCore.speech — spoken response engine."""

from __future__ import annotations

import subprocess
import unittest
from unittest.mock import patch

from FionaCore.speech import speak


class SpeakTests(unittest.TestCase):
    def test_dummy_mode_returns_true(self):
        """dummy mode always returns True without calling external commands."""
        self.assertTrue(speak("hello", mode="dummy"))

    def test_dummy_mode_default_text(self):
        self.assertTrue(speak("anything", mode="dummy"))

    @patch("FionaCore.speech.shutil.which")
    def test_returns_false_when_spd_say_not_available(self, mock_which):
        mock_which.return_value = None
        result = speak("hello", mode="speech-dispatcher")
        self.assertFalse(result)

    @patch("FionaCore.speech.shutil.which")
    @patch("FionaCore.speech.subprocess.run")
    def test_returns_true_on_success(self, mock_run, mock_which):
        mock_which.return_value = "/usr/bin/spd-say"
        mock_run.return_value = subprocess.CompletedProcess(
            ["spd-say", "hello"], returncode=0, stdout="", stderr=""
        )
        result = speak("hello", mode="speech-dispatcher")
        self.assertTrue(result)
        mock_run.assert_called_once_with(
            ["/usr/bin/spd-say", "hello"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=True,
        )

    @patch("FionaCore.speech.shutil.which")
    @patch("FionaCore.speech.subprocess.run")
    def test_returns_false_on_subprocess_error(self, mock_run, mock_which):
        mock_which.return_value = "/usr/bin/spd-say"
        mock_run.side_effect = subprocess.SubprocessError("spd-say failed")
        result = speak("hello", mode="speech-dispatcher")
        self.assertFalse(result)

    @patch("FionaCore.speech.shutil.which")
    @patch("FionaCore.speech.subprocess.run")
    def test_file_not_found_propagates(self, mock_run, mock_which):
        """FileNotFoundError is not a SubprocessError, so it propagates."""
        mock_which.return_value = "/usr/bin/spd-say"
        mock_run.side_effect = FileNotFoundError("spd-say not found")
        with self.assertRaises(FileNotFoundError):
            speak("hello")

    @patch("FionaCore.speech.shutil.which")
    def test_default_mode_is_speech_dispatcher(self, mock_which):
        """Default mode is 'speech-dispatcher'; which() is called."""
        mock_which.return_value = None
        speak("hello")
        mock_which.assert_called_once_with("spd-say")

    def test_speaks_empty_string_in_dummy_mode(self):
        self.assertTrue(speak("", mode="dummy"))

    def test_speaks_multiline_text_in_dummy_mode(self):
        self.assertTrue(speak("line1\nline2", mode="dummy"))

    @patch("FionaCore.speech.shutil.which")
    @patch("FionaCore.speech.subprocess.run")
    def test_passes_text_verbatim_to_spd_say(self, mock_run, mock_which):
        text = "System status is normal"
        mock_which.return_value = "/usr/bin/spd-say"
        mock_run.return_value = subprocess.CompletedProcess(
            ["spd-say", text], returncode=0, stdout="", stderr=""
        )
        speak(text, mode="speech-dispatcher")
        mock_run.assert_called_once_with(
            ["/usr/bin/spd-say", text],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=True,
        )


if __name__ == "__main__":
    unittest.main()
