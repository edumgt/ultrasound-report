from __future__ import annotations

import json
from pathlib import Path

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase
from django.urls import reverse

from core.measurement import normalize_measurements
from core.report_service import ReportService
from recorder.models import RecordingSession


class ReportServiceTests(TestCase):
    def test_measurement_normalization_and_structuring(self):
        assets_dir = Path(__file__).resolve().parents[2] / 'assets'
        service = ReportService(assets_dir)
        bundle = service.build_report_bundle('right robe hypo echoic nodule 약 1.5 센티')
        self.assertEqual(bundle['structured']['location'], 'Right Lobe')
        self.assertEqual(bundle['structured']['lesion'], 'Nodule')
        self.assertEqual(bundle['structured']['feature'], 'Hypoechoic')
        self.assertEqual(bundle['structured']['size'], '1.5cm')
        self.assertEqual(normalize_measurements('3 by 2 밀리'), '3×2mm')


class RecorderViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = get_user_model().objects.create_user(username='reviewer', password='secret123')

    def test_upload_audio_creates_session(self):
        audio = SimpleUploadedFile('sample.webm', b'RIFF....fake-audio', content_type='audio/webm')
        response = self.client.post(reverse('upload_audio'), {'audio': audio, 'transcript': 'left robe cyst 3 by 2 밀리', 'patient_id': 'P-1'})
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload['ok'])
        self.assertTrue(RecordingSession.objects.filter(patient_id='P-1').exists())

    def test_review_api_requires_login(self):
        session = RecordingSession.objects.create(patient_id='P-2')
        response = self.client.post(reverse('session_review_api', args=[session.id]), data=json.dumps({'report_status': 'final'}), content_type='application/json')
        self.assertEqual(response.status_code, 302)
        self.client.login(username='reviewer', password='secret123')
        response = self.client.post(reverse('session_review_api', args=[session.id]), data=json.dumps({'corrected_transcript': 'Right Lobe Nodule 1cm', 'report_status': 'final'}), content_type='application/json')
        self.assertEqual(response.status_code, 200)
        session.refresh_from_db()
        self.assertEqual(session.report_status, RecordingSession.ReportStatus.FINAL)
