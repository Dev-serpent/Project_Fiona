from __future__ import annotations

import tempfile
import time
import unittest
from pathlib import Path

from CamComs import (
    CamComsIdentity,
    TrustedSender,
    is_trust_expired,
    list_trusted_senders,
    prune_expired,
    remove_trusted_sender,
    save_trusted_sender,
)


class CamComsTrustTests(unittest.TestCase):
    def test_lists_and_removes_trusted_senders(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            trusted_dir = Path(tmp) / "trusted"
            esp32 = CamComsIdentity.generate("esp32")
            save_trusted_sender(esp32.public_bundle, trusted_dir)

            trusted_list = list_trusted_senders(trusted_dir)
            self.assertEqual([t.bundle.device_id for t in trusted_list], ["esp32"])
            self.assertIsNone(trusted_list[0].expires_at)
            self.assertFalse(is_trust_expired(trusted_list[0]))
            self.assertTrue(remove_trusted_sender("esp32", trusted_dir))
            self.assertFalse(remove_trusted_sender("esp32", trusted_dir))
            self.assertEqual(list_trusted_senders(trusted_dir), [])

    def test_saves_and_loads_with_expiry(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            trusted_dir = Path(tmp) / "trusted"
            esp32 = CamComsIdentity.generate("esp32")
            future = int(time.time()) + 86400
            save_trusted_sender(esp32.public_bundle, trusted_dir, expires_at=future)

            trusted_list = list_trusted_senders(trusted_dir)
            self.assertEqual(len(trusted_list), 1)
            self.assertEqual(trusted_list[0].bundle.device_id, "esp32")
            self.assertEqual(trusted_list[0].expires_at, future)
            self.assertFalse(is_trust_expired(trusted_list[0]))

    def test_prunes_expired_entries(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            trusted_dir = Path(tmp) / "trusted"
            esp32 = CamComsIdentity.generate("esp32")
            host = CamComsIdentity.generate("host")
            # Already expired
            save_trusted_sender(esp32.public_bundle, trusted_dir, expires_at=1000000)
            # Not expired
            save_trusted_sender(host.public_bundle, trusted_dir)

            removed = prune_expired(trusted_dir)
            self.assertEqual(removed, ["esp32"])
            remaining = list_trusted_senders(trusted_dir)
            self.assertEqual(len(remaining), 1)
            self.assertEqual(remaining[0].bundle.device_id, "host")

    def test_backward_compat_with_old_format(self) -> None:
        """Old format files (raw PublicKeyBundle dict) must still be readable."""
        with tempfile.TemporaryDirectory() as tmp:
            trusted_dir = Path(tmp) / "trusted"
            trusted_dir.mkdir(parents=True, exist_ok=True)
            esp32 = CamComsIdentity.generate("esp32")
            # Write old format directly
            old_data = esp32.public_bundle.to_dict()
            path = trusted_dir / "esp32.public.json"
            import json
            path.write_text(json.dumps(old_data, indent=2) + "\n", encoding="utf-8")

            # Must be loadable as TrustedSender
            trusted = list_trusted_senders(trusted_dir)
            self.assertEqual(len(trusted), 1)
            self.assertEqual(trusted[0].bundle.device_id, "esp32")
            self.assertIsNone(trusted[0].expires_at)
            self.assertEqual(trusted[0].added_at, 0)
            self.assertFalse(is_trust_expired(trusted[0]))

    def test_trusted_sender_round_trip(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            trusted_dir = Path(tmp) / "trusted"
            esp32 = CamComsIdentity.generate("esp32")
            future = int(time.time()) + 3600
            save_trusted_sender(esp32.public_bundle, trusted_dir, expires_at=future)

            loaded = list_trusted_senders(trusted_dir)[0]
            # Round-trip through to_dict/from_dict
            reconstructed = TrustedSender.from_dict(loaded.to_dict())
            self.assertEqual(reconstructed.bundle.device_id, loaded.bundle.device_id)
            self.assertEqual(reconstructed.added_at, loaded.added_at)
            self.assertEqual(reconstructed.expires_at, loaded.expires_at)
            self.assertFalse(is_trust_expired(reconstructed))

    def test_find_trusted_sender_returns_none_for_missing(self) -> None:
        from CamComs.trust import find_trusted_sender
        with tempfile.TemporaryDirectory() as tmp:
            result = find_trusted_sender("nonexistent", Path(tmp) / "trusted")
            self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()
