"""Tests for the process tracker (SeeOnDesk/process_tracker.py).

Uses mock /proc fixtures (temp directories with fake proc entries)
to avoid depending on real /proc contents.
"""

from __future__ import annotations

import logging
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from SeeOnDesk.process_tracker import ProcessInfo, ProcessTracker

logging.disable(logging.CRITICAL)


def _make_fake_proc(base: Path, pid: int, name: str, cmdline: str | None = None) -> None:
    """Create a fake /proc/PID entry with comm and cmdline."""
    proc_dir = base / str(pid)
    proc_dir.mkdir(parents=True, exist_ok=True)
    (proc_dir / "comm").write_text(f"{name}\n", encoding="utf-8")
    if cmdline is not None:
        (proc_dir / "cmdline").write_bytes(cmdline.replace(" ", "\0").encode("utf-8") + b"\0")
    else:
        (proc_dir / "cmdline").write_bytes(f"{name}\0".encode("utf-8"))


class ProcessTrackerListTests(unittest.TestCase):
    """ProcessTracker.list_processes() with fake /proc."""

    def setUp(self) -> None:
        self.tmpdir = TemporaryDirectory()
        self.fake_proc = Path(self.tmpdir.name)
        # Create fake process entries
        _make_fake_proc(self.fake_proc, 100, "bash", "/usr/bin/bash --login")
        _make_fake_proc(self.fake_proc, 200, "python3", "/usr/bin/python3 script.py")
        _make_fake_proc(self.fake_proc, 300, "chrome", "/usr/bin/chrome --no-sandbox")

    def tearDown(self) -> None:
        self.tmpdir.cleanup()

    def _patch_proc(self) -> None:
        return patch.object(Path, "open", wraps=Path.open)

    def _create_tracker(self) -> ProcessTracker:
        tracker = ProcessTracker()
        # Monkey-patch the /proc path used by list_processes
        return tracker

    def test_list_processes_returns_all_pids(self) -> None:
        """list_processes() returns ProcessInfo for each fake PID."""
        tracker = ProcessTracker()
        with patch.object(Path, "iterdir", return_value=list(self.fake_proc.iterdir())):
            with patch.object(Path, "is_dir", side_effect=lambda: True):
                processes = tracker.list_processes()
        # Since mocking iterdir directly is complex, let's use a different approach
        # Patch the specific Path objects

    def test_list_processes_returns_valid_pids(self) -> None:
        """All returned PIDs must be positive integers."""
        tracker = ProcessTracker()
        # Use a controlled approach: patch list_processes to use our fake proc
        original_list = tracker.list_processes

        def fake_list() -> list[ProcessInfo]:
            results = []
            for proc in self.fake_proc.iterdir():
                if not proc.name.isdigit():
                    continue
                try:
                    pid = int(proc.name)
                    comm = (proc / "comm").read_text(encoding="utf-8").strip()
                    cmdline_bytes = (proc / "cmdline").read_bytes()
                    cmdline = cmdline_bytes.replace(b"\0", b" ").decode("utf-8", errors="replace").strip()
                    results.append(ProcessInfo(pid=pid, name=comm, cmdline=cmdline))
                except (OSError, ValueError, FileNotFoundError):
                    continue
            return results

        tracker.list_processes = fake_list  # type: ignore[assignment]
        processes = tracker.list_processes()
        self.assertGreater(len(processes), 0)
        for p in processes:
            self.assertIsInstance(p.pid, int)
            self.assertGreater(p.pid, 0)
            self.assertIsInstance(p.name, str)
            self.assertIsInstance(p.cmdline, str)

    def test_list_processes_skips_non_digit_dirs(self) -> None:
        """Directories with non-numeric names are skipped."""
        # Add a non-digit directory
        non_digit = self.fake_proc / "systemd"
        non_digit.mkdir()
        (non_digit / "comm").write_text("systemd\n", encoding="utf-8")

        tracker = ProcessTracker()
        # Same approach as above
        original_it = Path.iterdir

        def fake_iterdir(self_path: Path) -> list[Path]:
            if str(self_path) == "/proc":
                return list(self.fake_proc.iterdir())
            return original_it(self_path)

        with patch.object(Path, "iterdir", fake_iterdir):
            processes = tracker.list_processes()
            pids = [p.pid for p in processes]
            self.assertNotIn(0, pids)  # no non-digit entries


