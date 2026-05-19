from __future__ import annotations

import json
from pathlib import Path
from uuid import uuid4

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST

from .forms import RecordingSessionReviewForm
from .models import RecordingSession
from .services import append_audit_log, build_report_service, persist_session_outputs
from .tasks import process_recording_session_async


@require_GET
def index(request: HttpRequest) -> HttpResponse:
    query = request.GET.get('q', '').strip()
    status_filter = request.GET.get('status', '').strip()
    sessions = RecordingSession.objects.all()
    if query:
        sessions = sessions.filter(patient_id__icontains=query)
    if status_filter:
        sessions = sessions.filter(report_status=status_filter)
    return render(request, 'recorder/index.html', {'sessions': sessions[:20], 'query': query, 'status_filter': status_filter})


@require_GET
def session_detail(request: HttpRequest, session_id: int) -> HttpResponse:
    session = get_object_or_404(RecordingSession, pk=session_id)
    form = RecordingSessionReviewForm(instance=session)
    return render(request, 'recorder/session_detail.html', {'session': session, 'form': form})


@require_GET
def session_list_api(request: HttpRequest) -> JsonResponse:
    query = request.GET.get('q', '').strip()
    sessions = RecordingSession.objects.all()
    if query:
        sessions = sessions.filter(patient_id__icontains=query)
    data = [
        {
            'id': session.id,
            'patient_id': session.patient_id,
            'domain': session.domain,
            'report_status': session.report_status,
            'updated_at': session.updated_at.isoformat(),
        }
        for session in sessions[:50]
    ]
    return JsonResponse({'ok': True, 'results': data})


@require_GET
def session_detail_api(request: HttpRequest, session_id: int) -> JsonResponse:
    session = get_object_or_404(RecordingSession, pk=session_id)
    return JsonResponse(
        {
            'ok': True,
            'session': {
                'id': session.id,
                'patient_id': session.patient_id,
                'domain': session.domain,
                'raw_transcript': session.raw_transcript,
                'corrected_transcript': session.corrected_transcript,
                'report_text': session.report_text,
                'structured_json': session.structured_json,
                'fhir_json': session.fhir_json,
                'report_status': session.report_status,
            },
        }
    )


@require_POST
def upload_audio(request: HttpRequest):
    audio_file = request.FILES.get('audio')
    transcript = request.POST.get('transcript', '').strip()
    patient_id = request.POST.get('patient_id', '').strip()

    if audio_file is None:
        return JsonResponse({'ok': False, 'error': 'audio 파일이 없습니다.'}, status=400)

    recordings_dir = Path(settings.BASE_DIR) / 'recordings'
    recordings_dir.mkdir(parents=True, exist_ok=True)
    filename = f'{uuid4().hex}_{audio_file.name}'
    target = recordings_dir / filename
    with target.open('wb') as f:
        for chunk in audio_file.chunks():
            f.write(chunk)

    session = RecordingSession.objects.create(
        patient_id=patient_id,
        created_by=request.user if request.user.is_authenticated else None,
    )
    session.audio_file.name = str(target.relative_to(settings.BASE_DIR))
    session.save(update_fields=['audio_file'])

    if getattr(settings, 'CELERY_TASK_ALWAYS_EAGER', False) or request.POST.get('process_async') != '1':
        service = build_report_service()
        bundle = service.build_report_bundle(transcript)
        persist_session_outputs(session, bundle, transcript)
        append_audit_log(session, 'upload_audio', request.user, {'saved_file': session.audio_file.name})
    else:
        process_recording_session_async.delay(session.id, transcript)

    return JsonResponse(
        {
            'ok': True,
            'session_id': session.id,
            'saved_file': session.audio_file.name,
            'transcript': session.corrected_transcript or transcript,
            'report_text': session.report_text,
            'report_status': session.report_status,
            'message': '녹음 파일 업로드 완료',
        }
    )


@login_required
@require_POST
def session_review(request: HttpRequest, session_id: int) -> HttpResponse:
    session = get_object_or_404(RecordingSession, pk=session_id)
    form = RecordingSessionReviewForm(request.POST, instance=session)
    if not form.is_valid():
        return render(request, 'recorder/session_detail.html', {'session': session, 'form': form}, status=400)

    before = {'report_status': session.report_status, 'corrected_transcript': session.corrected_transcript, 'report_text': session.report_text}
    updated = form.save(commit=False)
    updated.reviewed_by = request.user
    if updated.report_status == RecordingSession.ReportStatus.FINAL:
        updated.finalized_at = timezone.now()
    service = build_report_service()
    bundle = service.build_report_bundle(updated.corrected_transcript)
    updated.domain = bundle['structured'].get('domain', 'generic')
    updated.report_text = updated.report_text or bundle['report_text']
    updated.structured_json = bundle['structured']
    updated.fhir_json = bundle['fhir_payload']
    updated.save()
    append_audit_log(updated, 'review_update', request.user, {'before': before, 'after': {'report_status': updated.report_status}})
    return redirect('session_detail', session_id=updated.id)


@login_required
@require_POST
def session_review_api(request: HttpRequest, session_id: int) -> JsonResponse:
    session = get_object_or_404(RecordingSession, pk=session_id)
    payload = json.loads(request.body or '{}')
    session.patient_id = payload.get('patient_id', session.patient_id)
    session.corrected_transcript = payload.get('corrected_transcript', session.corrected_transcript)
    session.report_text = payload.get('report_text', session.report_text)
    status = payload.get('report_status')
    if status in RecordingSession.ReportStatus.values:
        session.report_status = status
    if session.report_status == RecordingSession.ReportStatus.FINAL:
        session.finalized_at = timezone.now()
        session.reviewed_by = request.user
    service = build_report_service()
    bundle = service.build_report_bundle(session.corrected_transcript)
    session.domain = bundle['structured'].get('domain', session.domain)
    session.structured_json = bundle['structured']
    session.fhir_json = bundle['fhir_payload']
    session.save()
    append_audit_log(session, 'api_review_update', request.user, {'status': session.report_status})
    return JsonResponse({'ok': True, 'session_id': session.id, 'report_status': session.report_status})
