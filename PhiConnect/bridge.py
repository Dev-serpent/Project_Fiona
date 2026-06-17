from __future__ import annotations

import logging
import threading
from typing import Any

from Agent.ollama import OllamaClient
from PhiConnect.chat import PhiConnectConfig, send_chat_message

logger = logging.getLogger(__name__)


class PhiConnectAgentBridge:
    def __init__(self, config: PhiConnectConfig, client: OllamaClient | None = None) -> None:
        self.config = config
        self.client = client or OllamaClient()
        self._lock = threading.Lock()

    def handle_message(self, event: dict[str, Any]) -> None:
        """
        Handle an inbound message event and potentially reply with the agent.
        """
        if event.get("direction") != "inbound" or not event.get("ok"):
            return

        body = event.get("body", "").strip()
        sender = event.get("sender", "")

        # If the message is from us (loopback), we might want to ignore it 
        # unless we specifically want to talk to ourselves.
        # However, in PhiConnect loopback test, sender == recipient.
        
        # Let's assume any inbound message that doesn't start with "[Fiona]" is a user message.
        if body.startswith("[Fiona]"):
            return

        # Start a thread to not block the receiver
        threading.Thread(
            target=self._process_and_reply,
            args=(body, sender),
            daemon=True
        ).start()

    def _process_and_reply(self, body: str, sender: str) -> None:
        with self._lock:
            try:
                logger.info(f"Agent bridge processing message from {sender}: {body}")
                response = self.client.ask(body)
                reply_body = f"[Fiona] {response}"
                
                # Send reply back. 
                # Note: This currently uses the peer_host/port from config.
                # In a loopback scenario, this works perfectly.
                send_chat_message(reply_body, config=self.config)
            except Exception as exc:
                logger.error(f"Agent bridge failed to reply: {exc}")
