# MacOS Local Realtime Video Translator

A lightning-fast, fully offline, realtime bilingual (English to Chinese) subtitle translation system built designed specifically for macOS.

This tool intercepts your system's audio playback using a virtual audio cable, detects speech endpoints via Voice Activity Detection (VAD), transcribes the English audio using `faster-whisper`, and translates it with ultra-low latency using a local Ollama LLM (`qwen2.5:3b`). The result is rendered natively as an un-clickable, transparent PyQt6 overlay that never steals your window focus.

## 🌟 Features
- **True Offline Processing**: No API keys, no monthly fees, 100% privacy-preserving.
- **Ultra-low Latency**: End-to-end sync in less than ~1.0 second.
- **Ghost Subtitle UI**: The bilingual Qt overlay acts as a proper system-wide HUD. Full mouse-click passthrough means you can use your browser and click on videos seamlessly without hitting the subtitle window.
- **Smart Chunking**: Aggressive VAD (150ms pauses) combined with a 3.0s forced cut prevents long-sentence backlog.

## 🛠 Prerequisites

### 1. Hardware & OS
- **Platform**: macOS (Tested on Apple Silicon M-series, e.g., M4 Max)
- **Memory**: Minimum 16GB Unified Memory recommended.

### 2. Audio Capture Configuration (CRITICAL)
This app needs to "hear" what your Mac is playing. You **must** install a virtual audio driver like BlackHole.

1. Install BlackHole via Homebrew:
   ```bash
   brew install blackhole-2ch
   ```
2. Configure a Multi-Output Device:
   - Open macOS **Audio MIDI Setup**.
   - Click the `+` at the bottom left -> **Create Multi-Output Device**.
   - Check both your **MacBook Speakers** and **BlackHole 2ch**.
   - ⚠️ **Important**: Check the **Drift Correction** box for BlackHole to prevent audio desync over time.
3. In your macOS System Settings > Sound > Output, select this new **Multi-Output Device**.

### 3. Local LLM Setup
Install [Ollama](https://ollama.com) and pull the high-speed translation model.
```bash
ollama run qwen2.5:3b
```
*(You can also use larger models like `qwen2.5:7b` by changing the configuration in `main.py`, but it will increase latency).*

## 🚀 Installation & Usage

1. **Clone the repository:**
   ```bash
   git clone https://github.com/your-username/realtime-translator.git
   cd realtime-translator
   ```

2. **Create a Python Virtual Environment:**
   ```bash
   python -m venv .venv
   source .venv/bin/activate
   ```

3. **Install Dependencies:**
   ```bash
   pip install -r requirements.txt
   ```
   *Note: If `webrtcvad` fails to compile, you may need to downgrade setuptools: `pip install "setuptools<70.0.0"` before installing.*

4. **Run the App:**
   Make sure Ollama is running in the background, then launch the translator:
   ```bash
   python main.py
   ```

Enjoy your real-time translation! To exit, return to the terminal running `main.py` and hit `Ctrl+C`.

## ⚙️ Configuration
All major parameters are located in the `CONFIG` dictionary at the top of `main.py`:
- `whisper_model`: "small" (or "base" for even faster, less accurate transcription)
- `silence_trigger_ms`: 150 (VAD pause before pushing transcription task)
- `max_chunk_duration_s`: 3.0 (forced break for long talkers)
- `ollama_model`: "qwen2.5:3b"

## 📝 License
MIT License
