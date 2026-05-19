const startBtn = document.getElementById('startBtn');
const stopBtn = document.getElementById('stopBtn');
const uploadBtn = document.getElementById('uploadBtn');
const statusEl = document.getElementById('status');
const transcriptEl = document.getElementById('transcript');
const reportPreviewEl = document.getElementById('reportPreview');
const player = document.getElementById('player');
const serverResponseEl = document.getElementById('serverResponse');
const fhirResponseEl = document.getElementById('fhirResponse');
const patientIdEl = document.getElementById('patientId');

let mediaRecorder;
let mediaStream;
let audioChunks = [];
let recordedBlob = null;
let recognition;
let socket;
let activeSessionId = null;

const setStatus = (msg) => {
  statusEl.textContent = msg;
};

const initSpeechRecognition = () => {
  const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!SpeechRecognition) {
    return null;
  }
  const rec = new SpeechRecognition();
  rec.lang = 'ko-KR';
  rec.continuous = true;
  rec.interimResults = true;
  rec.onresult = (event) => {
    let text = '';
    for (let i = 0; i < event.results.length; i += 1) {
      text += event.results[i][0].transcript + ' ';
    }
    if (!transcriptEl.value.trim()) {
      transcriptEl.value = text.trim();
    }
  };
  return rec;
};

const connectSocket = () => {
  const protocol = window.location.protocol === 'https:' ? 'wss' : 'ws';
  socket = new WebSocket(`${protocol}://${window.location.host}/ws/live-transcription/`);
  socket.binaryType = 'arraybuffer';
  socket.onopen = () => {
    setStatus('실시간 전사 연결 완료');
    if (patientIdEl.value.trim()) {
      socket.send(JSON.stringify({ action: 'set_patient', patient_id: patientIdEl.value.trim() }));
    }
  };
  socket.onmessage = (event) => {
    const data = JSON.parse(event.data);
    if (data.event === 'connected') {
      activeSessionId = data.session_id;
      serverResponseEl.textContent = JSON.stringify(data, null, 2);
      return;
    }
    if (data.event === 'preview') {
      activeSessionId = data.session_id;
      transcriptEl.value = data.corrected_transcript || '';
      reportPreviewEl.value = data.report_text || '';
      fhirResponseEl.textContent = JSON.stringify(data.fhir_json || {}, null, 2);
      serverResponseEl.textContent = JSON.stringify(data.structured || {}, null, 2);
      return;
    }
    if (data.event === 'stopped') {
      setStatus(`실시간 세션 종료 (#${data.session_id})`);
    }
  };
  socket.onerror = () => setStatus('WebSocket 오류가 발생했습니다.');
};

startBtn.addEventListener('click', async () => {
  try {
    transcriptEl.value = '';
    reportPreviewEl.value = '';
    audioChunks = [];
    recordedBlob = null;
    connectSocket();
    mediaStream = await navigator.mediaDevices.getUserMedia({ audio: true });
    mediaRecorder = new MediaRecorder(mediaStream, { mimeType: 'audio/webm' });
    mediaRecorder.ondataavailable = async (event) => {
      if (event.data.size > 0) {
        audioChunks.push(event.data);
        if (socket && socket.readyState === WebSocket.OPEN) {
          const buffer = await event.data.arrayBuffer();
          socket.send(buffer);
        }
      }
    };
    mediaRecorder.onstop = () => {
      recordedBlob = new Blob(audioChunks, { type: 'audio/webm' });
      player.src = URL.createObjectURL(recordedBlob);
      uploadBtn.disabled = false;
      if (socket && socket.readyState === WebSocket.OPEN) {
        socket.send(JSON.stringify({ action: 'stop' }));
      }
    };
    mediaRecorder.start(1500);
    recognition = initSpeechRecognition();
    if (recognition) recognition.start();
    setStatus('녹음 중...');
    startBtn.disabled = true;
    stopBtn.disabled = false;
  } catch (err) {
    setStatus(`마이크 접근 실패: ${err.message}`);
  }
});

stopBtn.addEventListener('click', () => {
  if (mediaRecorder && mediaRecorder.state !== 'inactive') {
    mediaRecorder.stop();
  }
  if (mediaStream) {
    mediaStream.getTracks().forEach((track) => track.stop());
  }
  if (recognition) {
    recognition.stop();
  }
  setStatus('녹음 종료');
  startBtn.disabled = false;
  stopBtn.disabled = true;
});

uploadBtn.addEventListener('click', async () => {
  if (!recordedBlob) {
    setStatus('업로드할 녹음 파일이 없습니다.');
    return;
  }
  const form = new FormData();
  form.append('audio', recordedBlob, 'recorded_audio.webm');
  form.append('transcript', transcriptEl.value);
  form.append('patient_id', patientIdEl.value);
  try {
    const res = await fetch('/api/upload-audio/', {
      method: 'POST',
      headers: { 'X-CSRFToken': window.CSRF_TOKEN },
      body: form,
    });
    const data = await res.json();
    serverResponseEl.textContent = JSON.stringify(data, null, 2);
    if (data.report_text) {
      reportPreviewEl.value = data.report_text;
    }
    if (data.session_id) {
      activeSessionId = data.session_id;
    }
    setStatus(data.ok ? '서버 업로드 완료' : '업로드 실패');
  } catch (err) {
    setStatus(`업로드 오류: ${err.message}`);
  }
});
