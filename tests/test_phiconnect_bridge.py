"""Tests for PhiConnect.bridge — agent message bridge."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from PhiConnect.bridge import PhiConnectAgentBridge
from PhiConnect.chat import PhiConnectConfig


class PhiConnectAgentBridgeInitTests(unittest.TestCase):
    def setUp(self):
        self.config = PhiConnectConfig(
            peer_host="127.0.0.1",
            peer_port=9000,
            listen_port=9001,
        )

    def test_init_stores_config(self):
        bridge = PhiConnectAgentBridge(self.config)
        self.assertIs(bridge.config, self.config)

    def test_init_creates_default_client(self):
        bridge = PhiConnectAgentBridge(self.config)
        self.assertIsNotNone(bridge.client)

    def test_init_accepts_custom_client(self):
        client = MagicMock()
        bridge = PhiConnectAgentBridge(self.config, client=client)
        self.assertIs(bridge.client, client)

    def test_init_has_lock(self):
        bridge = PhiConnectAgentBridge(self.config)
        self.assertTrue(hasattr(bridge, "_lock"))


class PhiConnectAgentBridgeHandleMessageTests(unittest.TestCase):
    def setUp(self):
        self.config = PhiConnectConfig(
            peer_host="127.0.0.1",
            peer_port=9000,
            listen_port=9001,
        )

    def test_ignores_outbound_messages(self):
        bridge = PhiConnectAgentBridge(self.config)
        bridge.client = MagicMock()
        bridge.handle_message({
            "direction": "outbound",
            "ok": True,
            "body": "hello",
            "sender": "user",
        })
        bridge.client.ask.assert_not_called()

    def test_ignores_failed_messages(self):
        bridge = PhiConnectAgentBridge(self.config)
        bridge.client = MagicMock()
        bridge.handle_message({
            "direction": "inbound",
            "ok": False,
            "body": "hello",
            "sender": "user",
        })
        bridge.client.ask.assert_not_called()

    def test_ignores_fiona_prefixed_messages(self):
        bridge = PhiConnectAgentBridge(self.config)
        bridge.client = MagicMock()
        bridge.handle_message({
            "direction": "inbound",
            "ok": True,
            "body": "[Fiona] This is an automated response",
            "sender": "user",
        })
        bridge.client.ask.assert_not_called()

    def test_processes_user_message(self):
        bridge = PhiConnectAgentBridge(self.config)
        bridge.client = MagicMock()
        bridge.client.ask.return_value = "I processed your message"

        bridge.handle_message({
            "direction": "inbound",
            "ok": True,
            "body": "What is the weather?",
            "sender": "user",
        })

        bridge.client.ask.assert_called_once_with("What is the weather?")

    def test_process_and_reply_sends_response(self):
        bridge = PhiConnectAgentBridge(self.config)
        bridge.client = MagicMock()
        bridge.client.ask.return_value = "The weather is sunny"

        with patch("PhiConnect.bridge.send_chat_message") as mock_send:
            bridge._process_and_reply("weather?", "user")
            mock_send.assert_called_once()
            args, _ = mock_send.call_args
            self.assertIn("[Fiona]", args[0])
            self.assertIn("sunny", args[0])

    def test_process_and_reply_failure_logged(self):
        bridge = PhiConnectAgentBridge(self.config)
        bridge.client = MagicMock()
        bridge.client.ask.side_effect = Exception("API error")

        with patch("PhiConnect.bridge.logger") as mock_logger:
            bridge._process_and_reply("test", "user")
            mock_logger.error.assert_called_once()
            self.assertIn("API error", str(mock_logger.error.call_args))

    def test_handle_message_empty_body(self):
        bridge = PhiConnectAgentBridge(self.config)
        bridge.client = MagicMock()
        bridge.handle_message({
            "direction": "inbound",
            "ok": True,
            "body": "",
            "sender": "user",
        })

    def test_handle_message_whitespace_body(self):
        bridge = PhiConnectAgentBridge(self.config)
        bridge.client = MagicMock()
        bridge.handle_message({
            "direction": "inbound",
            "ok": True,
            "body": "   ",
            "sender": "user",
        })

    def test_handle_message_calls_thread(self):
        """The handler starts a thread so it returns immediately."""
        bridge = PhiConnectAgentBridge(self.config)
        bridge.client = MagicMock()
        bridge.client.ask.return_value = "reply"

        with patch("PhiConnect.bridge.threading.Thread") as mock_thread:
            bridge.handle_message({
                "direction": "inbound",
                "ok": True,
                "body": "hello",
                "sender": "user",
            })
            mock_thread.assert_called_once()
            kwargs = mock_thread.call_args[1]
            self.assertTrue(kwargs["daemon"])

    def test_missing_body_key_handled(self):
        """Missing body defaults to empty string, which gets processed."""
        bridge = PhiConnectAgentBridge(self.config)
        bridge.client = MagicMock()
        bridge.client.ask.return_value = "reply"
        with patch("PhiConnect.bridge.send_chat_message"):
            bridge.handle_message({
                "direction": "inbound",
                "ok": True,
                "sender": "user",
            })
            # Empty body does NOT start with "[Fiona]", so it gets processed
            bridge.client.ask.assert_called_once_with("")

    def test_missing_sender_key_handled(self):
        bridge = PhiConnectAgentBridge(self.config)
        bridge.client = MagicMock()
        bridge.client.ask.return_value = "reply"
        with patch("PhiConnect.bridge.send_chat_message"):
            bridge.handle_message({
                "direction": "inbound",
                "ok": True,
                "body": "hello",
            })
            bridge.client.ask.assert_called_once()

    def test_missing_ok_key_handled(self):
        """Missing 'ok' defaults to None, which is falsy, so message is ignored."""
        bridge = PhiConnectAgentBridge(self.config)
        bridge.client = MagicMock()
        bridge.handle_message({
            "direction": "inbound",
            "body": "hello",
            "sender": "user",
        })
        bridge.client.ask.assert_not_called()


if __name__ == "__main__":
    unittest.main()
