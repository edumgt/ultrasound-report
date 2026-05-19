from django.urls import path

from recorder.consumers import LiveTranscriptionConsumer

websocket_urlpatterns = [
    path('ws/live-transcription/', LiveTranscriptionConsumer.as_asgi()),
]
