"""Tests for the Voice module (WakeWordEngine, PushToTalk, FeedbackEngine).

All tests mock external dependencies — no real audio hardware, pynput, or
pvporcupine required.
"""

from __future__ import annotations

import logging
import subprocess
import sys
import types
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import MagicMock, patch

from Voice.wake_word import WakeWordEngine
from Voice.push_to_talk import PushToTalk
from Voice.feedback_engine import FeedbackEngine

logging.disable(logging.CRITICAL)


# ──────────────────────────────────────────────────────────────────────────
# WakeWordEngine
# ──────────────────────────────────────────────────────────────────────────


class WakeWordEngineDetectionTests(unittest.TestCase):
    """WakeWordEngine — backend detection and availability."""

    def test_detects_no_backend_available(self) -> None:
        """When no wake word library is installed, available=False."""
        with patch.dict("sys.modules", {"pvporcupine": None, "snowboy": None, "mycroft_precise": None}):
            with patch("Voice.wake_word.logger") as mock_log:
                engine = WakeWordEngine()
                self.assertFalse(engine.available)
                mock_log.warning.assert_called_once()

    def test_detects_porcupine_backend(self) -> None:
        """When pvporcupine is importable, porcupine backend is selected."""
        mock_porcupine = MagicMock()
        with patch.dict("sys.modules", {"pvporcupine": mock_porcupine}):
            engine = WakeWordEngine()
            self.assertTrue(engine.available)
            self.assertEqual(engine._backend, "porcupine")

    def test_detects_snowboy_fallback(self) -> None:
        """When pvporcupine is missing but snowboy is available."""
        with patch.dict("sys.modules", {"pvporcupine": None, "snowboy": MagicMock()}):
            engine = WakeWordEngine()
            self.assertTrue(engine.available)
            self.assertEqual(engine._backend, "snowboy")

    def test_detects_precise_fallback(self) -> None:
        """When pvporcupine and snowboy are missing, precise backend is used."""
        with patch.dict("sys.modules", {"pvporcupine": None, "snowboy": None, "mycroft_precise": MagicMock()}):
            engine = WakeWordEngine()
            self.assertTrue(engine.available)
            self.assertEqual(engine._backend, "precise")

    def test_normalizes_wake_word_to_lowercase(self) -> None:
        engine = WakeWordEngine(wake_word="FIONA")
        self.assertEqual(engine.wake_word, "fiona")


class WakeWordEngineLifecycleTests(unittest.TestCase):
    """WakeWordEngine — start/stop lifecycle and callbacks."""

    def setUp(self) -> None:
        with patch.dict("sys.modules", {"pvporcupine": MagicMock()}):
            self.engine = WakeWordEngine()

    def test_start_sets_running(self) -> None:
        self.engine.start()
        self.assertTrue(self.engine._running)

    def test_stop_clears_running(self) -> None:
        self.engine.start()
        self.engine.stop()
        self.assertFalse(self.engine._running)

    def test_start_without_backend_logs_info(self) -> None:
        engine = WakeWordEngine.__new__(WakeWordEngine)
        engine.wake_word = "fiona"
        engine._on_wake = []
        engine._running = False
        engine._backend = None
        with patch("Voice.wake_word.logger") as mock_log:
            engine.start()
            self.assertFalse(engine._running)
            mock_log.info.assert_called_once()

    def test_trigger_calls_callbacks(self) -> None:
        callback = MagicMock()
        self.engine.on_wake(callback)
        self.engine.trigger()
        callback.assert_called_once()

    def test_trigger_calls_multiple_callbacks(self) -> None:
        cb1 = MagicMock()
        cb2 = MagicMock()
        self.engine.on_wake(cb1)
        self.engine.on_wake(cb2)
        self.engine.trigger()
        cb1.assert_called_once()
        cb2.assert_called_once()

    def test_trigger_no_callbacks_does_not_crash(self) -> None:
        self.engine.trigger()  # Should not raise

    def test_callback_exception_does_not_crash_trigger(self) -> None:
        failing_cb = MagicMock(side_effect=ValueError("cb failed"))
        self.engine.on_wake(failing_cb)
        # Should not raise
        self.engine.trigger()
        failing_cb.assert_called_once()


