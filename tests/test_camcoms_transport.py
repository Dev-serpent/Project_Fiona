from __future__ import annotations

import unittest
from unittest.mock import patch

from CamComs import CamComsHttpClient, CamComsIdentity, PublicKeyBundle, decode_envelope, encode_envelope, encrypt_and_send_instruction


class FakeResponse:
    def __init__(self, payload: bytes) -> None:
        self.payload = payload

    def __enter__(self) -> FakeResponse:
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def read(self) -> bytes:
        return self.payload


class CamComsTransportTests(unittest.TestCase):
    def test_encode_decode_envelope(self) -> None:
        envelope = {"kind": "camcoms.encrypted", "ciphertext": "abc"}

        encoded = encode_envelope(envelope)

        self.assertEqual(decode_envelope(encoded), envelope)
        self.assertIsInstance(encoded, str)

    def test_http_client_posts_encoded_message_and_reads_encoded_response(self) -> None:
        envelope = {"kind": "camcoms.encrypted", "ciphertext": "abc"}
        encoded = encode_envelope(envelope)

        with patch("CamComs.transport.request.urlopen", return_value=FakeResponse(encoded.encode("ascii"))) as urlopen:
            client = CamComsHttpClient(host="192.168.4.1", port=8080, timeout_seconds=2.0)

            response = client.send_envelope(envelope)

        self.assertEqual(response, envelope)
        http_request = urlopen.call_args.args[0]
        self.assertEqual(http_request.full_url, "http://192.168.4.1:8080/")
        self.assertEqual(http_request.data, encoded.encode("ascii"))

    def test_encrypt_and_send_instruction_posts_encoded_envelope(self) -> None:
        sender = CamComsIdentity.generate("host")
        recipient = CamComsIdentity.generate("esp32").public_bundle

        with patch("CamComs.transport.request.urlopen", return_value=FakeResponse(b"{\"ok\":true}")) as urlopen:
            response = encrypt_and_send_instruction(
                sender=sender,
                recipient=recipient,
                host="192.168.4.1",
                press_keys=["alt", "s"],
            )

        self.assertEqual(response, '{"ok":true}')
        http_request = urlopen.call_args.args[0]
        envelope = decode_envelope(http_request.data.decode("ascii"))
        self.assertEqual(envelope["sender"], "host")
        self.assertEqual(envelope["recipient"], "esp32")


if __name__ == "__main__":
    unittest.main()
