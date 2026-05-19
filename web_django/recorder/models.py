from __future__ import annotations

from django.conf import settings
from django.db import models


class RecordingSession(models.Model):
    class ReportStatus(models.TextChoices):
        DRAFT = 'draft', 'Draft'
        REVIEW = 'review', 'Review'
        FINAL = 'final', 'Final'

    patient_id = models.CharField(max_length=64, blank=True)
    modality = models.CharField(max_length=32, default='ultrasound')
    domain = models.CharField(max_length=32, default='generic')
    raw_transcript = models.TextField(blank=True)
    corrected_transcript = models.TextField(blank=True)
    report_text = models.TextField(blank=True)
    structured_json = models.JSONField(default=dict, blank=True)
    fhir_json = models.JSONField(default=dict, blank=True)
    audio_file = models.FileField(upload_to='recordings/', blank=True)
    report_status = models.CharField(max_length=16, choices=ReportStatus.choices, default=ReportStatus.DRAFT)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='created_recording_sessions')
    reviewed_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='reviewed_recording_sessions')
    finalized_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-updated_at']

    def __str__(self) -> str:
        return f'Session #{self.pk} ({self.patient_id or "no-patient"})'


class TermCorrectionLog(models.Model):
    session = models.ForeignKey(RecordingSession, on_delete=models.CASCADE, related_name='correction_logs')
    source_term = models.CharField(max_length=255)
    corrected_term = models.CharField(max_length=255)
    score = models.FloatField(default=0.0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']


class ReportAuditLog(models.Model):
    session = models.ForeignKey(RecordingSession, on_delete=models.CASCADE, related_name='audit_logs')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    action = models.CharField(max_length=64)
    details = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']


class ManagedTerm(models.Model):
    key = models.CharField(max_length=64, unique=True)
    canonical = models.CharField(max_length=255)
    aliases = models.JSONField(default=list, blank=True)
    category = models.CharField(max_length=32, default='feature')
    domain = models.CharField(max_length=32, default='generic')
    is_active = models.BooleanField(default=True)
    source = models.CharField(max_length=32, default='admin')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['domain', 'category', 'canonical']

    def __str__(self) -> str:
        return self.canonical