# ──────────────────────────────────────────────────────────────────────────
# PushToTalk
# ──────────────────────────────────────────────────────────────────────────


def _make_mock_pynput() -> tuple[types.ModuleType, types.ModuleType, MagicMock]:
    """Create proper mock modules for pynput and pynput.keyboard.

    Returns (mock_pynput, mock_keyboard, mock_listener).
    """
    mock_listener = MagicMock()
    mock_keyboard = types.ModuleType("pynput.keyboard")
    mock_keyboard.Listener = MagicMock(return_value=mock_listener)

    mock_pynput = types.ModuleType("pynput")
    mock_pynput.keyboard = mock_keyboard

    return mock_pynput, mock_keyboard, mock_listener


def _install_mock_pynput() -> tuple[types.ModuleType, types.ModuleType, MagicMock]:
    """Install mock pynput modules in sys.modules.

    Returns (mock_pynput, mock_keyboard, mock_listener).
    """
    mock_pynput, mock_keyboard, mock_listener = _make_mock_pynput()
    sys.modules["pynput"] = mock_pynput
    sys.modules["pynput.keyboard"] = mock_keyboard
    return mock_pynput, mock_keyboard, mock_listener


class PushToTalkDetectionTests(unittest.TestCase):
    """PushToTalk — pynput detection and availability."""

    def test_available_when_pynput_installed(self) -> None:
        """When pynput IS available, simulate by directly setting available flag."""
        from Voice.push_to_talk import PushToTalk
        ptt = PushToTalk()
        ptt._available = True
        self.assertTrue(ptt.available)

    def test_unavailable_when_pynput_missing(self) -> None:
        """When pynput is unavailable, available=False (simulated)."""
        from Voice.push_to_talk import PushToTalk
        ptt = PushToTalk()
        ptt._available = False  # Simulate pynput not available
        self.assertFalse(ptt.available)

    def test_start_unavailable_does_nothing(self) -> None:
        """start() is no-op when pynput unavailable (simulated)."""
        from Voice.push_to_talk import PushToTalk
        ptt = PushToTalk()
        ptt._available = False  # Simulate unavailable
        self.assertFalse(ptt.available)
        ptt.start()  # Should not raise
        self.assertIsNone(ptt._listener)

    def test_stop_when_not_started(self) -> None:
        from Voice.push_to_talk import PushToTalk
        ptt = PushToTalk()
        ptt.stop()  # Should not raise

    def test_on_press_registers_callback(self) -> None:
        from Voice.push_to_talk import PushToTalk
        ptt = PushToTalk()
        cb = MagicMock()
        ptt.on_press(cb)
        self.assertIn(cb, ptt._on_press)

    def test_on_release_registers_callback(self) -> None:
        from Voice.push_to_talk import PushToTalk
        ptt = PushToTalk()
        cb = MagicMock()
        ptt.on_release(cb)
        self.assertIn(cb, ptt._on_release)


