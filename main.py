import sys
import pyaudio
import numpy as np
import webrtcvad
import time
import queue
import threading
import requests
from PyQt6.QtWidgets import QApplication, QLabel, QWidget
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer
from faster_whisper import WhisperModel

# ================= Configuration =================
CONFIG = {
    "whisper_model": "small",
    "sample_rate": 16000,
    "chunk_duration_ms": 30,
    "vad_mode": 1,
    "silence_trigger_ms": 150, # Optimized for faster sync
    "max_chunk_duration_s": 3.0, # Optimized for faster sync
    "ollama_api_url": "http://127.0.0.1:11434/api/generate",
    "ollama_model": "qwen2.5:3b",
    "system_prompt": "你是字幕翻译引擎。\n只输出中文翻译。\n不要解释。\n不要补充。\n不要改写语气。",
    "ui_width": 800,
    "ui_height": 90,
    "ui_bottom_margin": 100
}

# Derived configurations
_sample_rate = int(CONFIG["sample_rate"]) # type: ignore
_chunk_duration_ms = float(CONFIG["chunk_duration_ms"]) # type: ignore
_silence_trigger_ms = float(CONFIG["silence_trigger_ms"]) # type: ignore
_max_chunk_duration_s = float(CONFIG["max_chunk_duration_s"]) # type: ignore

CHUNK_SIZE = int(_sample_rate * _chunk_duration_ms / 1000)
SILENCE_CHUNKS_THRESHOLD = int(_silence_trigger_ms / _chunk_duration_ms)
MAX_CHUNKS = int(_max_chunk_duration_s * 1000 / _chunk_duration_ms)

# ================= Global Queues =================
audio_queue = queue.Queue()
# V2.0 Requirement: Translation queue size = 1 (discard old tasks)
translation_queue = queue.Queue(maxsize=1) 

# ================= UI Component =================
class SubtitleWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.initUI()

    def initUI(self):
        self.setWindowFlags(
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.Tool |
            Qt.WindowType.WindowTransparentForInput
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)

        self.label = QLabel("等待语音输入...", self)
        self.label.setStyleSheet("""
            QLabel {
                color: white;
                background-color: rgba(0, 0, 0, 150);
                font-size: 24px;
                padding: 10px;
                border-radius: 10px;
            }
        """)

        screen = QApplication.primaryScreen().geometry()
        x = (screen.width() - CONFIG["ui_width"]) // 2
        y = screen.height() - CONFIG["ui_height"] - CONFIG["ui_bottom_margin"]
        
        self.setGeometry(x, y, CONFIG["ui_width"], CONFIG["ui_height"])
        self.label.setGeometry(0, 0, CONFIG["ui_width"], CONFIG["ui_height"])
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.oldPos = self.pos()

    def update_text(self, zh_text, en_text):
        if zh_text or en_text:
            html = f"<div align='center' style='line-height:1.2;'>{zh_text}<br><span style='font-size:16px; color:#cccccc;'>{en_text}</span></div>"
            self.label.setText(html)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.oldPos = event.globalPosition().toPoint()

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.MouseButton.LeftButton:
            delta = event.globalPosition().toPoint() - self.oldPos
            self.move(self.pos() + delta)
            self.oldPos = event.globalPosition().toPoint()

# ================= Threads =================
class TranscriberThread(QThread):
    def run(self):
        print(f"[Whisper] Loading model '{CONFIG['whisper_model']}'...")
        model = WhisperModel(CONFIG["whisper_model"], device="cpu", compute_type="int8")
        print("[Whisper] Model loaded.")

        while True:
            audio_data = audio_queue.get()
            if audio_data is None: break
            
            if not isinstance(audio_data, np.ndarray): continue
            audio_float32 = audio_data.astype(np.float32) / 32768.0 # type: ignore
            
            start_t = time.time()
            segments, _ = model.transcribe(audio_float32, beam_size=5, language="en")
            text = "".join([s.text for s in segments]).strip()
            
            if text:
                print(f"[Whisper] {text} ({time.time()-start_t:.2f}s)")
                
                # Push to translation queue (discard old if full)
                try:
                    translation_queue.put_nowait(text)
                except queue.Full:
                    try:
                        _ = translation_queue.get_nowait() # drop old
                        translation_queue.put_nowait(text) # insert new
                        print("[System] Dropped old translation task.")
                    except queue.Empty:
                        translation_queue.put_nowait(text) # safe push

