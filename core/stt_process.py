from __future__ import annotations
import os
import time
import queue as pyqueue
import numpy as np

from core.runtime import detect_whisper_runtime


def stt_worker_main(out_q, ctrl_q, cfg: dict):
    os.environ.setdefault('CT2_FORCE_CPU_ISA', 'GENERIC')
    os.environ.setdefault('OMP_NUM_THREADS', '1')
    os.environ.setdefault('OPENBLAS_NUM_THREADS', '1')
    os.environ.setdefault('MKL_NUM_THREADS', '1')
    os.environ.setdefault('NUMEXPR_NUM_THREADS', '1')

    import sounddevice as sd
    from faster_whisper import WhisperModel

    sample_rate = int(cfg.get('sample_rate', 16000))
    block_ms = int(cfg.get('block_ms', 400))
    blocksize = int(sample_rate * (block_ms / 1000.0))

    runtime = detect_whisper_runtime()
    model_size = cfg.get('model_size', 'small')
    device = cfg.get('device', runtime.device)
    compute_type = cfg.get('compute_type', runtime.compute_type)
    beam_size = int(cfg.get('beam_size', 5))
    vad_filter = bool(cfg.get('vad_filter', True))
    initial_prompt = cfg.get('initial_prompt', '')

    language = cfg.get('language')
    env_lang = os.environ.get('STT_LANG')
    if env_lang:
        language = None if env_lang.lower() == 'auto' else env_lang

    input_device = cfg.get('input_device', None)
    try:
        if input_device is None and os.environ.get('INPUT_DEVICE'):
            input_device = int(os.environ['INPUT_DEVICE'])
    except Exception:
        input_device = None

    min_seconds = float(cfg.get('min_seconds', 2.0))
    target_samples = int(sample_rate * min_seconds)
    energy_threshold = float(cfg.get('energy_threshold', 0.004))

    out_q.put({'type': 'status', 'msg': f'Loading STT model ({model_size}, {device}/{compute_type}) in subprocess...'})
    try:
        model = WhisperModel(
            model_size,
            device=device,
            compute_type=compute_type,
            cpu_threads=1,
            num_workers=1,
        )
    except Exception as e:
        out_q.put({'type': 'error', 'msg': f'Failed to init WhisperModel: {e}'})
        return

    out_q.put({'type': 'status', 'msg': 'STT model loaded.'})
    audio_q: 'pyqueue.Queue[np.ndarray]' = pyqueue.Queue()
    running = True
    last_level_t = time.time()
    last_rms = 0.0

    def callback(indata, frames, t, status):
        nonlocal last_rms
        try:
            audio = np.squeeze(indata.copy()).astype(np.float32)
            if audio.size:
                last_rms = float(np.sqrt(np.mean(np.square(audio))))
            audio_q.put(audio)
        except Exception as e:
            try:
                out_q.put({'type': 'error', 'msg': f'audio callback error: {e}'})
            except Exception:
                pass

    try:
        stream = sd.InputStream(
            device=input_device,
            channels=1,
            samplerate=sample_rate,
            blocksize=blocksize,
            dtype='float32',
            callback=callback,
        )
        stream.start()
    except Exception as e:
        out_q.put({'type': 'error', 'msg': f'Failed to start InputStream: {e}'})
        return

    out_q.put({'type': 'status', 'msg': 'Listening (subprocess)...'})
    buffer: list[np.ndarray] = []
    empty_count = 0
    ok_count = 0

    try:
        while running:
            now = time.time()
            if now - last_level_t >= 1.0:
                out_q.put({'type': 'audio_level', 'rms': float(last_rms)})
                last_level_t = now

            try:
                cmd = ctrl_q.get_nowait()
                if cmd == 'STOP':
                    running = False
                    break
            except Exception:
                pass

            try:
                chunk = audio_q.get(timeout=0.2)
                buffer.append(chunk)
            except pyqueue.Empty:
                continue
            except Exception as e:
                out_q.put({'type': 'error', 'msg': f'audio queue error: {e}'})
                continue

            if sum(len(x) for x in buffer) < target_samples:
                continue

            audio = np.concatenate(buffer).astype(np.float32)
            buffer.clear()
            rms_now = float(np.sqrt(np.mean(np.square(audio))) if audio.size else 0.0)
            if rms_now < energy_threshold:
                out_q.put({'type': 'status', 'msg': f'Too quiet (rms={rms_now:.4f})'})
                continue

            peak = float(np.max(np.abs(audio))) if audio.size else 0.0
            if peak > 0:
                audio = (audio / peak).astype(np.float32)

            out_q.put({'type': 'status', 'msg': 'Transcribing...'})
            t0 = time.time()
            try:
                segments, _info = model.transcribe(
                    audio,
                    language=language,
                    beam_size=beam_size,
                    vad_filter=vad_filter,
                    initial_prompt=initial_prompt,
                )
            except Exception as e:
                out_q.put({'type': 'error', 'msg': f'transcribe error: {e}'})
                continue
            dt = time.time() - t0

            text = ' '.join(seg.text.strip() for seg in segments if getattr(seg, 'text', None)).strip()
            if text:
                ok_count += 1
                out_q.put({'type': 'status', 'msg': f'OK ({ok_count}) in {dt:.2f}s'})
                out_q.put({'type': 'text', 'text': text})
            else:
                empty_count += 1
                out_q.put({'type': 'status', 'msg': f'No speech ({empty_count}) in {dt:.2f}s'})
    finally:
        try:
            stream.stop()
            stream.close()
        except Exception:
            pass
        out_q.put({'type': 'status', 'msg': 'Stopped (subprocess).'})
