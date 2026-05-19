from __future__ import annotations
from dataclasses import dataclass
from typing import Optional, List
import numpy as np
from faster_whisper import WhisperModel

from core.runtime import detect_whisper_runtime


@dataclass
class STTConfig:
    model_size: str = 'small'
    device: str = 'auto'
    compute_type: str = 'auto'
    beam_size: int = 5
    vad_filter: bool = True
    language: Optional[str] = None
    initial_prompt: str = ''


class WhisperSTT:
    def __init__(self, cfg: STTConfig):
        self.cfg = cfg
        runtime = detect_whisper_runtime() if cfg.device == 'auto' or cfg.compute_type == 'auto' else None
        device = runtime.device if runtime and cfg.device == 'auto' else cfg.device
        compute_type = runtime.compute_type if runtime and cfg.compute_type == 'auto' else cfg.compute_type
        self.model = WhisperModel(cfg.model_size, device=device, compute_type=compute_type)

    def transcribe(self, audio_f32: np.ndarray, sample_rate: int) -> str:
        segments, _info = self.model.transcribe(
            audio_f32,
            language=self.cfg.language,
            beam_size=self.cfg.beam_size,
            vad_filter=self.cfg.vad_filter,
            initial_prompt=self.cfg.initial_prompt,
        )
        parts: List[str] = []
        for seg in segments:
            if seg.text:
                parts.append(seg.text.strip())
        return ' '.join(parts).strip()
