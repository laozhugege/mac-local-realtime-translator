# MacOS Local Realtime Video Translator / MacOS 本地实时视频翻译器

[English](#english) | [中文](#中文)

---

<a id="english"></a>
## 🇬🇧 English

A lightning-fast, fully offline, realtime bilingual (English to Chinese) subtitle translation system designed specifically for macOS.

This tool intercepts your system's audio playback using a virtual audio cable, detects speech endpoints via Voice Activity Detection (VAD), transcribes the English audio using `faster-whisper`, and translates it with ultra-low latency using a local Ollama LLM (`qwen2.5:3b`). The result is rendered natively as an un-clickable, transparent PyQt6 overlay that never steals your window focus.

### 🌟 Features
- **True Offline Processing**: No API keys, no monthly fees, 100% privacy-preserving.
- **Ultra-low Latency**: End-to-end sync in less than ~1.0 second.
- **Ghost Subtitle UI**: The bilingual Qt overlay acts as a proper system-wide HUD. Full mouse-click passthrough means you can use your browser and click on videos seamlessly without hitting the subtitle window.
- **Smart Chunking**: Aggressive VAD (150ms pauses) combined with a 3.0s forced cut prevents long-sentence backlog.

### 🛠 Prerequisites

#### 1. Hardware & OS
- **Platform**: macOS (Tested on Apple Silicon M-series, e.g., M4 Max)
- **Memory**: Minimum 16GB Unified Memory recommended.

#### 2. Audio Capture Configuration (CRITICAL)
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

#### 3. Local LLM Setup
Install [Ollama](https://ollama.com) and pull the high-speed translation model.
```bash
ollama run qwen2.5:3b
```
*(You can also use larger models like `qwen2.5:7b` by changing the configuration in `main.py`, but it will increase latency).*

### 🚀 Installation & Usage

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

### ⚙️ Configuration
All major parameters are located in the `CONFIG` dictionary at the top of `main.py`:
- `whisper_model`: "small" (or "base" for even faster, less accurate transcription)
- `silence_trigger_ms`: 150 (VAD pause before pushing transcription task)
- `max_chunk_duration_s`: 3.0 (forced break for long talkers)
- `ollama_model`: "qwen2.5:3b"

### 📝 License
MIT License

---

<a id="中文"></a>
## 🇨🇳 中文版 (Chinese)

一个专为 macOS 设计的极速、完全离线、实时的双语（英译中）视频字幕翻译系统。

该工具通过虚拟音频线缆截获系统的音频播放，利用语音活动检测（VAD）识别语音端点，使用 `faster-whisper` 对英文音频进行转写，并调用本地的 Ollama 大语言模型 (`qwen2.5:3b`) 实现超低延迟翻译。最终的字幕会通过 PyQt6 渲染为一个完全不可点击、透明的悬浮窗（不会抢占任何窗口焦点）。

### 🌟 核心特性
- **完全离线处理**：无需 API Key，无订阅费用，100% 保护隐私。
- **超低延迟**：端到端音画同步延迟控制在 ~1.0 秒以内。
- **幽灵字幕 UI**：双语 Qt 悬浮窗作为系统级 HUD 存在。支持完全的鼠标点击穿透，意味着您可以无缝点按字幕下方的浏览器或视频播放器，绝不会被字幕窗阻挡。
- **智能切分**：激进的 VAD（150ms 停顿触发）结合 3.0 秒强制切断机制，彻底告别长难句带来的翻译积压与延迟。

### 🛠 环境要求

#### 1. 硬件与系统
- **平台**：macOS（在 Apple Silicon M 系列芯片如 M4 Max 上测试通过）
- **内存**：建议至少 16GB 统一内存。

#### 2. 音频捕获配置 (极其重要)
本程序需要“听见” Mac 发出的声音。您**必须**安装类似 BlackHole 的虚拟音频驱动。

1. 通过 Homebrew 安装 BlackHole：
   ```bash
   brew install blackhole-2ch
   ```
2. 配置多输出设备：
   - 打开 macOS 的 **“音频 MIDI 设置”** (Audio MIDI Setup)。
   - 点击左下角的 `+` -> **“创建多输出设备”**。
   - 勾选 **MacBook Pro 扬声器** 和 **BlackHole 2ch**。
   - ⚠️ **重要**：务必勾选 BlackHole 的 **“漂移校正” (Drift Correction)**，以防止长时间播放导致的音画不同步。
3. 在 macOS 的系统设置 > 声音 > 输出 中，选择这个新建的 **“多输出设备”**。

#### 3. 本地大模型设置
安装 [Ollama](https://ollama.com) 并拉取高速翻译模型。
```bash
ollama run qwen2.5:3b
```
*（您也可以在 `main.py` 中修改配置使用更大的模型如 `qwen2.5:7b`，但这会增加一些延迟）。*

### 🚀 安装与使用

1. **克隆仓库:**
   ```bash
   git clone https://github.com/您的用户名/realtime-translator.git
   cd realtime-translator
   ```

2. **创建 Python 虚拟环境:**
   ```bash
   python -m venv .venv
   source .venv/bin/activate
   ```

3. **安装依赖:**
   ```bash
   pip install -r requirements.txt
   ```
   *注意：如果 `webrtcvad` 编译失败，可能需要先降级 setuptools：`pip install "setuptools<70.0.0"`，然后再安装。*

4. **运行程序:**
   确保 Ollama 正在后台运行，然后启动翻译器：
   ```bash
   python main.py
   ```

享受您的实时翻译吧！想要退出程序，只需回到运行 `main.py` 的终端并按下 `Ctrl+C`。

### ⚙️ 核心配置
所有主要参数都位于 `main.py` 顶部的 `CONFIG` 字典中：
- `whisper_model`: "small" (或换成 "base" 以获得更快的转写速度，但准确率略低)
- `silence_trigger_ms`: 150 (VAD 触发翻译的静音停顿时间)
- `max_chunk_duration_s`: 3.0 (如果有人不停顿讲话时的强制切断时间)
- `ollama_model`: "qwen2.5:3b"

### 📝 开源协议
MIT License
