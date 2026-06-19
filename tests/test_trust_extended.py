"""Extended tests for trust management beyond test_camcoms_trust.py.

Covers: remove_trusted_sender edge cases, load_all_trusted_senders (via
list_trusted_senders) with empty/mixed format, prune_expired edge cases,
backward compatibility with old format, is_trust_expired edge cases, and
malformed file handling.
"""

from __future__ import annotations

import json
import time
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from CamComs import CamComsIdentity, TrustedSender
from CamComs.trust import (
    find_trusted_sender,
    is_trust_expired,
    list_trusted_senders,
    load_trusted_sender,
    prune_expired,
    remove_trusted_sender,
    save_trusted_sender,
)


class RemoveTrustedSenderTests(unittest.TestCase):
    """remove_trusted_sender() edge cases."""

    def setUp(self) -> None:
        self.tmpdir = TemporaryDirectory()
        self.trusted_dir = Path(self.tmpdir.name) / "trusted"

    def tearDown(self) -> None:
        self.tmpdir.cleanup()

    def test_remove_nonexistent_returns_false(self) -> None:
        self.assertFalse(remove_trusted_sender("nonexistent", self.trusted_dir))

    def test_remove_existing_returns_true(self) -> None:
        identity = CamComsIdentity.generate("test_dev")
        save_trusted_sender(identity.public_bundle, self.trusted_dir)
        self.assertTrue(remove_trusted_sender("test_dev", self.trusted_dir))

    def test_remove_twice_returns_false_second_time(self) -> None:
        identity = CamComsIdentity.generate("test_dev")
        save_trusted_sender(identity.public_bundle, self.trusted_dir)
        self.assertTrue(remove_trusted_sender("test_dev", self.trusted_dir))
        self.assertFalse(remove_trusted_sender("test_dev", self.trusted_dir))

    def test_remove_does_not_affect_other_devices(self) -> None:
        id_a = CamComsIdentity.generate("device_a")
        id_b = CamComsIdentity.generate("device_b")
        save_trusted_sender(id_a.public_bundle, self.trusted_dir)
        save_trusted_sender(id_b.public_bundle, self.trusted_dir)
        remove_trusted_sender("device_a", self.trusted_dir)
        remaining = list_trusted_senders(self.trusted_dir)
        self.assertEqual([t.bundle.device_id for t in remaining], ["device_b"])


class ListTrustedSendersTests(unittest.TestCase):
    """list_trusted_senders() — empty dir, mixed formats, malformed files."""

    def setUp(self) -> None:
        self.tmpdir = TemporaryDirectory()
        self.trusted_dir = Path(self.tmpdir.name) / "trusted"
        self.trusted_dir.mkdir(parents=True, exist_ok=True)

    def tearDown(self) -> None:
        self.tmpdir.cleanup()

    def test_empty_dir_returns_empty_list(self) -> None:
        self.assertEqual(list_trusted_senders(self.trusted_dir), [])

    def test_nonexistent_dir_returns_empty_list(self) -> None:
        nowhere = Path(self.tmpdir.name) / "nowhere"
        self.assertEqual(list_trusted_senders(nowhere), [])

    def test_malformed_json_file_is_skipped(self) -> None:
        bad_file = self.trusted_dir / "bad.public.json"
        bad_file.write_text("{invalid json}", encoding="utf-8")
        self.assertEqual(list_trusted_senders(self.trusted_dir), [])

    def test_non_json_file_is_skipped(self) -> None:
        bad_file = self.trusted_dir / "notjson.public.json"
        bad_file.write_text("hello world", encoding="utf-8")
        self.assertEqual(list_trusted_senders(self.trusted_dir), [])

    def test_incomplete_data_file_is_skipped(self) -> None:
        missing = self.trusted_dir / "incomplete.public.json"
        missing.write_text('{"device_id": "only_device_id"}', encoding="utf-8")
        self.assertEqual(list_trusted_senders(self.trusted_dir), [])

    def test_mixed_format_files_all_load(self) -> None:
        """New and old format files coexist."""
        id_new = CamComsIdentity.generate("new_dev")
        id_old = CamComsIdentity.generate("old_dev")
        # New format
        save_trusted_sender(id_new.public_bundle, self.trusted_dir)
        # Old format (raw bundle, no version)
        old_path = self.trusted_dir / "old_dev.public.json"
        old_path.write_text(
            json.dumps(id_old.public_bundle.to_dict(), indent=2) + "\n",
            encoding="utf-8",
        )
        result = list_trusted_senders(self.trusted_dir)
        device_ids = {t.bundle.device_id for t in result}
        self.assertIn("new_dev", device_ids)
        self.assertIn("old_dev", device_ids)


