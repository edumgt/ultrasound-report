from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

from core.report_service import ReportService
from core.term_correction import TermCorrector

from .models import ManagedTerm, RecordingSession, ReportAuditLog, TermCorrectionLog

ROOT_DIR = Path(__file__).resolve().parents[2]
ASSETS_DIR = ROOT_DIR / 'assets'


def build_term_payload() -> Dict[str, Any]:
    payload = TermCorrector.read_payload(ASSETS_DIR / 'terms.json')
    categories = payload.get('categories', {})
    terms = {item['key']: item for item in payload.get('terms', [])}
    for managed in ManagedTerm.objects.filter(is_active=True):
        terms[managed.key] = {
            'key': managed.key,
            'canonical': managed.canonical,
            'aliases': managed.aliases,
        }
        categories.setdefault(managed.category, [])
        if managed.key not in categories[managed.category]:
            categories[managed.category].append(managed.key)
        categories.setdefault('domains', {})
        domain_terms = categories['domains'].setdefault(managed.domain, [])
        if managed.key not in domain_terms:
            domain_terms.append(managed.key)
    return {'terms': list(terms.values()), 'categories': categories}


def build_report_service() -> ReportService:
    return ReportService(ASSETS_DIR, term_payload=build_term_payload())


def persist_session_outputs(session: RecordingSession, bundle: Dict[str, Any], raw_transcript: str) -> RecordingSession:
    session.domain = bundle['structured'].get('domain', 'generic')
    session.raw_transcript = raw_transcript
    session.corrected_transcript = bundle['corrected_text']
    session.report_text = bundle['report_text']
    session.structured_json = bundle['structured']
    session.fhir_json = bundle['fhir_payload']
    session.save()

    session.correction_logs.all().delete()
    TermCorrectionLog.objects.bulk_create(
        [
            TermCorrectionLog(
                session=session,
                source_term=change['from'],
                corrected_term=change['to'],
                score=change.get('score', 0.0),
            )
            for change in bundle['changes']
        ]
    )
    return session


def append_audit_log(session: RecordingSession, action: str, user, details: Dict[str, Any] | None = None) -> None:
    ReportAuditLog.objects.create(session=session, user=user if getattr(user, 'is_authenticated', False) else None, action=action, details=details or {})
