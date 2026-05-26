from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from CamComs import CamComsIdentity, ReplayGuard, encode_envelope, encrypt_message, save_trusted_sender
from PhiConnect import PhiConnectConfig, PhiConnectMessageProcessor, ensure_identity, read_recent_messages, send_chat_message


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
            alice = CamComsIdentity.generate("alice")
            bob = CamComsIdentity.generate("bob")
            trusted_dir = tmp_path / "trusted"
            save_trusted_sender(alice.public_bundle, trusted_dir)
            processor = PhiConnectMessageProcessor(
                identity=bob,
                trusted_dir=trusted_dir,
                replay_guard=ReplayGuard(tmp_path / "seen.json"),
                chat_log=None,
            )
            processor.chat_log.path = tmp_path / "chat.log"
            envelope = encrypt_message(
                json.dumps(
                    {"version": 1, "type": "chat", "sender": "alice", "recipient": "bob", "body": "hello"},
                    sort_keys=True,
                    separators=(",", ":"),
                ),
                sender=alice,
                recipient=bob.public_bundle,
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
                device_id="alice",
                private_path=tmp_path / "alice.private.json",
                public_path=tmp_path / "alice.public.json",
                peer_public_path=tmp_path / "bob.public.json",
                chat_log_path=tmp_path / "chat.log",
            )
            ensure_identity(config)
            bob = CamComsIdentity.generate("bob")
            (tmp_path / "bob.public.json").write_text(
                json.dumps(bob.public_bundle.to_dict()),
                encoding="utf-8",
            )

            with patch("CamComs.transport.request.urlopen", return_value=FakeResponse()) as urlopen:
                event = send_chat_message("hello bob", config=config, host="127.0.0.1", port=9000)

            self.assertTrue(event["ok"])
            self.assertEqual(event["body"], "hello bob")
            self.assertEqual(urlopen.call_args.args[0].full_url, "http://127.0.0.1:9000/")
            messages = read_recent_messages(tmp_path / "chat.log")
            self.assertEqual(messages[-1]["direction"], "outbound")


if __name__ == "__main__":
    unittest.main()