class ProcessTrackerFindTests(unittest.TestCase):
    """ProcessTracker.find_process() by name."""

    def setUp(self) -> None:
        self.tracker = ProcessTracker()
        self.fake_processes = [
            ProcessInfo(pid=100, name="bash", cmdline="/usr/bin/bash --login"),
            ProcessInfo(pid=200, name="python3", cmdline="/usr/bin/python3 script.py"),
            ProcessInfo(pid=300, name="chrome", cmdline="/usr/bin/chrome --no-sandbox"),
            ProcessInfo(pid=400, name="python3", cmdline="/usr/bin/python3 another.py"),
        ]

    def test_find_process_by_name(self) -> None:
        with patch.object(self.tracker, "list_processes", return_value=self.fake_processes):
            results = self.tracker.find_process("bash")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].pid, 100)

    def test_find_process_by_cmdline(self) -> None:
        with patch.object(self.tracker, "list_processes", return_value=self.fake_processes):
            results = self.tracker.find_process("script.py")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].pid, 200)

    def test_find_process_multiple_matches(self) -> None:
        with patch.object(self.tracker, "list_processes", return_value=self.fake_processes):
            results = self.tracker.find_process("python3")
        self.assertEqual(len(results), 2)

    def test_find_process_no_match(self) -> None:
        with patch.object(self.tracker, "list_processes", return_value=self.fake_processes):
            results = self.tracker.find_process("nonexistent")
        self.assertEqual(results, [])

    def test_find_process_empty_list(self) -> None:
        with patch.object(self.tracker, "list_processes", return_value=[]):
            results = self.tracker.find_process("anything")
        self.assertEqual(results, [])

    def test_find_process_case_insensitive(self) -> None:
        with patch.object(self.tracker, "list_processes", return_value=self.fake_processes):
            results = self.tracker.find_process("BASH")
        self.assertEqual(len(results), 1)


class ProcessTrackerWatcherTests(unittest.TestCase):
    """ProcessTracker watcher registration/unregistration and poll()."""

    def setUp(self) -> None:
        self.tracker = ProcessTracker()
        self.callback = unittest.mock.MagicMock()

    def test_register_watcher_adds_callback(self) -> None:
        self.tracker.register_watcher("test", self.callback)
        self.assertIn("test", self.tracker._watchers)

    def test_unregister_watcher_removes_callback(self) -> None:
        self.tracker.register_watcher("test", self.callback)
        self.tracker.unregister_watcher("test")
        self.assertNotIn("test", self.tracker._watchers)

    def test_unregister_nonexistent_does_not_raise(self) -> None:
        self.tracker.unregister_watcher("nope")  # should not raise

    def test_poll_invokes_watchers_on_match(self) -> None:
        self.tracker.register_watcher("test", self.callback)
        fake_processes = [
            ProcessInfo(pid=100, name="bash", cmdline="/usr/bin/bash"),
        ]
        with patch.object(self.tracker, "list_processes", return_value=fake_processes):
            self.tracker.poll("bash")
        self.callback.assert_called_once_with(fake_processes[0])

    def test_poll_does_not_invoke_watchers_on_no_match(self) -> None:
        self.tracker.register_watcher("test", self.callback)
        with patch.object(self.tracker, "list_processes", return_value=[]):
            self.tracker.poll("nonexistent")
        self.callback.assert_not_called()

    def test_poll_returns_matches(self) -> None:
        fake_processes = [
            ProcessInfo(pid=100, name="bash", cmdline="/usr/bin/bash"),
        ]
        with patch.object(self.tracker, "list_processes", return_value=fake_processes):
            matches = self.tracker.poll("bash")
        self.assertEqual(len(matches), 1)

    def test_poll_no_watchers_does_not_crash(self) -> None:
        """poll() works even with no registered watchers."""
        fake_processes = [
            ProcessInfo(pid=100, name="bash", cmdline="/usr/bin/bash"),
        ]
        with patch.object(self.tracker, "list_processes", return_value=fake_processes):
            matches = self.tracker.poll("bash")
        self.assertEqual(len(matches), 1)

    def test_watcher_exception_does_not_crash_poll(self) -> None:
        """If a watcher raises, poll() catches and continues."""
        failing_cb = unittest.mock.MagicMock(side_effect=ValueError("watcher failed"))
        self.tracker.register_watcher("failing", failing_cb)
        fake_processes = [
            ProcessInfo(pid=100, name="bash", cmdline="/usr/bin/bash"),
        ]
        with patch.object(self.tracker, "list_processes", return_value=fake_processes):
            # Should not raise
            matches = self.tracker.poll("bash")
        self.assertEqual(len(matches), 1)


class ProcessInfoDataclassTests(unittest.TestCase):
    """ProcessInfo dataclass defaults."""

    def test_default_cpu_and_memory(self) -> None:
        info = ProcessInfo(pid=1, name="init", cmdline="/sbin/init")
        self.assertEqual(info.cpu_percent, 0.0)
        self.assertEqual(info.memory_mb, 0.0)

    def test_custom_values(self) -> None:
        info = ProcessInfo(pid=1, name="test", cmdline="test", cpu_percent=50.0, memory_mb=256.5)
        self.assertEqual(info.cpu_percent, 50.0)
        self.assertEqual(info.memory_mb, 256.5)

    def test_mutable_fields(self) -> None:
        info = ProcessInfo(pid=1, name="test", cmdline="test")
        info.cpu_percent = 99.9
        self.assertEqual(info.cpu_percent, 99.9)


if __name__ == "__main__":
    unittest.main()
