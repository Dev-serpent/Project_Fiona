"""Fiona umbrella package.

Fiona is split into sibling subsystems:

- QuikTieper: local access layer for keyboard, mouse, and app actions
- CamComs: communication and encrypted message transport
- Vsee: 3D coordinate hologram viewer
- Agent: local LM Studio bridge for the future agent layer
- PhiConnect: encrypted computer-to-computer chat
- SeeOnDesk: desktop-awareness snapshots
- DataClient: topic search, scraping, summarization, and CSV export
"""

from __future__ import annotations

import sys

import Agent as Agent
import CamComs as CamComs
import DataClient as DataClient
import PhiConnect as PhiConnect
import QuikTieper as QuikTieper
import SeeOnDesk as SeeOnDesk
import Vsee as Vsee
from CamComs import (
    CamComsCryptoError,
    CamComsHttpClient,
    CamComsIdentity,
    PublicKeyBundle,
    decode_envelope,
    decrypt_message,
    decrypt_text,
    encode_envelope,
    encrypt_message,
    send_encoded_message,
    send_envelope,
)
from QuikTieper import AppLauncher, Binding

sys.modules.setdefault(__name__ + ".CamComs", CamComs)
sys.modules.setdefault(__name__ + ".Agent", Agent)
sys.modules.setdefault(__name__ + ".DataClient", DataClient)
sys.modules.setdefault(__name__ + ".PhiConnect", PhiConnect)
sys.modules.setdefault(__name__ + ".QuikTieper", QuikTieper)
sys.modules.setdefault(__name__ + ".SeeOnDesk", SeeOnDesk)
sys.modules.setdefault(__name__ + ".Vsee", Vsee)


def __getattr__(name: str) -> object:
    if name == "ChordListener":
        from QuikTieper import ChordListener

        return ChordListener
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

__all__ = [
    "AppLauncher",
    "Agent",
    "Binding",
    "CamComs",
    "CamComsCryptoError",
    "CamComsHttpClient",
    "CamComsIdentity",
    "DataClient",
    "PhiConnect",
    "SeeOnDesk",
    "ChordListener",
    "PublicKeyBundle",
    "QuikTieper",
    "Vsee",
    "decode_envelope",
    "decrypt_message",
    "decrypt_text",
    "encode_envelope",
    "encrypt_message",
    "send_encoded_message",
    "send_envelope",
]
