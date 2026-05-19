from django.contrib import admin

from .models import ManagedTerm, RecordingSession, ReportAuditLog, TermCorrectionLog


@admin.register(RecordingSession)
class RecordingSessionAdmin(admin.ModelAdmin):
    list_display = ('id', 'patient_id', 'domain', 'report_status', 'updated_at')
    list_filter = ('domain', 'report_status')
    search_fields = ('patient_id', 'raw_transcript', 'corrected_transcript', 'report_text')
    readonly_fields = ('created_at', 'updated_at', 'finalized_at')


@admin.register(TermCorrectionLog)
class TermCorrectionLogAdmin(admin.ModelAdmin):
    list_display = ('session', 'source_term', 'corrected_term', 'score', 'created_at')
    search_fields = ('source_term', 'corrected_term')


@admin.register(ReportAuditLog)
class ReportAuditLogAdmin(admin.ModelAdmin):
    list_display = ('session', 'action', 'user', 'created_at')
    list_filter = ('action',)


@admin.register(ManagedTerm)
class ManagedTermAdmin(admin.ModelAdmin):
    list_display = ('canonical', 'category', 'domain', 'is_active', 'updated_at')
    list_filter = ('category', 'domain', 'is_active')
    search_fields = ('key', 'canonical')
