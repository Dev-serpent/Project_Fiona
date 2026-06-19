"""Tests for CamComs.replay — replay attack protection."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from CamComs.encryption import CamComsCryptoError
from CamComs.replay import ReplayGuard


class ReplayGuardInitTests(unittest.TestCase):
    def test_default_path(self):
        guard = ReplayGuard()
        self.assertTrue(str(guard.path).endswith("seen_messages.json"))

    def test_custom_path(self):
        guard = ReplayGuard(Path("/tmp/test_seen.json"))
        self.assertEqual(guard.path, Path("/tmp/test_seen.json"))

    def test_default_max_age(self):
        guard = ReplayGuard()
        self.assertEqual(guard.max_age_seconds, 300)

    def test_custom_max_age(self):
        guard = ReplayGuard(max_age_seconds=60)
        self.assertEqual(guard.max_age_seconds, 60)


class ReplayGuardCheckRecordTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "seen.json"

    def tearDown(self):
        self.tmp.cleanup()

    def _make_envelope(self, message_id="msg1", created_at=None):
        import time
        return {
            "message_id": message_id,
            "created_at": created_at or int(time.time()),
        }

    def test_accepts_new_message(self):
        guard = ReplayGuard(self.path)
        envelope = self._make_envelope()
        guard.check_and_record(envelope, now=envelope["created_at"])
        # No exception means success
        self.assertTrue(self.path.exists())

    def test_records_message_id_to_file(self):
        guard = ReplayGuard(self.path)
        envelope = self._make_envelope("unique123", created_at=1000000)
        guard.check_and_record(envelope, now=1000000)
        data = json.loads(self.path.read_text())
        self.assertIn("unique123", data)

    def test_rejects_duplicate_message_id(self):
        guard = ReplayGuard(self.path)
        envelope = self._make_envelope("dup1", created_at=1000000)
        guard.check_and_record(envelope, now=1000000)
        with self.assertRaises(CamComsCryptoError) as ctx:
            guard.check_and_record(envelope, now=1000000)
        self.assertIn("already been seen", str(ctx.exception))

    def test_rejects_message_without_message_id(self):
        guard = ReplayGuard(self.path)
        envelope = {"created_at": 1000000}
        with self.assertRaises(CamComsCryptoError) as ctx:
            guard.check_and_record(envelope, now=1000000)
        self.assertIn("message_id", str(ctx.exception))

    def test_rejects_message_with_empty_message_id(self):
        guard = ReplayGuard(self.path)
        envelope = {"message_id": "", "created_at": 1000000}
        with self.assertRaises(CamComsCryptoError) as ctx:
            guard.check_and_record(envelope, now=1000000)
        self.assertIn("message_id", str(ctx.exception))

    def test_rejects_message_without_created_at(self):
        guard = ReplayGuard(self.path)
        envelope = {"message_id": "m1"}
        with self.assertRaises(CamComsCryptoError) as ctx:
            guard.check_and_record(envelope, now=1000000)
        self.assertIn("created_at", str(ctx.exception))

    def test_rejects_message_with_non_int_created_at(self):
        guard = ReplayGuard(self.path)
        envelope = {"message_id": "m1", "created_at": "not_an_int"}
        with self.assertRaises(CamComsCryptoError) as ctx:
            guard.check_and_record(envelope, now=1000000)
        self.assertIn("created_at", str(ctx.exception))

    def test_rejects_message_outside_replay_window(self):
        guard = ReplayGuard(self.path, max_age_seconds=60)
        envelope = self._make_envelope("old", created_at=1000)
        with self.assertRaises(CamComsCryptoError) as ctx:
            guard.check_and_record(envelope, now=99999)
        self.assertIn("replay window", str(ctx.exception))

    def test_accepts_message_at_edge_of_window(self):
        guard = ReplayGuard(self.path, max_age_seconds=60)
        now = 1000000
        envelope = self._make_envelope("edge", created_at=now - 60)
        guard.check_and_record(envelope, now=now)
        self.assertTrue(self.path.exists())

    def test_rejects_message_one_second_beyond_window(self):
        guard = ReplayGuard(self.path, max_age_seconds=60)
        now = 1000000
        envelope = self._make_envelope("beyond", created_at=now - 61)
        with self.assertRaises(CamComsCryptoError):
            guard.check_and_record(envelope, now=now)


class ReplayGuardPruneTests(unittest.TestCase):
    def test_prunes_expired_entries(self):
        tmp = tempfile.TemporaryDirectory()
        path = Path(tmp.name) / "seen.json"
        guard = ReplayGuard(path, max_age_seconds=60)
        now = 1000000

        # Insert entries within the window at the current time
        guard.check_and_record(
            {"message_id": "old1", "created_at": now - 30}, now=now  # 30s old — within 60s window
        )
        guard.check_and_record(
            {"message_id": "fresh", "created_at": now - 10}, now=now  # 10s old
        )

        # Fast-forward: old1 (30s old at t=1000) is >60s old at t=1060
        # fresh is still within window (only 70s old, but window is 60s... so it also gets pruned)
        # Adjust: make fresh more recent
        later = now + 50  # +50s → now=1000050
        guard.check_and_record(
            {"message_id": "new", "created_at": later}, now=later
        )

        data = json.loads(path.read_text())
        self.assertNotIn("old1", data)   # old1: created_at=999970, cutoff=1000050-60=999990, 999970<999990 → pruned
        self.assertIn("fresh", data)     # fresh: created_at=999990, 999990>=999990 → kept (exactly at cutoff)
        self.assertIn("new", data)
        tmp.cleanup()

    def test_prune_empty_seen_does_nothing(self):
        guard = ReplayGuard(max_age_seconds=60)
        seen = {}
        guard._prune_seen(seen, 1000)
        self.assertEqual(seen, {})

    def test_prune_all_expired(self):
        guard = ReplayGuard(max_age_seconds=60)
        seen = {"old1": 800, "old2": 900}
        guard._prune_seen(seen, 1000)
        self.assertEqual(seen, {})

    def test_prune_keeps_recent(self):
        guard = ReplayGuard(max_age_seconds=60)
        seen = {"old1": 800, "fresh": 950}
        guard._prune_seen(seen, 1000)
        self.assertIn("fresh", seen)
        self.assertNotIn("old1", seen)


class ReplayGuardLoadWriteTests(unittest.TestCase):
    def test_load_seen_returns_empty_for_missing_file(self):
        guard = ReplayGuard(Path("/nonexistent/seen.json"))
        self.assertEqual(guard._load_seen(), {})

    def test_load_seen_raises_for_invalid_json(self):
        """Invalid JSON content causes a JSONDecodeError (not caught internally)."""
        import json as _json
        tmp = tempfile.TemporaryDirectory()
        path = Path(tmp.name) / "seen.json"
        path.write_text("not json", encoding="utf-8")
        guard = ReplayGuard(path)
        with self.assertRaises(_json.JSONDecodeError):
            guard._load_seen()
        tmp.cleanup()

    def test_load_seen_returns_empty_for_non_dict_json(self):
        tmp = tempfile.TemporaryDirectory()
        path = Path(tmp.name) / "seen.json"
        path.write_text("[]", encoding="utf-8")
        guard = ReplayGuard(path)
        self.assertEqual(guard._load_seen(), {})
        tmp.cleanup()

    def test_load_seen_reads_valid_file(self):
        tmp = tempfile.TemporaryDirectory()
        path = Path(tmp.name) / "seen.json"
        path.write_text('{"msg1": 1000, "msg2": 1001}', encoding="utf-8")
        guard = ReplayGuard(path)
        self.assertEqual(guard._load_seen(), {"msg1": 1000, "msg2": 1001})
        tmp.cleanup()

    def test_write_seen_creates_parent_dir(self):
        tmp = tempfile.TemporaryDirectory()
        path = Path(tmp.name) / "sub" / "seen.json"
        guard = ReplayGuard(path)
        guard._write_seen({"test": 123})
        self.assertTrue(path.exists())
        data = json.loads(path.read_text())
        self.assertEqual(data, {"test": 123})
        tmp.cleanup()


if __name__ == "__main__":
    unittest.main()
