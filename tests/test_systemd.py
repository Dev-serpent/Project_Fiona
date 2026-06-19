"""Tests for CamComs.systemd — systemd service unit management."""

from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

from CamComs.systemd import (
    DEFAULT_SERVICE_NAME,
    DEFAULT_SYSTEMD_USER_DIR,
    install_host_service_unit,
    read_host_service_logs,
    render_host_service_unit,
    run_user_service_command,
    service_unit_path,
)


class RenderHostServiceUnitTests(unittest.TestCase):
    def test_renders_unit_file_content(self):
        unit = render_host_service_unit()
        self.assertIn("[Unit]", unit)
        self.assertIn("[Service]", unit)
        self.assertIn("[Install]", unit)

    def test_includes_python_executable(self):
        unit = render_host_service_unit(python_executable="/usr/bin/python3")
        self.assertIn("/usr/bin/python3", unit)

    def test_includes_working_directory(self):
        unit = render_host_service_unit(working_directory=Path("/home/test/fiona"))
        self.assertIn("WorkingDirectory=/home/test/fiona", unit)

    def test_includes_config_path(self):
        unit = render_host_service_unit(config_path=Path("/custom/config.json"))
        self.assertIn("--config /custom/config.json", unit)

    def test_includes_restart_policy(self):
        unit = render_host_service_unit()
        self.assertIn("Restart=on-failure", unit)
        self.assertIn("RestartSec=5", unit)

    def test_defaults_use_current_directory(self):
        unit = render_host_service_unit()
        self.assertIn("Type=simple", unit)

    def test_default_uses_sys_executable(self):
        unit = render_host_service_unit()
        self.assertIn(sys.executable, unit)

    def test_default_uses_cwd(self):
        unit = render_host_service_unit()
        self.assertIn(str(Path.cwd()), unit)


class ServiceUnitPathTests(unittest.TestCase):
    def test_default_name(self):
        path = service_unit_path()
        self.assertEqual(path.name, DEFAULT_SERVICE_NAME)
        self.assertEqual(path.parent, DEFAULT_SYSTEMD_USER_DIR)

    def test_custom_name(self):
        path = service_unit_path("custom.service")
        self.assertEqual(path.name, "custom.service")

    def test_path_is_absolute(self):
        path = service_unit_path()
        self.assertTrue(path.is_absolute())


class InstallHostServiceUnitTests(unittest.TestCase):
    def test_installs_unit_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            systemd_dir = Path(tmp) / ".config" / "systemd" / "user"
            with patch(
                "CamComs.systemd.DEFAULT_SYSTEMD_USER_DIR", systemd_dir
            ):
                path = install_host_service_unit()
                self.assertTrue(path.exists())
                content = path.read_text(encoding="utf-8")
                self.assertIn("[Unit]", content)

    def test_creates_parent_directories(self):
        with tempfile.TemporaryDirectory() as tmp:
            systemd_dir = Path(tmp) / "deep" / "nested" / "systemd" / "user"
            with patch(
                "CamComs.systemd.DEFAULT_SYSTEMD_USER_DIR", systemd_dir
            ):
                path = install_host_service_unit()
                self.assertTrue(path.parent.exists())

    def test_returns_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            systemd_dir = Path(tmp) / ".config" / "systemd" / "user"
            with patch(
                "CamComs.systemd.DEFAULT_SYSTEMD_USER_DIR", systemd_dir
            ):
                path = install_host_service_unit()
                self.assertIsInstance(path, Path)


