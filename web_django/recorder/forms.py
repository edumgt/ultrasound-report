from django import forms

from .models import RecordingSession


class RecordingSessionReviewForm(forms.ModelForm):
    class Meta:
        model = RecordingSession
        fields = ['patient_id', 'corrected_transcript', 'report_text', 'report_status']
        widgets = {
            'corrected_transcript': forms.Textarea(attrs={'rows': 8}),
            'report_text': forms.Textarea(attrs={'rows': 12}),
        }
