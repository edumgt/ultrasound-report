from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class WhisperRuntime:
    device: str
    compute_type: str


def detect_whisper_runtime() -> WhisperRuntime:
    forced_device = os.environ.get('WHISPER_DEVICE')
    forced_compute = os.environ.get('WHISPER_COMPUTE_TYPE')
    if forced_device:
        return WhisperRuntime(device=forced_device, compute_type=forced_compute or 'float16')

    try:
        import ctranslate2
        if getattr(ctranslate2, 'get_cuda_device_count', None) and ctranslate2.get_cuda_device_count() > 0:
            return WhisperRuntime(device='cuda', compute_type=forced_compute or 'float16')
    except Exception:
        pass

    return WhisperRuntime(device='cpu', compute_type=forced_compute or 'int8')
