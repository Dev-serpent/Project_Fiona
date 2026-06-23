"""Voice API endpoints.

Wraps FionaCore.parse_voice_command() and FionaCore.WhisperEngine.
"""

from __future__ import annotations

import base64
import logging
from typing import Any

import numpy as np
from aiohttp.web import Request, Response, json_response

from FionaCore import WhisperEngine, parse_voice_command

from fionaLocalPages.server.middleware import ApiError

logger = logging.getLogger(__name__)

_whisper: WhisperEngine | None = None


def _get_whisper() -> WhisperEngine:
    global _whisper  # noqa: PLW0603
    if _whisper is None:
        _whisper = WhisperEngine()
    return _whisper


# ── Handlers ───────────────────────────────────────────────────────────────


async def voice_parse(request: Request) -> Response:
    """POST /api/v1/voice/parse

    Body: { phrase }
    """
    try:
        body: dict[str, Any] = await request.json()
    except Exception:
        raise ApiError(400, "Invalid JSON body")

    phrase: str | None = body.get("phrase")
    if not phrase:
        raise ApiError(400, "Missing required field: phrase")

    try:
        result = parse_voice_command(phrase)
        if result is None:
            return json_response({
                "ok": True,
                "data": {"matched": False, "text": phrase},
            })
        return json_response({
            "ok": True,
            "data": result.to_dict(),
        })
    except Exception as exc:
        logger.exception("Voice parse failed")
        raise ApiError(500, str(exc)) from exc


async def voice_transcribe(request: Request) -> Response:
    """POST /api/v1/voice/transcribe

    Body: { audio_data }  — base64-encoded WAV audio (16kHz, mono, 16-bit)
    """
    try:
        body: dict[str, Any] = await request.json()
    except Exception:
        raise ApiError(400, "Invalid JSON body")

    audio_b64: str | None = body.get("audio_data")
    if not audio_b64:
        raise ApiError(400, "Missing required field: audio_data")

    try:
        raw_bytes = base64.b64decode(audio_b64)
        audio_array = np.frombuffer(raw_bytes, dtype=np.int16).astype(np.float32) / 32768.0

        engine = _get_whisper()
        text = engine.transcribe_audio_buffer(audio_array, sample_rate=16000)
        return json_response({
            "ok": True,
            "data": {"text": text},
        })
    except RuntimeError as exc:
        raise ApiError(501, str(exc)) from exc
    except Exception as exc:
        logger.exception("Voice transcription failed")
        raise ApiError(500, str(exc)) from exc