class PushToTalkLifecycleTests(unittest.TestCase):
    """PushToTalk — lifecycle tests with sys.modules injection.

    Since pynput may not be installed, we inject mock modules into
    sys.modules so the local import inside start() resolves correctly.
    These tests do NOT reload Voice.push_to_talk — they only manipulate
    sys.modules temporarily.
    """

    def setUp(self) -> None:
        from Voice.push_to_talk import PushToTalk
        self.ptt = PushToTalk()
        # Simulate pynput availability (bypass _detect())
        self.ptt._available = True

        self.mock_listener = MagicMock()

        # Create proper mock modules for pynput and pynput.keyboard
        self.mock_keyboard = types.ModuleType("pynput.keyboard")
        self.mock_keyboard.Listener = MagicMock(return_value=self.mock_listener)
        self.mock_pynput = types.ModuleType("pynput")
        self.mock_pynput.keyboard = self.mock_keyboard

        # Save originals
        self._old_pynput = sys.modules.get("pynput")
        self._old_keyboard = sys.modules.get("pynput.keyboard")

        # Install mocks
        sys.modules["pynput"] = self.mock_pynput
        sys.modules["pynput.keyboard"] = self.mock_keyboard

    def tearDown(self) -> None:
        # Restore sys.modules
        if self._old_pynput is None:
            sys.modules.pop("pynput", None)
        else:
            sys.modules["pynput"] = self._old_pynput
        if self._old_keyboard is None:
            sys.modules.pop("pynput.keyboard", None)
        else:
            sys.modules["pynput.keyboard"] = self._old_keyboard

    def test_start_creates_listener(self) -> None:
        """With mocked pynput in sys.modules, start() creates a Listener."""
        self.ptt.start()
        self.assertIsNotNone(self.ptt._listener)
        self.mock_listener.start.assert_called_once()

    def test_stop_stops_listener(self) -> None:
        """stop() stops the listener and clears the reference."""
        self.ptt.start()
        self.ptt.stop()
        self.mock_listener.stop.assert_called_once()
        self.assertIsNone(self.ptt._listener)


# ──────────────────────────────────────────────────────────────────────────
# FeedbackEngine
# ──────────────────────────────────────────────────────────────────────────


class FeedbackEngineSoundTests(unittest.TestCase):
    """FeedbackEngine.play_sound() — missing sounds, player fallback."""

    def setUp(self) -> None:
        self.tmpdir = TemporaryDirectory()
        self.sound_dir = Path(self.tmpdir.name)
        self.engine = FeedbackEngine(sound_dir=self.sound_dir)

    def tearDown(self) -> None:
        self.tmpdir.cleanup()

    def test_play_sound_returns_false_for_missing_sound(self) -> None:
        result = self.engine.play_sound("nonexistent")
        self.assertFalse(result)

    def test_play_sound_uses_aplay_when_available(self) -> None:
        wav = self.sound_dir / "ack.wav"
        wav.write_text("fake wav content", encoding="utf-8")
        mock_run = MagicMock()
        mock_run.return_value = subprocess.CompletedProcess(
            args=["aplay"], returncode=0, stdout="", stderr="",
        )
        with patch("subprocess.run", mock_run):
            result = self.engine.play_sound("ack")
        self.assertTrue(result)

    def test_play_sound_tries_paplay_when_aplay_missing(self) -> None:
        wav = self.sound_dir / "ack.wav"
        wav.write_text("fake wav content", encoding="utf-8")
        calls = []

        def side_effect(*args, **kwargs):
            cmd = args[0] if args else kwargs.get("args", [])
            calls.append(cmd)
            if cmd[0] == "aplay":
                raise FileNotFoundError("aplay not found")
            if cmd[0] == "paplay":
                return subprocess.CompletedProcess(
                    args=["paplay"], returncode=0, stdout="", stderr="",
                )
            raise ValueError(f"unexpected: {cmd}")

        with patch("subprocess.run", side_effect=side_effect):
            result = self.engine.play_sound("ack")
        self.assertTrue(result)

    def test_play_sound_tries_extensions_in_order(self) -> None:
        """Should try .wav, .mp3, .ogg in order."""
        ogg = self.sound_dir / "test.ogg"
        ogg.write_text("fake ogg", encoding="utf-8")
        mock_run = MagicMock()
        mock_run.return_value = subprocess.CompletedProcess(
            args=["aplay"], returncode=0, stdout="", stderr="",
        )
        with patch("subprocess.run", mock_run):
            result = self.engine.play_sound("test")
        self.assertTrue(result)
        # aplay was called for .ogg
        cmd = mock_run.call_args[0][0]
        self.assertEqual(cmd[2], str(ogg))

    def test_play_sound_handles_timeout(self) -> None:
        wav = self.sound_dir / "ack.wav"
        wav.write_text("fake", encoding="utf-8")

        def side_effect(*args, **kwargs):
            raise subprocess.TimeoutExpired(cmd="aplay", timeout=5)

        with patch("subprocess.run", side_effect=side_effect):
            result = self.engine.play_sound("ack")
        self.assertFalse(result)


