from __future__ import annotations

import json
import unittest
from CamComs.encryption import _canonical_bytes

class ESP32CompatibilityTests(unittest.TestCase):
    def test_canonical_json_order(self) -> None:
        # This test ensures that the key order expected by the ESP32
        # (alphabetical via sort_keys=True) is exactly what the Python side uses.
        
        data = {
            "version": 1,
            "kind": "camcoms.encrypted",
            "message_id": "123",
            "message_type": "instruction",
            "created_at": 1600000000,
            "sender": "esp32",
            "recipient": "host",
            "sender_signing_public_key": "pubkey",
            "ephemeral_public_key": "ephkey",
            "salt": "salt",
            "nonce": "nonce",
        }
        
        canonical = _canonical_bytes(data).decode("utf-8")
        
        # Keys should be in alphabetical order:
        # created_at, ephemeral_public_key, kind, message_id, message_type, nonce, recipient, salt, sender, sender_signing_public_key, version
        expected_keys = [
            "created_at", "ephemeral_public_key", "kind", "message_id", 
            "message_type", "nonce", "recipient", "salt", "sender", 
            "sender_signing_public_key", "version"
        ]
        
        # Verify order in string
        last_pos = -1
        for key in expected_keys:
            pos = canonical.find(f'"{key}":')
            self.assertGreater(pos, last_pos, f"Key {key} is out of order in canonical JSON")
            last_pos = pos

    def test_signature_canonical_json_order_with_ciphertext(self) -> None:
        # The signature includes 'ciphertext'. Alphabetically, 'ciphertext'
        # comes BEFORE 'created_at'.
        
        data = {
            "version": 1,
            "kind": "camcoms.encrypted",
            "message_id": "123",
            "message_type": "instruction",
            "created_at": 1600000000,
            "sender": "esp32",
            "recipient": "host",
            "sender_signing_public_key": "pubkey",
            "ephemeral_public_key": "ephkey",
            "salt": "salt",
            "nonce": "nonce",
            "ciphertext": "secret"
        }
        
        canonical = _canonical_bytes(data).decode("utf-8")
        
        # ciphertext should be the FIRST key
        self.assertTrue(canonical.startswith('{"ciphertext":"secret",'), f"Ciphertext should be first. Got: {canonical[:50]}")

if __name__ == "__main__":
    unittest.main()
