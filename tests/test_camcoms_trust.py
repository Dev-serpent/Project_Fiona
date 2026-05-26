from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from CamComs import CamComsIdentity, list_trusted_senders, remove_trusted_sender, save_trusted_sender


class CamComsTrustTests(unittest.TestCase):
    def test_lists_and_removes_trusted_senders(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            trusted_dir = Path(tmp) / "trusted"
            esp32 = CamComsIdentity.generate("esp32")
            save_trusted_sender(esp32.public_bundle, trusted_dir)

            self.assertEqual([bundle.device_id for bundle in list_trusted_senders(trusted_dir)], ["esp32"])
            self.assertTrue(remove_trusted_sender("esp32", trusted_dir))
            self.assertFalse(remove_trusted_sender("esp32", trusted_dir))
            self.assertEqual(list_trusted_senders(trusted_dir), [])


if __name__ == "__main__":
    unittest.main()
