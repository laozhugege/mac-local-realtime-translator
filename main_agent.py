import sys
import os
import multiprocessing
import logging
import traceback
import collections
import pyaudio # type: ignore
import numpy as np # type: ignore
import webrtcvad # type: ignore
import time
import queue
import threading
import requests # type: ignore
from PyQt6.QtWidgets import QApplication, QLabel, QWidget, QSystemTrayIcon, QMenu, QMessageBox # type: ignore
from PyQt6.QtGui import QIcon, QAction, QActionGroup, QPixmap, QPainter, QColor, QFont # type: ignore
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer, QPoint # type: ignore
from faster_whisper import WhisperModel # type: ignore

# ================= Logging & Error Handling =================
LOG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "realtime_agent.log")
logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)

def exception_hook(exctype, value, tb):
    err_msg = "".join(traceback.format_exception(exctype, value, tb))
    logging.error(f"Unhandled Exception:\n{err_msg}")
    print(err_msg, file=sys.stderr)
    # Optional: show a dialog
    # QMessageBox.critical(None, "Fatal Error", err_msg)

sys.excepthook = exception_hook

# ================= Configuration =================
CONFIG = {
    "whisper_model": "small",
    "sample_rate": 16000,
    "chunk_duration_ms": 30,
    "vad_mode": 1,
    "silence_trigger_ms": 150, # Reverted: Optimized for video speech (not music)
    "max_chunk_duration_s": 3.0, # Reverted: 3s gives complete clauses for speech
    "ollama_api_url": "http://127.0.0.1:11434/api/generate",
    "ollama_model": "qwen2.5:7b",
    # ADOPTED from video-subtitle-generator/translator.py (proven high-quality)
    "system_prompt": (
        "You are a professional subtitle translator.\n"
        "Translate the following text into natural, fluent Chinese (Simplified).\n"
        "Do NOT include any explanations, transliterations, or original text in your output.\n"
        "Just provide the pure Chinese translation. If the text is already in Chinese, just output it as is."
    ),
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
translation_queue = queue.Queue(maxsize=5)  # Increased from 1 to prevent dropped segments

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

        self.label = QLabel("Waiting for speech... (Start from Menu 📝)", self)
        self.label.setStyleSheet("""
            QLabel {
                color: white;
                background-color: rgba(28, 28, 30, 200);
                font-family: '-apple-system', 'SF Pro Text', 'Helvetica Neue', sans-serif;
                font-size: 24px;
                padding: 10px;
                border-radius: 12px;
                border: 1px solid rgba(255, 255, 255, 20);
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
            html = f"<div align='center' style='line-height:1.2; font-weight: bold;'>{zh_text}<br><span style='font-size:16px; color:#aeaeb2; font-weight: normal;'>{en_text}</span></div>"
            self.label.setText(html)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.oldPos = event.globalPosition().toPoint()

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.MouseButton.LeftButton:
            delta = event.globalPosition().toPoint() - self.oldPos
            self.move(self.pos() + delta)
            self.oldPos = event.globalPosition().toPoint()

# Whisper hallucination detection: substring patterns (case-insensitive)
HALLUCINATION_PATTERNS = [
    "thank you", "thanks for watching", "please subscribe", 
    "bye bye", "bye.", "subtitles by", "don't forget to like",
    "see you in the next", "i'll be right back",
    "set to continue", "mbc",
]

# Chinese hallucination patterns (for Ollama output filtering)
ZH_HALLUCINATION_PATTERNS = [
    "感谢观看", "谢谢观看", "别忘了点赞", "请订阅", "下次再见",
    "我马上回来", "广告之后",
]

def is_whisper_hallucination(text: str, processing_time: float) -> bool:
    """Check if Whisper output is likely a hallucination."""
    t = text.strip().lower()
    # Single character or empty
    if len(t) <= 1:
        return True
    # Only punctuation
    if all(c in '.,!?…-' for c in t):
        return True
    # Substring pattern match
    for pattern in HALLUCINATION_PATTERNS:
        if pattern in t:
            return True
    # If Whisper took >5s on a single chunk, it's likely processing silence
    if processing_time > 5.0:
        return True
    return False

def is_zh_hallucination(zh_text: str) -> bool:
    """Check if Ollama output contains hallucinated Chinese phrases."""
    for pattern in ZH_HALLUCINATION_PATTERNS:
        if pattern in zh_text:
            return True
    return False

class TranscriberThread(QThread):
    def run(self):
        print(f"[Whisper] Loading model '{CONFIG['whisper_model']}'...")
        try:
            model = WhisperModel(CONFIG["whisper_model"], device="cpu", compute_type="int8")
            print("[Whisper] Model loaded.")
        except Exception as e:
            print(f"[Whisper] Failed to load model: {e}")
            return

        while True:
            audio_data = audio_queue.get()
            if audio_data is None: break # Exit signal
            
            if not isinstance(audio_data, np.ndarray): continue
            audio_float32 = audio_data.astype(np.float32) / 32768.0 # type: ignore
            
            start_t = time.time()
            # beam_size=5 adopted from video-subtitle-generator (higher accuracy)
            segments, _ = model.transcribe(audio_float32, beam_size=5, language="en")
            text = "".join([s.text for s in segments]).strip()
            processing_time = time.time() - start_t
            
            # HALLUCINATION FILTER (substring + timing based)
            if text:
                if is_whisper_hallucination(text, processing_time):
                    print(f"[Whisper] Filtered hallucination: '{text}' ({processing_time:.2f}s)")
                    continue

                print(f"[Whisper] {text} ({processing_time:.2f}s)")
                try:
                    translation_queue.put_nowait(text)
                except queue.Full:
                    try:
                        _ = translation_queue.get_nowait()
                        translation_queue.put_nowait(text)
                    except queue.Empty:
                        translation_queue.put_nowait(text)

class TranslatorThread(QThread):
    translation_ready = pyqtSignal(str, str)
    
    def __init__(self):
        super().__init__()
        # Bilingual context: list of (en, zh) tuples
        self.context_pairs: list[tuple[str, str]] = []
        # Short-segment accumulator
        self.pending_fragment = ""

    def run(self):
        print("[Translator] Thread started.")
        while True:
            text = translation_queue.get()
            if text is None: break # Exit signal
            
            en_text = str(text).strip()
            if not en_text:
                continue
            
            # SHORT-SEGMENT MERGING: accumulate very short fragments
            # e.g. "work." or "blues in A." are too short for good translation alone
            words = en_text.split()
            has_ending = en_text[-1] in '.?!' if en_text else False
            
            if len(words) <= 3 and not has_ending and not self.pending_fragment:
                # Too short and no punctuation — hold it for next segment
                self.pending_fragment = en_text
                print(f"[Translator] Holding short fragment: '{en_text}'")
                continue
            
            # Merge any pending fragment
            if self.pending_fragment:
                en_text = self.pending_fragment + " " + en_text
                self.pending_fragment = ""
                print(f"[Translator] Merged -> '{en_text}'")

            # Build BILINGUAL context: show both EN and ZH of recent segments
            context_lines = []
            for en, zh in self.context_pairs[-3:]:  # type: ignore
                context_lines.append(f"EN: {en}")
                context_lines.append(f"ZH: {zh}")
            
            if context_lines:
                context_block = "\n".join(context_lines)
                full_prompt = f"[Translation history for context:]\n{context_block}\n\n[Now translate this new segment:]\n{en_text}"
            else:
                full_prompt = en_text
            
            system_msg = str(CONFIG["system_prompt"])
            
            payload = {
                "model": str(CONFIG["ollama_model"]),
                "prompt": full_prompt,
                "system": system_msg,
                "stream": False,
                "options": {
                    "temperature": 0.0,
                    "top_p": 0.1
                }
            }
            
            start_t = time.time()
            try:
                resp = requests.post(
                    CONFIG["ollama_api_url"], 
                    json=payload, 
                    timeout=10.0,
                    proxies={"http": None, "https": None}
                )
                resp.raise_for_status()
                zh_text = resp.json().get("response", "").strip()
                
                # Filter garbage output + Chinese hallucinations
                if zh_text and not zh_text.startswith("[") and not zh_text.startswith("Translate") and not is_zh_hallucination(zh_text):
                    print(f"[Ollama] {zh_text} ({time.time()-start_t:.2f}s)")
                    self.translation_ready.emit(zh_text, en_text)
                    
                    # Store bilingual pair for future context
                    self.context_pairs.append((en_text, zh_text))
                    if len(self.context_pairs) > 5:
                        self.context_pairs = self.context_pairs[-5:]  # type: ignore
                else:
                    print(f"[Ollama] Filtered bad output: {zh_text}")
                    
            except requests.exceptions.Timeout:
                print(f"[Ollama] Timeout ({time.time()-start_t:.2f}s) - skipping")
            except Exception as e:
                print(f"[Ollama Error] {e}")

class AudioCaptureThread(QThread):
    error_signal = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.p = pyaudio.PyAudio()
        self.vad = webrtcvad.Vad(CONFIG["vad_mode"])
        self.stream = None
        self.running = True

    def run(self):
        device_index = self.p.get_default_input_device_info()['index']
        blackhole_found = False
        for i in range(self.p.get_device_count()):
            info = self.p.get_device_info_by_index(i)
            if "BlackHole" in info.get('name') and info.get('maxInputChannels') > 0:
                device_index = i
                blackhole_found = True
                break

        if not blackhole_found:
            self.error_signal.emit("BlackHole not found! Capturing from default mic instead. Please set aggregate device.")

        print(f"[Audio] Capturing from device {device_index}")
        
        try:
            self.stream = self.p.open(format=pyaudio.paInt16, channels=1,
                                      rate=CONFIG["sample_rate"], input=True,
                                      input_device_index=device_index,
                                      frames_per_buffer=CHUNK_SIZE)
        except Exception as e:
            self.error_signal.emit(f"Failed to open audio stream: {e}")
            return
            
        current_buffer = []
        silence_counter: int = 0
        
        try:
            while self.running:
                if self.stream is None:
                    break
                try:
                    data = self.stream.read(CHUNK_SIZE, exception_on_overflow=False) # type: ignore
                except Exception:
                    continue
                    
                is_speech = self.vad.is_speech(data, CONFIG["sample_rate"])
                
                if is_speech:
                    silence_counter = 0
                    current_buffer.append(data)
                else:
                    import typing
                    sc_val = typing.cast(int, silence_counter)
                    silence_counter = sc_val + 1
                    if current_buffer:
                        current_buffer.append(data)
                        
                force_cut = len(current_buffer) >= int(MAX_CHUNKS)
                silence_cut = (int(silence_counter) >= int(SILENCE_CHUNKS_THRESHOLD)) and len(current_buffer) > 10
                
                if force_cut or silence_cut:
                    combined = b"".join(current_buffer)
                    audio_np = np.frombuffer(combined, dtype=np.int16)
                    audio_queue.put(audio_np.copy())
                    current_buffer = []
                    silence_counter = 0
        finally:
            # Clean up stream resources here (in the worker thread, not stop())
            if self.stream:
                try:
                    self.stream.stop_stream()  # type: ignore
                    self.stream.close()  # type: ignore
                except Exception:
                    pass
            try:
                self.p.terminate()
            except Exception:
                pass

    def stop(self):
        # Only set flag — stream cleanup happens in run()'s finally block
        self.running = False

# ================= System Tray Agent =================
class MenuBarAgent(QSystemTrayIcon):
    def __init__(self, app, window, transcriber, translator):
        # Initialize without positional arguments to satisfy strict linters
        super().__init__()
        self.setParent(app)
        self.setIcon(QIcon())
        self.app = app
        self.window = window
        self.transcriber = transcriber
        self.translator = translator
        self.audio_thread = None
        
        # Create a High-Visibility custom icon
        self.update_icon()
        self.setToolTip("Subtitle Translator Agent")

        # Create menu
        self.menu = QMenu() # No parent needed if it's set as context menu, but app is safer 
        self.menu.setMinimumWidth(180)
        
        # Start/Stop Action
        self.start_action = QAction("▶ Start Translation", self)
        self.start_action.triggered.connect(self.toggle_translation)
        self.menu.addAction(self.start_action)
        
        self.menu.addSeparator()
        
        # Settings Menu (Dynamic)
        self.settings_menu = QMenu("⚙️ Settings", self.menu)
        self.menu.addMenu(self.settings_menu)
        
        # Whisper Menu
        self.whisper_menu = QMenu("ASR Model (Whisper)", self.settings_menu)
        self.settings_menu.addMenu(self.whisper_menu)
        self.whisper_group = QActionGroup(self)
        for model in ["tiny", "base", "small"]:
            action = QAction(model, self, checkable=True)
            if model == CONFIG["whisper_model"]:
                action.setChecked(True)
            action.triggered.connect(lambda checked, m=model: self.change_whisper(m))
            self.whisper_group.addAction(action)
            self.whisper_menu.addAction(action)
            
        # Ollama Menu
        self.ollama_menu = QMenu("LLM Translate (Ollama)", self.settings_menu)
        self.settings_menu.addMenu(self.ollama_menu)
        self.ollama_group = QActionGroup(self)
        self.load_ollama_models()
        self.settings_menu.addSeparator()
        
        self.menu.addSeparator()
        
        # Quit
        quit_action = QAction("Quit", self)
        quit_action.triggered.connect(self.quit_app)
        self.menu.addAction(quit_action)
        
        self.setContextMenu(self.menu)

    def update_icon(self):
        pixmap = QPixmap(32, 32)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Draw a rounded blue square
        painter.setBrush(QColor("#0a84ff")) # macOS accent blue
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(2, 2, 28, 28, 6, 6)
        
        # Draw initials
        painter.setPen(QColor("white"))
        font = QFont("Arial", 16, QFont.Weight.Bold)
        painter.setFont(font)
        painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, "T")
        painter.end()
        self.setIcon(QIcon(pixmap))

    def load_ollama_models(self):
        try:
            resp = requests.get("http://127.0.0.1:11434/api/tags", timeout=2.0)
            if resp.status_code == 200:
                models = [m["name"] for m in resp.json().get("models", [])]
                if not models:
                    models = ["qwen2.5:3b (fallback)"]
            else:
                models = ["qwen2.5:3b (fallback)"]
        except Exception:
            models = ["qwen2.5:3b (fallback)"]
            
        for model in models:
            m_str = str(model)
            action = QAction(m_str, self, checkable=True)
            if m_str.startswith(str(CONFIG["ollama_model"])):
                action.setChecked(True)
            action.triggered.connect(lambda checked, m=m_str: self.change_ollama(m))
            self.ollama_group.addAction(action)
            self.ollama_menu.addAction(action)

    def change_whisper(self, model_name):
        print(f"Applying new Whisper Model (Requires Restart): {model_name}")
        CONFIG["whisper_model"] = model_name

    def change_ollama(self, model_name):
        actual_name = model_name.split(" ")[0]
        print(f"Applying new Ollama Model: {actual_name}")
        CONFIG["ollama_model"] = actual_name

    def toggle_translation(self):
        thread = self.audio_thread
        if thread is not None:
            if thread.isRunning():
                # Stop — non-blocking with timeout to prevent freeze
                thread.stop()
                if not thread.wait(3000):  # 3 second timeout
                    print("[Agent] Audio thread didn't stop in time, forcing termination")
                    thread.terminate()
                    thread.wait(1000)
                self.audio_thread = None
                self.window.hide()
                self.start_action.setText("▶ Start Translation")
                
                # Clear queues
                while not audio_queue.empty():
                    try: audio_queue.get_nowait()
                    except: pass
                while not translation_queue.empty():
                    try: translation_queue.get_nowait()
                    except: pass
            else:
                # Start
                self.window.label.setText("Waiting for speech... 🎙️")
                # ... rest of the logic involves creating a NEW thread anyway
                pass
        else:
            # Start
            self.window.label.setText("Waiting for speech... 🎙️")
            self.window.show()
            new_thread = AudioCaptureThread()
            self.audio_thread = new_thread
            new_thread.error_signal.connect(self.show_error)
            new_thread.start()
            self.start_action.setText("⏹ Stop Translation")

    def show_error(self, err):
        print(f"Error: {err}")
        # Could show OS notification here if needed

    def quit_app(self):
        thread = self.audio_thread
        if thread is not None and thread.isRunning():
            thread.stop()
            thread.wait()
            
        audio_queue.put(None)
        translation_queue.put(None) # type: ignore
        
        self.transcriber.quit()
        self.transcriber.wait()
        self.translator.quit()
        self.translator.wait()
        
        self.app.quit()

# ================= Main =================
def main():
    app = QApplication(sys.argv)
    
    # Must NOT quit when window is hidden
    app.setQuitOnLastWindowClosed(False)

    window = SubtitleWindow()
    # DO NOT show window initially.
    
    # Start blocking agent threads
    transcriber_th = TranscriberThread()
    translator_th = TranslatorThread()
    translator_th.translation_ready.connect(window.update_text)
    
    transcriber_th.start()
    translator_th.start()
    
    agent = MenuBarAgent(app, window, transcriber_th, translator_th)
    agent.show()
    
    # Show a system notification to confirm it started
    agent.showMessage("Subtitle Agent", "Running in Menu Bar (右上角已启动)", QSystemTrayIcon.MessageIcon.Information, 3000)
    
    print("\n[Agent] Menu Bar Agent is running...")
    sys.exit(app.exec())

if __name__ == '__main__':
    main()
