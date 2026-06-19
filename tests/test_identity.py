"""Tests for key rotation and identity management (CamComs/identity.py).

Covers rotate_keys() with temp identity, get_fingerprint(), load_identity(),
atomic save behavior, error handling for missing/corrupt identity, and
permissions.
"""

from __future__ import annotations

import json
import os
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from CamComs import CamComsIdentity
from CamComs.identity import (
    get_fingerprint,
    load_identity,
    rotate_keys,
)


class RotateKeysTests(unittest.TestCase):
    """rotate_keys() — key rotation with atomic save."""

    def setUp(self) -> None:
        self.tmpdir = TemporaryDirectory()
        self.identity_path = Path(self.tmpdir.name) / "identity.json"
        self.pubkey_path = Path(self.tmpdir.name) / "identity.pub"

    def tearDown(self) -> None:
        self.tmpdir.cleanup()

    def test_rotate_creates_identity_when_none_exists(self) -> None:
        old_fp, new_fp = rotate_keys(
            identity_path=self.identity_path,
            pubkey_path=self.pubkey_path,
            device_id="host",
        )
        self.assertEqual(old_fp, "(none)")
        self.assertNotEqual(new_fp, "(none)")
        self.assertTrue(self.identity_path.exists())
        self.assertTrue(self.pubkey_path.exists())

    def test_rotate_updates_existing_identity(self) -> None:
        # First rotation creates
        old_fp1, new_fp1 = rotate_keys(
            identity_path=self.identity_path,
            pubkey_path=self.pubkey_path,
            device_id="host",
        )
        # Second rotation should produce a different fingerprint
        old_fp2, new_fp2 = rotate_keys(
            identity_path=self.identity_path,
            pubkey_path=self.pubkey_path,
            device_id="host",
        )
        self.assertEqual(old_fp2, new_fp1)
        self.assertNotEqual(new_fp1, new_fp2)

    def test_rotate_saves_valid_json(self) -> None:
        rotate_keys(
            identity_path=self.identity_path,
            pubkey_path=self.pubkey_path,
            device_id="host",
        )
        data = json.loads(self.identity_path.read_text(encoding="utf-8"))
        self.assertIn("device_id", data)
        self.assertIn("encryption_private_key", data)
        self.assertIn("signing_private_key", data)
        self.assertEqual(data["device_id"], "host")

    def test_rotate_saves_public_key(self) -> None:
        rotate_keys(
            identity_path=self.identity_path,
            pubkey_path=self.pubkey_path,
            device_id="host",
        )
        pub_data = json.loads(self.pubkey_path.read_text(encoding="utf-8"))
        self.assertIn("device_id", pub_data)
        self.assertIn("encryption_public_key", pub_data)
        self.assertIn("signing_public_key", pub_data)

    def test_rotate_atomic_write_no_leftover_temp(self) -> None:
        """After rotation, no .tmp files remain in the identity directory."""
        rotate_keys(
            identity_path=self.identity_path,
            pubkey_path=self.pubkey_path,
            device_id="host",
        )
        tmp_files = list(self.identity_path.parent.glob("*.tmp"))
        self.assertEqual(tmp_files, [])

    def test_rotate_sets_private_permissions_on_posix(self) -> None:
        if os.name != "posix":
            self.skipTest("Permission test only applies on POSIX")
        rotate_keys(
            identity_path=self.identity_path,
            pubkey_path=self.pubkey_path,
            device_id="host",
        )
        mode = self.identity_path.stat().st_mode & 0o777
        self.assertEqual(mode, 0o600)


class LoadIdentityTests(unittest.TestCase):
    """load_identity() — loading identity from disk."""

    def setUp(self) -> None:
        self.tmpdir = TemporaryDirectory()
        self.identity_path = Path(self.tmpdir.name) / "identity.json"

    def tearDown(self) -> None:
        self.tmpdir.cleanup()

    def test_load_returns_none_when_missing(self) -> None:
        result = load_identity(self.identity_path)
        self.assertIsNone(result)

    def test_load_returns_identity_after_rotate(self) -> None:
        pubkey_path = Path(self.tmpdir.name) / "identity.pub"
        rotate_keys(
            identity_path=self.identity_path,
            pubkey_path=pubkey_path,
            device_id="host",
        )
        loaded = load_identity(self.identity_path)
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded.device_id, "host")

    def test_load_returns_none_for_corrupt_json(self) -> None:
        self.identity_path.write_text("{corrupt_json", encoding="utf-8")
        result = load_identity(self.identity_path)
        self.assertIsNone(result)

    def test_load_returns_none_for_invalid_data(self) -> None:
        self.identity_path.write_text('{"device_id": "incomplete"}', encoding="utf-8")
        result = load_identity(self.identity_path)
        self.assertIsNone(result)

    def test_load_returns_none_for_empty_file(self) -> None:
        self.identity_path.write_text("", encoding="utf-8")
        result = load_identity(self.identity_path)
        self.assertIsNone(result)


class GetFingerprintTests(unittest.TestCase):
    """get_fingerprint() — fingerprint from identity or path."""

    def setUp(self) -> None:
        self.tmpdir = TemporaryDirectory()
        self.identity_path = Path(self.tmpdir.name) / "identity.json"
        self.pubkey_path = Path(self.tmpdir.name) / "identity.pub"

    def tearDown(self) -> None:
        self.tmpdir.cleanup()

    def test_get_fingerprint_from_identity_object(self) -> None:
        identity = CamComsIdentity.generate("test_device")
        fp = get_fingerprint(identity=identity)
        self.assertIsInstance(fp, str)
        self.assertNotEqual(fp, "(no identity)")

    def test_get_fingerprint_from_path(self) -> None:
        rotate_keys(
            identity_path=self.identity_path,
            pubkey_path=self.pubkey_path,
            device_id="host",
        )
        fp = get_fingerprint(identity=None, identity_path=self.identity_path)
        self.assertIsInstance(fp, str)
        self.assertNotEqual(fp, "(no identity)")

    def test_get_fingerprint_returns_placeholder_when_no_identity(self) -> None:
        fp = get_fingerprint(identity=None, identity_path=self.identity_path)
        self.assertEqual(fp, "(no identity)")

    def test_get_fingerprint_consistent_for_same_identity(self) -> None:
        identity = CamComsIdentity.generate("test_device")
        fp1 = get_fingerprint(identity=identity)
        fp2 = get_fingerprint(identity=identity)
        self.assertEqual(fp1, fp2)


if __name__ == "__main__":
    unittest.main()