class TranslatorThread(QThread):
    translation_ready = pyqtSignal(str, str)
    
    def run(self):
        print("[Translator] Thread started.")
        while True:
            text = translation_queue.get()
            if text is None: break
            
            payload = {
                "model": CONFIG["ollama_model"],
                "prompt": f"English: {text}\nTranslation:",
                "system": CONFIG["system_prompt"],
                "stream": False,
                "options": {
                    "temperature": 0.0,
                    "top_p": 0.1,
                    "num_predict": 100
                }
            }
            
            start_t = time.time()
            try:
                resp = requests.post(
                    CONFIG["ollama_api_url"], 
                    json=payload, 
                    timeout=3.0,
                    proxies={"http": None, "https": None}
                )
                resp.raise_for_status()
                zh_text = resp.json().get("response", "").strip()
                print(f"[Ollama] {zh_text} ({time.time()-start_t:.2f}s)")
                self.translation_ready.emit(zh_text, str(text))  # Cast text to str for pyre issue
            except Exception as e:
                print(f"[Ollama Error] {e}")

class AudioCaptureThread(QThread):
    def __init__(self):
        super().__init__()
        self.p = pyaudio.PyAudio()
        self.vad = webrtcvad.Vad(CONFIG["vad_mode"])
        self.stream = None
        self.running = True

    def run(self):
        device_index = self.p.get_default_input_device_info()['index']
        for i in range(self.p.get_device_count()):
            info = self.p.get_device_info_by_index(i)
            if "BlackHole" in info.get('name') and info.get('maxInputChannels') > 0:
                device_index = i
                break

        print(f"[Audio] Capturing from device {device_index}")
        
        self.stream = self.p.open(format=pyaudio.paInt16, channels=1,
                                  rate=CONFIG["sample_rate"], input=True,
                                  input_device_index=device_index,
                                  frames_per_buffer=CHUNK_SIZE)
        
        current_buffer = []
        silence_counter = 0
        
        try:
            while self.running:
                if self.stream is None:
                    break
                data = self.stream.read(CHUNK_SIZE, exception_on_overflow=False) # type: ignore
                is_speech = self.vad.is_speech(data, CONFIG["sample_rate"])
                
                if is_speech:
                    silence_counter = 0
                    current_buffer.append(data)
                else:
                    silence_counter += 1
                    if current_buffer:
                        current_buffer.append(data)
                        
                force_cut = len(current_buffer) >= MAX_CHUNKS
                silence_cut = (silence_counter >= SILENCE_CHUNKS_THRESHOLD) and len(current_buffer) > 10
                
                if force_cut or silence_cut:
                    combined = b"".join(current_buffer)
                    audio_np = np.frombuffer(combined, dtype=np.int16)
                    audio_queue.put(audio_np.copy())
                    print(f"[Audio] VAD triggered (chunks: {len(current_buffer)}). Pushed to Whisper queue.")
                    
                    current_buffer = []
                    silence_counter = 0
        finally:
            self.stop()

    def stop(self):
        self.running = False
        if self.stream and self.stream.is_active():
            self.stream.stop_stream() # type: ignore
            self.stream.close() # type: ignore
        self.p.terminate()

import signal

# ================= Main =================
def main():
    app = QApplication(sys.argv)
    
    # Allow terminal Ctrl+C to penetrate the PyQt event loop
    signal.signal(signal.SIGINT, signal.SIG_DFL)
    timer = QTimer()
    timer.timeout.connect(lambda: None)
    timer.start(100)

    window = SubtitleWindow()
    window.show()

    transcriber_th = TranscriberThread()
    translator_th = TranslatorThread()
    translator_th.translation_ready.connect(window.update_text)
    
    transcriber_th.start()
    translator_th.start()
    
    audio_th = AudioCaptureThread()
    audio_th.start()

    print("\nSystem running. Press Ctrl+C in terminal to exit.")
    app.exec() # Wait for UI to close
    
    print("\nShutting down threads...")
    audio_th.stop()
    audio_th.wait() # QThread uses wait
    
    # Send poison pills
    audio_queue.put(None)
    translation_queue.put(None) # type: ignore
    
    transcriber_th.quit()
    transcriber_th.wait()
    translator_th.quit()
    translator_th.wait()
    print("Clean exit.")

if __name__ == '__main__':
    main()
