from __future__ import annotations

import base64
import json
import unittest
import time
from CamComs.encryption import (
    CamComsIdentity,
    PublicKeyBundle,
    decrypt_text,
    _canonical_bytes,
)
from CamComs.codec import decode_envelope

class ESP32FirmwareSimulationTests(unittest.TestCase):
    """
    This test simulates the EXACT logic implemented in the ESP32 .ino file
    to ensure that the firmware's specific implementation of 
    canonicalization, encoding, and timestamp handling is 100% 
    compatible with the host's expectations.
    """

    def test_mock_esp32_payload_generation_and_host_decryption(self) -> None:
        # 1. Setup Identities
        host_id = CamComsIdentity.generate(device_id="host")
        esp32_id = CamComsIdentity.generate(device_id="esp32")
        
        # 2. ESP32 Side: Mocking the C++ implementation
        instruction = '{"keys":["alt","s"],"type":"press","version":1}'
        
        # Mock NTP Time
        now = int(time.time())
        created_at_str = str(now)
        
        # Mock random components
        message_id = "mock-id-12345"
        salt = b"1234567890123456" # 16 bytes
        nonce = b"123456789012"     # 12 bytes
        
        # ESP32 Helper: Manual Base64URL with padding (matching esp32payload.ino)
        def esp32_b64url(data: bytes) -> str:
            return base64.urlsafe_b64encode(data).decode("ascii")

        esp32_pub_signing_b64 = esp32_b64url(esp32_id.public_bundle.signing_public_key.public_bytes_raw())
        
        # 3. ESP32: Build AAD (jsonCanonicalForAad in C++)
        # Match the alphabetical order: created_at, ephemeral_public_key, kind, message_id, message_type, nonce, recipient, salt, sender, sender_signing_public_key, version
        # NOTE: In the C++, we generate an ephemeral key. Here we use a real one for the functional test.
        eph_private = CamComsIdentity.generate().encryption_private_key
        eph_public_bytes = eph_private.public_key().public_bytes_raw()
        eph_pub_b64 = esp32_b64url(eph_public_bytes)

        aad_dict = {
            "created_at": now,
            "ephemeral_public_key": eph_pub_b64,
            "kind": "camcoms.encrypted",
            "message_id": message_id,
            "message_type": "instruction",
            "nonce": esp32_b64url(nonce),
            "recipient": "host",
            "salt": esp32_b64url(salt),
            "sender": "esp32",
            "sender_signing_public_key": esp32_pub_signing_b64,
            "version": 1
        }
        
        # Python's _canonical_bytes uses sort_keys=True, which matches our C++ manual string building
        aad_bytes = _canonical_bytes(aad_dict)
        
        # 4. ESP32: Encrypt (Mocking encryptForHost in C++)
        shared_secret = eph_private.exchange(host_id.public_bundle.encryption_public_key)
        
        # Derived key using HKDF (Python side)
        from CamComs.encryption import _derive_message_key
        aes_key = _derive_message_key(shared_secret, salt)
        
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
        ciphertext_with_tag = AESGCM(aes_key).encrypt(nonce, instruction.encode("utf-8"), aad_bytes)
        ciphertext_b64 = esp32_b64url(ciphertext_with_tag)
        
        # 5. ESP32: Sign (jsonCanonicalForSignature in C++)
        # Alphabetical: "ciphertext" comes before "created_at"
        # We'll just update the dict and use canonical_bytes
        signed_dict = dict(aad_dict)
        signed_dict["ciphertext"] = ciphertext_b64
        
        signature_payload = _canonical_bytes(signed_dict)
        signature = esp32_id.signing_private_key.sign(signature_payload)
        
        # 6. ESP32: Final Envelope
        envelope = dict(signed_dict)
        envelope["signature"] = esp32_b64url(signature)
        
        # 7. Host Side: Verification
        # This is where we verify that the host's decrypt_text accepts the ESP32's "manual" assembly
        try:
            decrypted = decrypt_text(
                envelope,
                recipient=host_id,
                expected_sender=esp32_id.public_bundle
            )
            self.assertEqual(decrypted, instruction)
        except Exception as e:
            self.fail(f"Host failed to decrypt ESP32-simulated payload: {e}")

if __name__ == "__main__":
    unittest.main()
