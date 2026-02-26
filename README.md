# 🎬 Realtime Subtitle Translator | 实时字幕翻译器

A fully **offline**, **real-time** multilingual-to-Chinese subtitle translator for macOS. Captures system audio, auto-detects the spoken language using Whisper, and translates to Chinese via a local Ollama LLM — all running locally on your Mac with zero cloud dependency.

一款完全**离线**的 macOS **实时**多语言转中文字幕翻译器。通过捕获系统音频，利用 Whisper 自动识别语种并进行语音识别，再由本地 Ollama 大语言模型翻译成中文 —— 全程在本地运行，无需云端服务。

![macOS](https://img.shields.io/badge/macOS-Apple%20Silicon-blue?logo=apple)
![Python](https://img.shields.io/badge/Python-3.10+-blue?logo=python)
![License](https://img.shields.io/badge/License-MIT-green)

---

## ✨ Features | 功能特点

| Feature | 功能 |
|---|---|
| 🔇 Fully offline — no internet required | 完全离线 — 无需联网 |
| 🌍 Multi-language auto-detection (EN/JA/KO/FR/DE...) | 多语言自动识别 (英/日/韩/法/德...) |
| 🎙️ System audio capture via BlackHole | 通过 BlackHole 捕获系统音频 |
| ⚡ Low-latency streaming translation | 低延迟流式翻译 |
| 🌐 Local LLM translation (Ollama) | 本地大模型翻译 (Ollama) |
| 🖥️ Floating subtitle overlay | 悬浮字幕窗口 |
| 📊 Menu bar agent with one-click control | 菜单栏一键启停 |
| 🛡️ Multi-language hallucination filtering | 多语言幻觉过滤系统 |
| 🧠 Bilingual context window for coherence | 双语上下文窗口保证连贯性 |
| 🇬🇧🇯🇵🇰🇷 Language flag indicator in subtitles | 字幕语言国旗标识 |

---

## 🏗️ Architecture | 系统架构

```
System Audio (BlackHole) → VAD (WebRTC) → Whisper ASR (auto-detect lang) → Ollama LLM (streaming) → Floating Subtitle
       Thread 1                              Thread 2                          Thread 3                  Main Thread
```

Three independent threads ensure **zero blocking**: audio capture never waits for ASR, and ASR never waits for translation.

三个独立线程确保**零阻塞**：音频捕获不等待识别，识别不等待翻译。

---

## 📋 Prerequisites | 前置条件

### 1. Ollama

Install and run [Ollama](https://ollama.com) with a translation model:

安装并运行 [Ollama](https://ollama.com)，下载翻译模型：

```bash
# Install Ollama (if not installed)
brew install ollama

# Pull the recommended model (7b for quality, 3b for speed)
# 推荐模型（7b 质量优先，3b 速度优先）
ollama pull qwen2.5:7b

# Start Ollama server
ollama serve
```

### 2. BlackHole (Audio Loopback)

Required to capture system audio output.

用于捕获系统音频输出。

```bash
brew install blackhole-2ch
```

Then configure macOS **Audio MIDI Setup**:
1. Open **Audio MIDI Setup** (音频 MIDI 设置)
2. Click **"+"** → **Create Multi-Output Device** (创建多输出设备)
3. Check both **Built-in Output** and **BlackHole 2ch**
4. Set the Multi-Output Device as your system output (设为系统输出设备)

### 3. PortAudio (for PyAudio)

```bash
brew install portaudio
```

---

## 🚀 Installation | 安装

```bash
# Clone the repository | 克隆仓库
git clone https://github.com/laozhugege/realtime-translator.git
cd realtime-translator

# One-step launch (auto-creates venv & installs deps)
# 一键启动（自动创建虚拟环境并安装依赖）
chmod +x start.sh
./start.sh
```

Or manually:
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python main_agent.py
```

---

## ▶️ Usage | 使用方法

```bash
# Quick start | 快速启动
./start.sh

# Or manually | 或手动启动
source .venv/bin/activate
python main_agent.py
```

After starting:
1. Look for the blue **T** icon in the menu bar (菜单栏蓝色 **T** 图标)
2. Click **▶ Start Translation** to begin (开始翻译)
3. Play any English video — subtitles appear automatically (播放英文视频即可自动显示字幕)
4. Click **⏹ Stop Translation** to stop (停止翻译)

### Settings | 设置

From the menu bar icon, you can:
- Switch ASR model: `tiny` / `base` / `small`
- Switch LLM model: any model available in your Ollama

通过菜单栏图标可以：
- 切换 ASR 模型：`tiny` / `base` / `small`
- 切换 LLM 模型：Ollama 中已安装的任意模型

---

## ⚙️ Configuration | 配置参数

Key parameters in `main_agent.py`:

`main_agent.py` 中的关键参数：

| Parameter | Default | Description |
|---|---|---|
| `whisper_model` | `small` | Whisper model size (`tiny`/`base`/`small`) |
| `ollama_model` | `qwen2.5:7b` | Ollama translation model |
| `silence_trigger_ms` | `100` | Silence duration before segment cut (ms) |
| `max_chunk_duration_s` | `2.0` | Max audio segment length (s) |
| `vad_mode` | `1` | WebRTC VAD aggressiveness (0-3) |

---

## 🧪 Testing | 测试

```bash
# Test audio capture | 测试音频捕获
python test_audio.py

# Test Whisper ASR | 测试语音识别
python test_whisper.py

# Test Ollama translation | 测试翻译
python test_translate.py

# Test UI rendering | 测试界面
python test_ui.py
```

---

## 📁 Project Structure | 项目结构

```
realtime-translator/
├── main_agent.py       # Main application (核心应用)
├── start.sh            # Quick launch script (快捷启动脚本)
├── requirements.txt    # Python dependencies (依赖列表)
├── test_audio.py       # Audio capture test (音频测试)
├── test_whisper.py     # ASR test (识别测试)
├── test_translate.py   # Translation test (翻译测试)
├── test_ui.py          # UI test (界面测试)
└── README.md           # This file (本文件)
```

---

## 🔧 Troubleshooting | 常见问题

### No audio captured | 没有捕获到音频
- Ensure BlackHole is installed and the Multi-Output Device is set as system output
- 确保 BlackHole 已安装且多输出设备已设为系统输出

### Ollama connection error | Ollama 连接错误
- Make sure Ollama is running: `ollama serve`
- 确保 Ollama 正在运行：`ollama serve`

### Hallucinations ("Thank you" during silence) | 幻觉（静音时出现"谢谢"）
- The built-in filter handles most cases automatically
- 内置过滤器会自动处理大多数情况

### Translation quality | 翻译质量
- Use `qwen2.5:7b` for best quality (requires ~5GB RAM)
- 使用 `qwen2.5:7b` 获得最佳质量（需约 5GB 内存）
- `qwen2.5:3b` is faster but less accurate
- `qwen2.5:3b` 更快但准确度较低

### `ModuleNotFoundError: No module named 'pkg_resources'` (Python 3.12+)
- This project uses `webrtcvad-wheels` which is compatible with Python 3.12+
- If you previously installed with the old `webrtcvad`, reinstall: `pip install webrtcvad-wheels`
- 本项目使用兼容 Python 3.12+ 的 `webrtcvad-wheels`
- 如果之前安装过旧版 `webrtcvad`，请重新安装：`pip install webrtcvad-wheels`

---

## 💡 How It Works | 工作原理

1. **Audio Capture**: BlackHole routes system audio to the app via PyAudio
2. **VAD**: WebRTC Voice Activity Detection segments audio at natural speech pauses
3. **ASR**: faster-whisper transcribes each segment to English text
4. **Hallucination Filter**: Removes common Whisper artifacts (e.g., "Thank you")
5. **Translation**: Ollama translates with bilingual context for coherence
6. **Display**: Floating subtitle overlay shows bilingual (ZH + EN) results

---

## 📄 License | 许可证

MIT License. See [LICENSE](LICENSE) for details.

---

## 🙏 Acknowledgments | 致谢

- [faster-whisper](https://github.com/SYSTRAN/faster-whisper) — Fast Whisper inference
- [Ollama](https://ollama.com) — Local LLM inference
- [BlackHole](https://existential.audio/blackhole/) — macOS audio loopback
- [WebRTC VAD](https://github.com/wiseman/py-webrtcvad) — Voice Activity Detection
- [PyQt6](https://www.riverbankcomputing.com/software/pyqt/) — GUI framework
