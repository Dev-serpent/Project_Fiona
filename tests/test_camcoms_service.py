from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from CamComs import (
    HostService,
    HostServiceConfig,
    load_host_service_config,
    read_host_service_logs,
    render_host_service_unit,
    run_user_service_command,
    save_host_service_config,
)


class CamComsServiceTests(unittest.TestCase):
    def test_config_round_trip(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            config_path = Path(tmp) / "config.json"
            config = HostServiceConfig(
                quiktieper_config_path=Path(tmp) / "bindings.json",
                host_private_path=Path(tmp) / "host.private.json",
                trusted_dir=Path(tmp) / "trusted",
                replay_path=Path(tmp) / "seen.json",
                receiver_host="127.0.0.1",
                receiver_port=9090,
                execute_remote_actions=True,
                start_quiktieper_listener=True,
                allowed_remote_actions=("press", "macro"),
                audit_log_path=Path(tmp) / "audit.log",
            )

            save_host_service_config(config, config_path)
            restored = load_host_service_config(config_path)

            self.assertEqual(restored, config)

    def test_status_reports_missing_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            service = HostService(
                HostServiceConfig(
                    quiktieper_config_path=Path(tmp) / "missing-bindings.json",
                    host_private_path=Path(tmp) / "missing-host.private.json",
                    trusted_dir=Path(tmp) / "missing-trusted",
                    replay_path=Path(tmp) / "state" / "seen.json",
                    audit_log_path=Path(tmp) / "state" / "audit.log",
                )
            )

            status = service.status()

            self.assertFalse(status["ready"])
            check_names = {check["name"] for check in status["checks"]}
            self.assertIn("quiktieper_config", check_names)
            self.assertIn("host_private_key", check_names)
            self.assertIn("trusted_dir", check_names)
            self.assertIn("audit_log_dir", check_names)

    def test_renders_user_systemd_service(self) -> None:
        unit = render_host_service_unit(
            python_executable="/usr/bin/python3",
            working_directory=Path("/opt/fiona"),
            config_path=Path("/tmp/fiona-config.json"),
        )

        self.assertIn("Description=Fiona host service", unit)
        self.assertIn("WorkingDirectory=/opt/fiona", unit)
        self.assertIn("ExecStart=/usr/bin/python3 -m fiona.cli host run --config /tmp/fiona-config.json", unit)
        self.assertIn("Restart=on-failure", unit)

    def test_runs_user_service_lifecycle_commands(self) -> None:
        with patch("CamComs.systemd.subprocess.run") as run:
            run_user_service_command("enable", service_name="fiona-host.service")
            run_user_service_command("restart", service_name="fiona-host.service")

        run.assert_any_call(
            ["systemctl", "--user", "enable", "--now", "fiona-host.service"],
            check=True,
            text=True,
            capture_output=True,
        )
        run.assert_any_call(
            ["systemctl", "--user", "restart", "fiona-host.service"],
            check=True,
            text=True,
            capture_output=True,
        )

    def test_rejects_unknown_user_service_action(self) -> None:
        with self.assertRaises(ValueError):
            run_user_service_command("delete")

    def test_reads_user_service_logs(self) -> None:
        with patch("CamComs.systemd.subprocess.run") as run:
            read_host_service_logs(service_name="fiona-host.service", lines=25)

        run.assert_called_once_with(
            ["journalctl", "--user", "-u", "fiona-host.service", "-n", "25", "--no-pager"],
            check=True,
            text=True,
            capture_output=True,
        )


if __name__ == "__main__":
    unittest.main()
