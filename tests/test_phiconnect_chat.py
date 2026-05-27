from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from CamComs import CamComsIdentity, ReplayGuard, encode_envelope, encrypt_message, save_trusted_sender
from PhiConnect import (
    PhiConnectConfig,
    PhiConnectError,
    PhiConnectMessageProcessor,
    ensure_identity,
    read_recent_messages,
    send_chat_message,
    trust_public_key,
)
from PhiConnect.chat import _chat_payload


class FakeResponse:
    def __enter__(self) -> FakeResponse:
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def read(self) -> bytes:
        return b'{"ok":true}'


class PhiConnectChatTests(unittest.TestCase):
    def test_processes_encrypted_chat_from_trusted_peer(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            fiona = CamComsIdentity.generate("fiona")
            fiona_peer = CamComsIdentity.generate("fiona-peer")
            trusted_dir = tmp_path / "trusted"
            save_trusted_sender(fiona.public_bundle, trusted_dir)
            processor = PhiConnectMessageProcessor(
                identity=fiona_peer,
                trusted_dir=trusted_dir,
                replay_guard=ReplayGuard(tmp_path / "seen.json"),
                chat_log=None,
            )
            processor.chat_log.path = tmp_path / "chat.log"
            envelope = encrypt_message(
                json.dumps(
                    {"version": 1, "type": "chat", "sender": "fiona", "recipient": "fiona-peer", "body": "hello"},
                    sort_keys=True,
                    separators=(",", ":"),
                ),
                sender=fiona,
                recipient=fiona_peer.public_bundle,
                message_type="chat",
            )

            response = processor.process_encoded(encode_envelope(envelope))

            self.assertTrue(response["ok"])
            messages = read_recent_messages(tmp_path / "chat.log")
            self.assertEqual(messages[-1]["body"], "hello")
            self.assertEqual(messages[-1]["direction"], "inbound")

    def test_send_chat_message_encrypts_and_posts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            config = PhiConnectConfig(
                device_id="fiona",
                private_path=tmp_path / "fiona.private.json",
                public_path=tmp_path / "fiona.public.json",
                peer_public_path=tmp_path / "fiona-peer.public.json",
                chat_log_path=tmp_path / "chat.log",
            )
            ensure_identity(config)
            fiona_peer = CamComsIdentity.generate("fiona-peer")
            (tmp_path / "fiona-peer.public.json").write_text(
                json.dumps(fiona_peer.public_bundle.to_dict()),
                encoding="utf-8",
            )

            with patch("CamComs.transport.request.urlopen", return_value=FakeResponse()) as urlopen:
                event = send_chat_message("hello fiona", config=config, host="127.0.0.1", port=9000)

            self.assertTrue(event["ok"])
            self.assertEqual(event["body"], "hello fiona")
            self.assertEqual(urlopen.call_args.args[0].full_url, "http://127.0.0.1:9000/")
            messages = read_recent_messages(tmp_path / "chat.log")
            self.assertEqual(messages[-1]["direction"], "outbound")

    def test_ensure_identity_reuses_existing_key_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            config = PhiConnectConfig(
                device_id="fiona",
                private_path=tmp_path / "fiona.private.json",
                public_path=tmp_path / "fiona.public.json",
            )

            first = ensure_identity(config)
            second = ensure_identity(config)

        self.assertEqual(first.device_id, "fiona")
        self.assertEqual(second.device_id, "fiona")
        self.assertEqual(first.public_bundle.to_dict(), second.public_bundle.to_dict())

    def test_trust_public_key_writes_bundle_by_device_id(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            peer = CamComsIdentity.generate("peer")
            public_path = tmp_path / "peer.public.json"
            trusted_dir = tmp_path / "trusted"
            public_path.write_text(json.dumps(peer.public_bundle.to_dict()), encoding="utf-8")

            trusted_path = trust_public_key(public_path, trusted_dir)

            self.assertEqual(trusted_path.name, "peer.public.json")
            self.assertTrue(trusted_path.exists())

    def test_rejects_untrusted_sender_and_logs_failure(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            fiona = CamComsIdentity.generate("fiona")
            fiona_peer = CamComsIdentity.generate("fiona-peer")
            processor = PhiConnectMessageProcessor(
                identity=fiona_peer,
                trusted_dir=tmp_path / "trusted",
                replay_guard=ReplayGuard(tmp_path / "seen.json"),
                chat_log=None,
            )
            processor.chat_log.path = tmp_path / "chat.log"
            envelope = encrypt_message(
                json.dumps(_chat_payload("hello", sender="fiona", recipient="fiona-peer"), sort_keys=True, separators=(",", ":")),
                sender=fiona,
                recipient=fiona_peer.public_bundle,
                message_type="chat",
            )

            with self.assertRaises(PhiConnectError):
                processor.process_encoded(encode_envelope(envelope))

            messages = read_recent_messages(tmp_path / "chat.log")
            self.assertFalse(messages[-1]["ok"])
            self.assertIn("sender is not trusted", messages[-1]["error"])

    def test_rejects_replayed_chat_message(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            fiona = CamComsIdentity.generate("fiona")
            fiona_peer = CamComsIdentity.generate("fiona-peer")
            trusted_dir = tmp_path / "trusted"
            save_trusted_sender(fiona.public_bundle, trusted_dir)
            processor = PhiConnectMessageProcessor(
                identity=fiona_peer,
                trusted_dir=trusted_dir,
                replay_guard=ReplayGuard(tmp_path / "seen.json"),
                chat_log=None,
            )
            processor.chat_log.path = tmp_path / "chat.log"
            envelope = encrypt_message(
                json.dumps(_chat_payload("hello", sender="fiona", recipient="fiona-peer"), sort_keys=True, separators=(",", ":")),
                sender=fiona,
                recipient=fiona_peer.public_bundle,
                message_type="chat",
            )
            encoded = encode_envelope(envelope)

            self.assertTrue(processor.process_encoded(encoded)["ok"])
            with self.assertRaises(ValueError):
                processor.process_encoded(encoded)

            messages = read_recent_messages(tmp_path / "chat.log")
            self.assertFalse(messages[-1]["ok"])

    def test_chat_payload_rejects_blank_body(self) -> None:
        with self.assertRaises(PhiConnectError):
            _chat_payload("   ", sender="fiona", recipient="fiona-peer")


if __name__ == "__main__":
    unittest.main()