class FeedbackEngineNotifyTests(unittest.TestCase):
    """FeedbackEngine.notify() — notify-send dependency."""

    def setUp(self) -> None:
        self.tmpdir = TemporaryDirectory()
        self.engine = FeedbackEngine(sound_dir=Path(self.tmpdir.name))

    def tearDown(self) -> None:
        self.tmpdir.cleanup()

    def test_notify_returns_false_when_notify_send_missing(self) -> None:
        with patch("subprocess.run", side_effect=FileNotFoundError("notify-send not found")):
            result = self.engine.notify("Title", "Message")
        self.assertFalse(result)

    def test_notify_returns_true_when_success(self) -> None:
        mock_run = MagicMock()
        mock_run.return_value = subprocess.CompletedProcess(
            args=["notify-send"], returncode=0, stdout="", stderr="",
        )
        with patch("subprocess.run", mock_run):
            result = self.engine.notify("Title", "Message")
        self.assertTrue(result)

    def test_notify_handles_timeout(self) -> None:
        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired("notify-send", timeout=5)):
            result = self.engine.notify("Title", "Message")
        self.assertFalse(result)

    def test_notify_sets_urgency(self) -> None:
        mock_run = MagicMock()
        with patch("subprocess.run", mock_run):
            self.engine.notify("T", "M", urgency="critical")
        args = mock_run.call_args[0][0]
        self.assertIn("--urgency=critical", args)

    def test_notify_default_urgency(self) -> None:
        mock_run = MagicMock()
        with patch("subprocess.run", mock_run):
            self.engine.notify("T", "M")
        args = mock_run.call_args[0][0]
        self.assertIn("--urgency=normal", args)


class FeedbackEngineCompositeTests(unittest.TestCase):
    """FeedbackEngine.acknowledge(), error(), success()."""

    def setUp(self) -> None:
        self.tmpdir = TemporaryDirectory()
        self.sound_dir = Path(self.tmpdir.name)
        self.engine = FeedbackEngine(sound_dir=self.sound_dir)

    def tearDown(self) -> None:
        self.tmpdir.cleanup()

    def test_acknowledge_plays_ack_sound(self) -> None:
        with patch.object(self.engine, "play_sound") as mock_ps:
            with patch.object(self.engine, "notify"):
                self.engine.acknowledge()
        mock_ps.assert_called_once_with("ack")

    def test_acknowledge_sends_notification(self) -> None:
        with patch.object(self.engine, "play_sound"):
            with patch.object(self.engine, "notify") as mock_notify:
                self.engine.acknowledge()
        mock_notify.assert_called_once_with("Fiona", "Listening...", urgency="low")

    def test_error_plays_error_sound(self) -> None:
        with patch.object(self.engine, "play_sound") as mock_ps:
            with patch.object(self.engine, "notify"):
                self.engine.error("Something went wrong")
        mock_ps.assert_called_once_with("error")

    def test_error_sends_critical_notification(self) -> None:
        with patch.object(self.engine, "play_sound"):
            with patch.object(self.engine, "notify") as mock_notify:
                self.engine.error("Error msg")
        mock_notify.assert_called_once_with("Fiona Error", "Error msg", urgency="critical")

    def test_success_plays_success_sound(self) -> None:
        with patch.object(self.engine, "play_sound") as mock_ps:
            with patch.object(self.engine, "notify"):
                self.engine.success("Done!")
        mock_ps.assert_called_once_with("success")

    def test_success_sends_notification(self) -> None:
        with patch.object(self.engine, "play_sound"):
            with patch.object(self.engine, "notify") as mock_notify:
                self.engine.success("Completed")
        mock_notify.assert_called_once_with("Fiona", "Completed", urgency="normal")


if __name__ == "__main__":
    unittest.main()
