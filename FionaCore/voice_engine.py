from __future__ import annotations

import io
import time
import wave
from dataclasses import dataclass
from typing import Any

import numpy as np

try:
    import sounddevice as sd
    from faster_whisper import WhisperModel
    HAS_VOICE_DEPS = True
except ImportError:
    HAS_VOICE_DEPS = False


@dataclass
class WhisperEngine:
    model_size: str = "tiny"
    device: str = "cpu"
    compute_type: str = "int8"
    cpu_threads: int = 4
    
    _model: WhisperModel | None = None

    def _ensure_model(self) -> WhisperModel:
        if not HAS_VOICE_DEPS:
            raise RuntimeError("Voice dependencies (faster-whisper, sounddevice) are not installed.")
        
        if self._model is None:
            self._model = WhisperModel(
                self.model_size,
                device=self.device,
                compute_type=self.compute_type,
                cpu_threads=self.cpu_threads,
            )
        return self._model

    def transcribe_audio_buffer(self, audio_data: np.ndarray, sample_rate: int = 16000) -> str:
        model = self._ensure_model()
        
        # Convert numpy array to WAV in-memory
        buffer = io.BytesIO()
        with wave.open(buffer, 'wb') as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2) # 16-bit
            wf.setframerate(sample_rate)
            wf.writeframes(audio_data.tobytes())
        buffer.seek(0)
        
        segments, _ = model.transcribe(buffer, beam_size=5, vad_filter=True)
        text = " ".join([segment.text for segment in segments]).strip()
        return text

    def listen_and_transcribe(self, duration_seconds: float = 5.0, sample_rate: int = 16000) -> str:
        if not HAS_VOICE_DEPS:
            raise RuntimeError("Voice dependencies are not installed.")
            
        # Record audio
        # dtype='int16' matches Whisper expectation after conversion
        recording = sd.rec(
            int(duration_seconds * sample_rate),
            samplerate=sample_rate,
            channels=1,
            dtype='int16'
        )
        sd.wait()
        
        return self.transcribe_audio_buffer(recording, sample_rate)


def quick_transcribe(phrase_seconds: float = 3.0) -> str:
    """Helper for one-shot command listening."""
    engine = WhisperEngine()
    return engine.listen_and_transcribe(duration_seconds=phrase_seconds)
