# Generated manually for repository task.
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='ManagedTerm',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('key', models.CharField(max_length=64, unique=True)),
                ('canonical', models.CharField(max_length=255)),
                ('aliases', models.JSONField(blank=True, default=list)),
                ('category', models.CharField(default='feature', max_length=32)),
                ('domain', models.CharField(default='generic', max_length=32)),
                ('is_active', models.BooleanField(default=True)),
                ('source', models.CharField(default='admin', max_length=32)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={'ordering': ['domain', 'category', 'canonical']},
        ),
        migrations.CreateModel(
            name='RecordingSession',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('patient_id', models.CharField(blank=True, max_length=64)),
                ('modality', models.CharField(default='ultrasound', max_length=32)),
                ('domain', models.CharField(default='generic', max_length=32)),
                ('raw_transcript', models.TextField(blank=True)),
                ('corrected_transcript', models.TextField(blank=True)),
                ('report_text', models.TextField(blank=True)),
                ('structured_json', models.JSONField(blank=True, default=dict)),
                ('fhir_json', models.JSONField(blank=True, default=dict)),
                ('audio_file', models.FileField(blank=True, upload_to='recordings/')),
                ('report_status', models.CharField(choices=[('draft', 'Draft'), ('review', 'Review'), ('final', 'Final')], default='draft', max_length=16)),
                ('finalized_at', models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='created_recording_sessions', to=settings.AUTH_USER_MODEL)),
                ('reviewed_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='reviewed_recording_sessions', to=settings.AUTH_USER_MODEL)),
            ],
            options={'ordering': ['-updated_at']},
        ),
        migrations.CreateModel(
            name='TermCorrectionLog',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('source_term', models.CharField(max_length=255)),
                ('corrected_term', models.CharField(max_length=255)),
                ('score', models.FloatField(default=0.0)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('session', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='correction_logs', to='recorder.recordingsession')),
            ],
            options={'ordering': ['created_at']},
        ),
        migrations.CreateModel(
            name='ReportAuditLog',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('action', models.CharField(max_length=64)),
                ('details', models.JSONField(blank=True, default=dict)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('session', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='audit_logs', to='recorder.recordingsession')),
                ('user', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
            ],
            options={'ordering': ['-created_at']},
        ),
    ]