class PruneExpiredTests(unittest.TestCase):
    """prune_expired() edge cases."""

    def setUp(self) -> None:
        self.tmpdir = TemporaryDirectory()
        self.trusted_dir = Path(self.tmpdir.name) / "trusted"
        self.trusted_dir.mkdir(parents=True, exist_ok=True)

    def tearDown(self) -> None:
        self.tmpdir.cleanup()

    def test_prune_empty_dir_returns_empty_list(self) -> None:
        result = prune_expired(self.trusted_dir)
        self.assertEqual(result, [])

    def test_prune_non_expired_returns_empty_list(self) -> None:
        identity = CamComsIdentity.generate("valid_dev")
        far_future = int(time.time()) + 86400 * 365
        save_trusted_sender(identity.public_bundle, self.trusted_dir, expires_at=far_future)
        result = prune_expired(self.trusted_dir)
        self.assertEqual(result, [])

    def test_prune_expired_returns_removed_ids(self) -> None:
        identity = CamComsIdentity.generate("expired_dev")
        past = int(time.time()) - 10  # 10 seconds ago
        save_trusted_sender(identity.public_bundle, self.trusted_dir, expires_at=past)
        result = prune_expired(self.trusted_dir)
        self.assertEqual(result, ["expired_dev"])

    def test_prune_mixed_expired_and_valid(self) -> None:
        id_valid = CamComsIdentity.generate("valid_dev")
        id_expired = CamComsIdentity.generate("expired_dev")
        save_trusted_sender(id_valid.public_bundle, self.trusted_dir)
        past = int(time.time()) - 10
        save_trusted_sender(id_expired.public_bundle, self.trusted_dir, expires_at=past)
        removed = prune_expired(self.trusted_dir)
        self.assertIn("expired_dev", removed)
        self.assertNotIn("valid_dev", removed)
        remaining = list_trusted_senders(self.trusted_dir)
        self.assertEqual([t.bundle.device_id for t in remaining], ["valid_dev"])


class IsTrustExpiredTests(unittest.TestCase):
    """is_trust_expired() edge cases."""

    def test_no_expiry_never_expired(self) -> None:
        identity = CamComsIdentity.generate("dev")
        trusted = TrustedSender(bundle=identity.public_bundle, added_at=0)
        self.assertFalse(is_trust_expired(trusted))

    def test_expiry_in_future_not_expired(self) -> None:
        identity = CamComsIdentity.generate("dev")
        trusted = TrustedSender(bundle=identity.public_bundle, added_at=0, expires_at=int(time.time()) + 3600)
        self.assertFalse(is_trust_expired(trusted))

    def test_expiry_in_past_is_expired(self) -> None:
        identity = CamComsIdentity.generate("dev")
        trusted = TrustedSender(bundle=identity.public_bundle, added_at=0, expires_at=int(time.time()) - 1)
        self.assertTrue(is_trust_expired(trusted))

    def test_expiry_at_zero_is_expired(self) -> None:
        identity = CamComsIdentity.generate("dev")
        trusted = TrustedSender(bundle=identity.public_bundle, added_at=0, expires_at=0)
        self.assertTrue(is_trust_expired(trusted))

    def test_none_expiry_field_not_expired(self) -> None:
        identity = CamComsIdentity.generate("dev")
        trusted = TrustedSender(bundle=identity.public_bundle, added_at=0, expires_at=None)
        self.assertFalse(is_trust_expired(trusted))


class BackwardCompatibilityTests(unittest.TestCase):
    """Loading old format trust files."""

    def setUp(self) -> None:
        self.tmpdir = TemporaryDirectory()
        self.trusted_dir = Path(self.tmpdir.name) / "trusted"
        self.trusted_dir.mkdir(parents=True, exist_ok=True)

    def tearDown(self) -> None:
        self.tmpdir.cleanup()

    def test_old_format_loaded_as_trusted_sender(self) -> None:
        """Old format (raw PublicKeyBundle dict) loads with added_at=0 and no expiry."""
        identity = CamComsIdentity.generate("legacy_dev")
        old_data = identity.public_bundle.to_dict()
        path = self.trusted_dir / "legacy_dev.public.json"
        path.write_text(json.dumps(old_data, indent=2) + "\n", encoding="utf-8")
        trusted = load_trusted_sender("legacy_dev", self.trusted_dir)
        self.assertEqual(trusted.bundle.device_id, "legacy_dev")
        self.assertEqual(trusted.added_at, 0)
        self.assertIsNone(trusted.expires_at)

    def test_mixed_format_in_same_dir(self) -> None:
        """Directory with both old and new format files loads all."""
        id_old = CamComsIdentity.generate("old_dev")
        id_new = CamComsIdentity.generate("new_dev")
        # Old format
        old_path = self.trusted_dir / "old_dev.public.json"
        old_path.write_text(
            json.dumps(id_old.public_bundle.to_dict(), indent=2) + "\n",
            encoding="utf-8",
        )
        # New format
        save_trusted_sender(id_new.public_bundle, self.trusted_dir)
        trusted_list = list_trusted_senders(self.trusted_dir)
        self.assertEqual(len(trusted_list), 2)

    def test_round_trip_preserves_added_at_and_expiry(self) -> None:
        identity = CamComsIdentity.generate("rt_dev")
        now = int(time.time())
        future = now + 86400
        save_trusted_sender(identity.public_bundle, self.trusted_dir, expires_at=future)
        loaded = load_trusted_sender("rt_dev", self.trusted_dir)
        self.assertGreaterEqual(loaded.added_at, now - 2)  # allow clock skew
        self.assertEqual(loaded.expires_at, future)


class FindTrustedSenderTests(unittest.TestCase):
    """find_trusted_sender() edge cases."""

    def setUp(self) -> None:
        self.tmpdir = TemporaryDirectory()
        self.trusted_dir = Path(self.tmpdir.name) / "trusted"

    def tearDown(self) -> None:
        self.tmpdir.cleanup()

    def test_find_nonexistent_dir_returns_none(self) -> None:
        nowhere = Path(self.tmpdir.name) / "nowhere"
        result = find_trusted_sender("dev", nowhere)
        self.assertIsNone(result)

    def test_find_existing_returns_sender(self) -> None:
        identity = CamComsIdentity.generate("existing_dev")
        save_trusted_sender(identity.public_bundle, self.trusted_dir)
        result = find_trusted_sender("existing_dev", self.trusted_dir)
        self.assertIsNotNone(result)
        self.assertEqual(result.bundle.device_id, "existing_dev")


if __name__ == "__main__":
    unittest.main()
