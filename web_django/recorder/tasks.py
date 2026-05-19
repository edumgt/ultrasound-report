from __future__ import annotations

from celery import shared_task

from .models import RecordingSession
from .services import append_audit_log, build_report_service, persist_session_outputs


@shared_task
def process_recording_session_async(session_id: int, transcript: str) -> dict:
    session = RecordingSession.objects.get(pk=session_id)
    service = build_report_service()
    bundle = service.build_report_bundle(transcript)
    persist_session_outputs(session, bundle, transcript)
    append_audit_log(session, 'celery_process', None, {'async': True})
    return {'session_id': session.id, 'report_status': session.report_status}
