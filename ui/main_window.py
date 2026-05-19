        from __future__ import annotations
        import os
        import datetime
        import multiprocessing as mp
        from queue import Empty

        from PySide6.QtCore import Qt, QTimer
        from PySide6.QtGui import QKeySequence, QShortcut
        from PySide6.QtWidgets import (
            QMainWindow, QTextEdit, QPushButton, QLabel, QVBoxLayout, QWidget,
            QHBoxLayout, QMessageBox
        )

        SAFE_MODE = os.environ.get('SAFE_MODE', '0') == '1'

        if not SAFE_MODE:
            from core.report_service import ReportService
            from core.runtime import detect_whisper_runtime
            from core.storage import save_session
            from core.stt_process import stt_worker_main


        class MainWindow(QMainWindow):
            def _log(self, msg: str):
                ts = datetime.datetime.now().strftime('%H:%M:%S')
                line = f'[{ts}] {msg}'
                print(line, flush=True)
                try:
                    with open(os.path.join(self.sessions_dir, 'ui_debug.log'), 'a', encoding='utf-8') as f:
                        f.write(line + '
')
                except Exception:
                    pass

            def _setup_ui_safe_only(self):
                self.setWindowTitle('Ultrasound Auto Report PoC (SAFE_MODE)')
                self.status_label = QLabel('SAFE_MODE=1 (UI only)')
                self.status_label.setAlignment(Qt.AlignLeft)
                self.text_live = QTextEdit()
                self.text_live.setReadOnly(True)
                self.text_live.setPlaceholderText('SAFE MODE: STT/Audio disabled. Close with Esc.')
                layout = QVBoxLayout()
                layout.addWidget(self.status_label)
                layout.addWidget(self.text_live)
                w = QWidget()
                w.setLayout(layout)
                self.setCentralWidget(w)

            def _setup_shortcuts_safe_only(self):
                QShortcut(QKeySequence('Esc'), self, activated=self.close)

            def __init__(self, assets_dir: str, sessions_dir: str):
                super().__init__()
                self.assets_dir = assets_dir
                self.sessions_dir = sessions_dir

                if SAFE_MODE:
                    self._setup_ui_safe_only()
                    self._setup_shortcuts_safe_only()
                    return

                self._ctx = mp.get_context('spawn')
                self.setWindowTitle('Ultrasound Auto Report PoC')
                self.status_label = QLabel('Idle')
                self.status_label.setAlignment(Qt.AlignLeft)
                self.text_live = QTextEdit()
                self.text_live.setReadOnly(True)
                self.text_live.setPlaceholderText('실시간 인식/보정 결과(누적)')
                self.text_edit = QTextEdit()
                self.text_edit.setPlaceholderText('사용자 수정 에디터(최종 리포트 생성 기준)')
                self.btn_toggle = QPushButton('Start/Stop (F2)')
                self.btn_reset = QPushButton('Reset (F3)')
                self.btn_report = QPushButton('Generate Report (Ctrl+Enter)')
                self.btn_save = QPushButton('Save Session (Ctrl+S)')
                self.btn_toggle.clicked.connect(self.toggle)
                self.btn_reset.clicked.connect(self.reset)
                self.btn_report.clicked.connect(self.generate_report)
                self.btn_save.clicked.connect(self.save)

                top = QHBoxLayout()
                top.addWidget(self.btn_toggle)
                top.addWidget(self.btn_reset)
                top.addWidget(self.btn_report)
                top.addWidget(self.btn_save)

                layout = QVBoxLayout()
                layout.addWidget(self.status_label)
                layout.addLayout(top)
                layout.addWidget(QLabel('Live (Auto-corrected)'))
                layout.addWidget(self.text_live)
                layout.addWidget(QLabel('Editable (Final)'))
                layout.addWidget(self.text_edit)
                w = QWidget()
                w.setLayout(layout)
                self.setCentralWidget(w)

                self.report_service = ReportService(self.assets_dir)
                prompt = self._build_prompt()
                lang = os.environ.get('STT_LANG', 'ko')
                runtime = detect_whisper_runtime()
                self._stt_cfg = dict(
                    model_size=os.environ.get('WHISPER_MODEL_SIZE', 'small'),
                    device=runtime.device,
                    compute_type=runtime.compute_type,
                    beam_size=int(os.environ.get('WHISPER_BEAM_SIZE', '5')),
                    vad_filter=os.environ.get('WHISPER_VAD_FILTER', '1') != '0',
                    language=None if lang == 'auto' else lang,
                    initial_prompt=prompt,
                    sample_rate=16000,
                    block_ms=400,
                )
                self._stt_proc: mp.Process | None = None
                self._out_q = None
                self._ctrl_q = None
                self._timer = QTimer(self)
                self._timer.setInterval(100)
                self._timer.timeout.connect(self._drain_out_queue)
                self._timer.start()
                QShortcut(QKeySequence('F2'), self, activated=self.toggle)
                QShortcut(QKeySequence('F3'), self, activated=self.reset)
                QShortcut(QKeySequence('Ctrl+Return'), self, activated=self.generate_report)
                QShortcut(QKeySequence('Ctrl+S'), self, activated=self.save)
                self.last_report = ''
                self.last_fhir_payload = {}

            def _build_prompt(self) -> str:
                ex_path = os.path.join(self.assets_dir, 'examples.txt')
                examples = ''
                if os.path.exists(ex_path):
                    with open(ex_path, 'r', encoding='utf-8') as f:
                        examples = f.read().strip()
                return (
                    'You are transcribing an ultrasound medical dictation.
'
                    'Korean and English mixed medical terms must be written in correct English spelling.
'
                    f'{examples}
'
                )

            def _start_stt_process(self):
                if self._stt_proc and self._stt_proc.is_alive():
                    return
                self.status_label.setText('Starting STT subprocess...')
                self._log('Starting STT subprocess...')
                self._out_q = self._ctx.Queue()
                self._ctrl_q = self._ctx.Queue()
                self._stt_proc = self._ctx.Process(target=stt_worker_main, args=(self._out_q, self._ctrl_q, self._stt_cfg), daemon=False)
                self._stt_proc.start()
                self._log(f'STT subprocess started pid={self._stt_proc.pid}')

            def _stop_stt_process(self):
                if not self._stt_proc:
                    return
                try:
                    if self._ctrl_q:
                        self._ctrl_q.put('STOP')
                except Exception:
                    pass
                self._stt_proc.join(timeout=3)
                if self._stt_proc.is_alive():
                    self._stt_proc.terminate()
                self._stt_proc = None
                self._out_q = None
                self._ctrl_q = None
                self.status_label.setText('Stopped.')

            def toggle(self):
                if self._stt_proc and self._stt_proc.is_alive():
                    self._stop_stt_process()
                else:
                    self._start_stt_process()

            def reset(self):
                self._stop_stt_process()
                self.text_live.clear()
                self.text_edit.clear()
                self.last_report = ''
                self.last_fhir_payload = {}
                self.status_label.setText('Reset.')

            def _drain_out_queue(self):
                if self._stt_proc is not None and (not self._stt_proc.is_alive()):
                    code = self._stt_proc.exitcode
                    self._log(f'STT subprocess exited. exitcode={code}')
                    self.status_label.setText(f'STT subprocess exited (code {code})')
                    self._stt_proc = None
                    self._out_q = None
                    self._ctrl_q = None
                    return
                if self._out_q is None:
                    return
                while True:
                    try:
                        msg = self._out_q.get_nowait()
                    except Empty:
                        break
                    except Exception as e:
                        self._log(f'Queue read error: {e!r}')
                        break
                    try:
                        mtype = msg.get('type')
                        if mtype == 'status':
                            s = msg.get('msg', '')
                            self.status_label.setText(s)
                            self._log(f'status: {s}')
                        elif mtype == 'error':
                            em = msg.get('msg', '')
                            self._log(f'error: {em}')
                            QMessageBox.critical(self, 'STT Error', em)
                        elif mtype == 'audio_level':
                            rms = msg.get('rms', 0.0)
                            self.status_label.setText(f'Listening... mic rms={rms:.4f}')
                        elif mtype == 'text':
                            text = msg.get('text', '')
                            if text:
                                corrected, _changes = self.report_service.correct_text(text)
                                self.text_live.append(corrected)
                                self.text_edit.append(corrected)
                                self._log(f'text: {corrected}')
                    except Exception as e:
                        self._log(f'Message handling error: {e!r}')
                return

            def generate_report(self):
                final_text = self.text_edit.toPlainText().strip()
                if not final_text:
                    self.status_label.setText('No text to report.')
                    return
                bundle = self.report_service.build_report_bundle(final_text)
                self.last_report = bundle['report_text']
                self.last_fhir_payload = bundle['fhir_payload']
                self.text_live.append('
--- [REPORT] ---
' + self.last_report + '
--- [/REPORT] ---
')
                self.status_label.setText('Report generated.')

            def save(self):
                final_text = self.text_edit.toPlainText().strip()
                if not final_text:
                    self.status_label.setText('Nothing to save.')
                    return
                bundle = self.report_service.build_report_bundle(final_text)
                folder = save_session(
                    base_dir=self.sessions_dir,
                    raw_text='',
                    corrected_text=bundle['corrected_text'],
                    report_text=bundle['report_text'],
                    structured=bundle['structured'],
                )
                self.status_label.setText(f'Saved session: {folder}')

            def closeEvent(self, event):
                self._stop_stt_process()
                super().closeEvent(event)
