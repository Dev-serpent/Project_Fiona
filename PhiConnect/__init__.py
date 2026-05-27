"""Encrypted computer-to-computer chat layer for Fiona."""

from PhiConnect.chat import (
    DEFAULT_PHICONNECT_DIR,
    DEFAULT_PHICONNECT_PORT,
    PhiConnectConfig,
    PhiConnectError,
    PhiConnectMessageProcessor,
    build_phiconnect_server,
    ensure_identity,
    read_recent_messages,
    run_phiconnect_receiver,
    send_chat_message,
    trust_public_key,
)

__all__ = [
    "DEFAULT_PHICONNECT_DIR",
    "DEFAULT_PHICONNECT_PORT",
    "PhiConnectConfig",
    "PhiConnectError",
    "PhiConnectMessageProcessor",
    "build_phiconnect_server",
    "ensure_identity",
    "read_recent_messages",
    "run_phiconnect_receiver",
    "send_chat_message",
    "trust_public_key",
]
