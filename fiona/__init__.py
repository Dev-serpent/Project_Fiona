"""Fiona umbrella package.

Fiona is split into sibling subsystems:

- QuikTieper: local access layer for keyboard, mouse, and app actions
- CamComs: communication and encrypted message transport
- Vsee: 3D coordinate hologram viewer
- Agent: local LM Studio bridge for the future agent layer
- PhiConnect: encrypted computer-to-computer chat
- SeeOnDesk: desktop-awareness snapshots
- DataClient: topic search, scraping, summarization, and CSV export
- EyeControl: optional camera-based eye-controlled mouse tracker
- TerminalAssist: btop-style terminal dashboard and Zellij workspace
- CmdTrace: command trace storage
- RecallVault: structured remembrance storage
- FionaCore: shared action router, permissions, notifications, voice, and macros
"""

from __future__ import annotations

import sys

import Agent as Agent
import CamComs as CamComs
import CmdTrace as CmdTrace
import DataClient as DataClient
import EyeControl as EyeControl
import FionaCore as FionaCore
import PhiConnect as PhiConnect
import QuikTieper as QuikTieper
import RecallVault as RecallVault
import SeeOnDesk as SeeOnDesk
import TerminalAssist as TerminalAssist
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
sys.modules.setdefault(__name__ + ".CmdTrace", CmdTrace)
sys.modules.setdefault(__name__ + ".DataClient", DataClient)
sys.modules.setdefault(__name__ + ".EyeControl", EyeControl)
sys.modules.setdefault(__name__ + ".FionaCore", FionaCore)
sys.modules.setdefault(__name__ + ".PhiConnect", PhiConnect)
sys.modules.setdefault(__name__ + ".QuikTieper", QuikTieper)
sys.modules.setdefault(__name__ + ".RecallVault", RecallVault)
sys.modules.setdefault(__name__ + ".SeeOnDesk", SeeOnDesk)
sys.modules.setdefault(__name__ + ".TerminalAssist", TerminalAssist)
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
    "CmdTrace",
    "DataClient",
    "EyeControl",
    "FionaCore",
    "PhiConnect",
    "SeeOnDesk",
    "TerminalAssist",
    "ChordListener",
    "PublicKeyBundle",
    "QuikTieper",
    "RecallVault",
    "Vsee",
    "decode_envelope",
    "decrypt_message",
    "decrypt_text",
    "encode_envelope",
    "encrypt_message",
    "send_encoded_message",
    "send_envelope",
]