class RunUserServiceCommandTests(unittest.TestCase):
    @patch("CamComs.systemd.subprocess.run")
    def test_enable_action(self, mock_run):
        mock_run.return_value = subprocess.CompletedProcess(
            ["systemctl"], returncode=0, stdout="", stderr=""
        )
        run_user_service_command("enable")
        mock_run.assert_called_once_with(
            ["systemctl", "--user", "enable", "--now", DEFAULT_SERVICE_NAME],
            check=True, text=True, capture_output=True,
        )

    @patch("CamComs.systemd.subprocess.run")
    def test_disable_action(self, mock_run):
        mock_run.return_value = subprocess.CompletedProcess(
            ["systemctl"], returncode=0, stdout="", stderr=""
        )
        run_user_service_command("disable")
        mock_run.assert_called_once_with(
            ["systemctl", "--user", "disable", DEFAULT_SERVICE_NAME],
            check=True, text=True, capture_output=True,
        )

    @patch("CamComs.systemd.subprocess.run")
    def test_restart_action(self, mock_run):
        mock_run.return_value = subprocess.CompletedProcess(
            ["systemctl"], returncode=0, stdout="", stderr=""
        )
        run_user_service_command("restart")
        mock_run.assert_called_once_with(
            ["systemctl", "--user", "restart", DEFAULT_SERVICE_NAME],
            check=True, text=True, capture_output=True,
        )

    @patch("CamComs.systemd.subprocess.run")
    def test_stop_action(self, mock_run):
        mock_run.return_value = subprocess.CompletedProcess(
            ["systemctl"], returncode=0, stdout="", stderr=""
        )
        run_user_service_command("stop")
        mock_run.assert_called_once_with(
            ["systemctl", "--user", "stop", DEFAULT_SERVICE_NAME],
            check=True, text=True, capture_output=True,
        )

    def test_raises_value_error_for_unsupported_action(self):
        with self.assertRaises(ValueError) as ctx:
            run_user_service_command("unsupported")
        self.assertIn("unsupported service action", str(ctx.exception))

    def test_raises_value_error_for_empty_action(self):
        with self.assertRaises(ValueError):
            run_user_service_command("")

    @patch("CamComs.systemd.subprocess.run")
    def test_custom_service_name(self, mock_run):
        mock_run.return_value = subprocess.CompletedProcess(
            ["systemctl"], returncode=0, stdout="", stderr=""
        )
        run_user_service_command("restart", service_name="my-app.service")
        mock_run.assert_called_once_with(
            ["systemctl", "--user", "restart", "my-app.service"],
            check=True, text=True, capture_output=True,
        )


class ReadHostServiceLogsTests(unittest.TestCase):
    @patch("CamComs.systemd.subprocess.run")
    def test_read_logs_default_lines(self, mock_run):
        mock_run.return_value = subprocess.CompletedProcess(
            ["journalctl"], returncode=0, stdout="log line 1\nlog line 2", stderr=""
        )
        result = read_host_service_logs()
        self.assertEqual(result.returncode, 0)
        mock_run.assert_called_once()
        args = mock_run.call_args[0][0]
        self.assertIn("journalctl", args)
        self.assertIn("-n", args)
        self.assertIn("80", args)

    @patch("CamComs.systemd.subprocess.run")
    def test_read_logs_custom_lines(self, mock_run):
        mock_run.return_value = subprocess.CompletedProcess(
            ["journalctl"], returncode=0, stdout="", stderr=""
        )
        read_host_service_logs(lines=200)
        args = mock_run.call_args[0][0]
        self.assertIn("200", args)

    @patch("CamComs.systemd.subprocess.run")
    def test_read_logs_custom_service_name(self, mock_run):
        mock_run.return_value = subprocess.CompletedProcess(
            ["journalctl"], returncode=0, stdout="", stderr=""
        )
        read_host_service_logs(service_name="custom.service")
        args = mock_run.call_args[0][0]
        self.assertIn("-u", args)
        self.assertIn("custom.service", args)

    @patch("CamComs.systemd.subprocess.run")
    def test_read_logs_with_follow(self, mock_run):
        mock_run.return_value = subprocess.CompletedProcess(
            ["journalctl"], returncode=0, stdout="", stderr=""
        )
        read_host_service_logs(follow=True)
        args = mock_run.call_args[0][0]
        self.assertIn("-f", args)

    @patch("CamComs.systemd.subprocess.run")
    def test_read_logs_without_follow(self, mock_run):
        mock_run.return_value = subprocess.CompletedProcess(
            ["journalctl"], returncode=0, stdout="", stderr=""
        )
        read_host_service_logs(follow=False)
        args = mock_run.call_args[0][0]
        self.assertNotIn("-f", args)

    @patch("CamComs.systemd.subprocess.run")
    def test_read_logs_includes_no_pager(self, mock_run):
        mock_run.return_value = subprocess.CompletedProcess(
            ["journalctl"], returncode=0, stdout="", stderr=""
        )
        read_host_service_logs()
        args = mock_run.call_args[0][0]
        self.assertIn("--no-pager", args)


if __name__ == "__main__":
    unittest.main()
