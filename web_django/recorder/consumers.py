from __future__ import annotations

import asyncio
import tempfile
from pathlib import Path

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer

from core.runtime import detect_whisper_runtime
from core.stt_whisper import STTConfig, WhisperSTT

from .models import RecordingSession
from .services import append_audit_log, build_report_service, persist_session_outputs


class LiveTranscriptionConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        await self.accept()
        self.report_service = await database_sync_to_async(build_report_service)()
        self.runtime = detect_whisper_runtime()
        self.stt = await asyncio.to_thread(
            WhisperSTT,
            STTConfig(
                model_size='small',
                device=self.runtime.device,
                compute_type=self.runtime.compute_type,
                beam_size=5,
                vad_filter=True,
                language=None,
            ),
        )
        self.session = await database_sync_to_async(RecordingSession.objects.create)(report_status=RecordingSession.ReportStatus.DRAFT)
        self.full_transcript = ''
        await self.send_json({'event': 'connected', 'session_id': self.session.id, 'device': self.runtime.device})

    async def receive(self, text_data=None, bytes_data=None):
        if text_data:
            payload = self.decode_json(text_data)
            action = payload.get('action')
            if action == 'stop':
                await self._emit_preview(finalize=True)
                await self.send_json({'event': 'stopped', 'session_id': self.session.id})
            elif action == 'set_patient':
                self.session = await database_sync_to_async(self._set_patient)(payload.get('patient_id', ''))
                await self.send_json({'event': 'patient_updated', 'patient_id': self.session.patient_id})
            return
        if not bytes_data:
            return
        text = await asyncio.to_thread(self._transcribe_chunk, bytes_data)
        if not text:
            return
        corrected_text, _changes = self.report_service.correct_text(text)
        self.full_transcript = f'{self.full_transcript} {corrected_text}'.strip()
        await self._emit_preview(finalize=False)

    async def disconnect(self, close_code):
        if getattr(self, 'session', None):
            await database_sync_to_async(append_audit_log)(self.session, 'websocket_disconnect', None, {'close_code': close_code})

    def _transcribe_chunk(self, bytes_data: bytes) -> str:
        with tempfile.NamedTemporaryFile(suffix='.webm', delete=False) as tmp:
            tmp.write(bytes_data)
            temp_path = Path(tmp.name)
        try:
            segments, _info = self.stt.model.transcribe(
                str(temp_path),
                beam_size=self.stt.cfg.beam_size,
                vad_filter=self.stt.cfg.vad_filter,
                language=self.stt.cfg.language,
                initial_prompt=self.stt.cfg.initial_prompt,
            )
            return ' '.join(seg.text.strip() for seg in segments if getattr(seg, 'text', None)).strip()
        finally:
            temp_path.unlink(missing_ok=True)

    async def _emit_preview(self, finalize: bool) -> None:
        bundle = self.report_service.build_report_bundle(self.full_transcript)
        await database_sync_to_async(persist_session_outputs)(self.session, bundle, self.full_transcript)
        await database_sync_to_async(append_audit_log)(self.session, 'websocket_preview' if not finalize else 'websocket_finalize', None, {'finalize': finalize})
        await self.send_json(
            {
                'event': 'preview',
                'session_id': self.session.id,
                'corrected_transcript': bundle['corrected_text'],
                'report_text': bundle['report_text'],
                'structured': bundle['structured'],
                'fhir_json': bundle['fhir_payload'],
                'finalized': finalize,
            }
        )

    def _set_patient(self, patient_id: str) -> RecordingSession:
        self.session.patient_id = patient_id.strip()
        self.session.save(update_fields=['patient_id', 'updated_at'])
        return self.session
