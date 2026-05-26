from __future__ import annotations

import unittest

from CamComs import (
    CamComsCryptoError,
    CamComsIdentity,
    PublicKeyBundle,
    decrypt_text,
    encrypt_message,
    instruction_to_text,
    press_instruction,
)


class CamComsEncryptionTests(unittest.TestCase):
    def test_encrypts_and_decrypts_for_recipient(self) -> None:
        sender = CamComsIdentity.generate("laptop")
        recipient = CamComsIdentity.generate("desktop")

        instruction_text = instruction_to_text(press_instruction(["alt", "s"]))
        envelope = encrypt_message(instruction_text, sender=sender, recipient=recipient.public_bundle)

        self.assertEqual(
            decrypt_text(envelope, recipient=recipient, expected_sender=sender.public_bundle),
            instruction_text,
        )
        self.assertNotIn(instruction_text, str(envelope))

    def test_rejects_wrong_recipient(self) -> None:
        sender = CamComsIdentity.generate("laptop")
        recipient = CamComsIdentity.generate("desktop")
        other_device = CamComsIdentity.generate("phone")
        envelope = encrypt_message("secret", sender=sender, recipient=recipient.public_bundle)

        with self.assertRaises(CamComsCryptoError):
            decrypt_text(envelope, recipient=other_device, expected_sender=sender.public_bundle)

    def test_rejects_tampered_ciphertext(self) -> None:
        sender = CamComsIdentity.generate("laptop")
        recipient = CamComsIdentity.generate("desktop")
        envelope = encrypt_message("secret", sender=sender, recipient=recipient.public_bundle)
        envelope["ciphertext"] = envelope["ciphertext"][:-2] + "AA"

        with self.assertRaises(CamComsCryptoError):
            decrypt_text(envelope, recipient=recipient, expected_sender=sender.public_bundle)

    def test_public_bundle_round_trip(self) -> None:
        identity = CamComsIdentity.generate("laptop")

        restored = PublicKeyBundle.from_dict(identity.public_bundle.to_dict())

        self.assertEqual(restored.device_id, "laptop")

    def test_encrypted_private_bundle_requires_passphrase(self) -> None:
        identity = CamComsIdentity.generate("laptop")
        encrypted = identity.to_private_dict("secret")

        with self.assertRaises(CamComsCryptoError):
            CamComsIdentity.from_private_dict(encrypted)

        restored = CamComsIdentity.from_private_dict(encrypted, passphrase="secret")
        self.assertEqual(restored.device_id, "laptop")


if __name__ == "__main__":
    unittest.main()
