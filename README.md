<div align="center">
  <img src="src-tauri/icons/128x128.png" alt="Jen Logo" width="128" height="128" />
  <h1>Jen</h1>
  <p><b>Your Minimalist, Voice-Powered Assistant for Windows</b></p>

  <p>
    <a href="https://github.com/SehajveerSingh2005/jen/releases/latest">
      <img src="https://img.shields.io/github/v/release/SehajveerSingh2005/jen?style=flat-square&color=6366f1" alt="Latest Release" />
    </a>
    <img src="https://img.shields.io/badge/platform-windows-blue?style=flat-square" alt="Platform: Windows" />
    <img src="https://img.shields.io/badge/built_with-tauri_v2-brightgreen?style=flat-square" alt="Built with Tauri v2" />
    <img src="https://img.shields.io/badge/license-GPLv3-yellow?style=flat-square" alt="License: GPLv3" />
  </p>

  <p>
    <i>Jen is a lightweight, non-intrusive virtual companion designed to live at the bottom of your screen. Jen listens for your wake word, executes commands, and stays out of your way.</i>
  </p>
</div>

---

## Features

- **Always Listening:** Hands-free interaction with a custom wake word ("Hey Jen").
- **Noise-Resistant Engine:** Multi-frame debouncing and RMS volume gating to prevent false triggers from sneezes, coughs, or room noise.
- **LLM-Powered Agent:** Natural language understanding via local (llama-server) or cloud (OpenAI/Anthropic) models — no fuzzy matching. Recommended local model: Qwen 3.5 4B (100% tool-selection accuracy in our eval).
- **GPU Acceleration:** Optional one-click Vulkan runtime (30 MB) runs the model on your GPU — ~4x faster commands on a modern GPU.
- **Tool Calling:** The LLM decides which tools to call (apps, browser, window management, media, power, clipboard, etc.) and narrates its reasoning.
- **Persistent Memory:** Jen remembers facts you ask her to (name, preferences, aliases). Conversation history stays in-session only — never replayed across restarts.
- **Personality Modes:** Minimal (answers only) or Conversational (confirms every action) — configurable in Settings.
- **Follow-Up Window:** 12-second window after each turn where you can speak again without re-saying the wake word.
- **Barge-In:** Interrupt Jen's TTS response by saying "Hey Jen" mid-sentence.
- **Voice Dictation:** Hands-free text typing directly into your currently active application.
- **Keypress Commands:** Speak to hit keys like Enter, Spacebar, Tab, Escape, Backspace, or Arrow keys.
- **Global Hotkey:** Quick manual trigger with `Ctrl+Shift+R` (customizable).
- **Media Control:** Control Spotify, YouTube, or system media with voice (Play/Pause/Next/Prev).
- **Smart Search:** Instant Google searches or "I'm Feeling Lucky" navigation.
- **Window Management:** Quickly focus, minimize, maximize, or close application windows.
- **System Commands:** Screenshots, clipboard ops, keyboard shortcuts, brightness, and quick-launch built-in apps.
- **Power Control:** Lock, sleep, hibernate, restart, or shut down — with an optional safety guard.
- **Sensitive Command Protection:** A toggle in Settings to block power commands from being triggered by voice.
- **Minimalist UI:** A beautiful, transparent orb that reacts to your voice.
- **Auto-Start:** Optionally launch Jen automatically when you sign in to Windows.

---

## Preview

<div align="center">
  <img width="1920" height="1080" alt="jen-1" src="https://github.com/user-attachments/assets/31642e52-8369-4118-8358-5500c9921698" />
</div>

---

## Supported Commands

Jen understands natural language and routes to the correct tool. Here are example phrases:

| Category | Example Phrases |
| :--- | :--- |
| **Dictation / Typing** | "Type hello world", "Dictate python main.py", "Write meeting notes", "Type out npm run dev" |
| **Button / Key Press** | "Press Enter", "Hit Space", "Press Tab", "Press Escape", "Press Backspace", "Press Up / Down / Left / Right" |
| **Media** | "Pause", "Resume", "Next song", "Previous track", "Stop music" |
| **Music Search** | "Play Bohemian Rhapsody", "Listen to Daft Punk", "Search and play Lo-fi" |
| **Search** | "Search Google for latest space news", "Look up how to make pasta", "Google GitHub" |
| **App Launch** | "Open Notepad", "Launch Chrome", "Start Spotify", "Run VS Code" |
| **Window Control** | "Minimize Discord", "Maximize Chrome", "Close Notepad", "Switch to Firefox", "Focus Slack" |
| **Screenshot** | "Take a screenshot", "Screenshot", "Capture screen", "Snap screen" |
| **Clipboard** | "Copy", "Paste", "Cut", "Copy that", "Paste that" |
| **Keyboard Shortcuts** | "Undo", "Redo", "Save", "Select all", "New tab", "Close tab", "Reopen tab", "Zoom in", "Zoom out", "Refresh", "Find", "Go back", "Go forward", "Show desktop", "New window", "Close application" |
| **Quick Launch** | "Open Calculator", "File Explorer", "Snipping Tool", "Notepad", "Paint", "Terminal", "PowerShell", "Task Manager", "Control Panel", "Windows Settings", "Edge", "Firefox" |
| **Volume** | "Volume up", "Volume down", "Mute", "Unmute", "Increase volume", "Decrease volume" |
| **Brightness** | "Brightness up", "Brighter", "Brightness down", "Dimmer", "Dim screen" |
| **Memory** | "Remember that I prefer dark mode", "What's my name?", "Recall my settings" |
| **Power** *(protection off)* | "Lock screen", "Sleep", "Hibernate", "Restart", "Shut down", "Turn off" |

> **Note:** Power commands (lock, sleep, hibernate, restart, shutdown) are **blocked by default**. Toggle **Sensitive Command Protection** off in Settings to enable them.

---

## Settings

Open Settings from the system tray icon (right-click → Settings).

| Setting | Description |
| :--- | :--- |
| **Launch on Startup** | Start Jen automatically when Windows boots |
| **Audio Feedback** | Play chime sounds when Jen detects a wake word or finishes a command |
| **Sensitive Command Protection** | Block voice-triggered power commands (lock, sleep, restart, shutdown). Toggle off to allow them. |
| **Activation Hotkey** | Customize the keyboard shortcut to manually trigger Jen (default: `Ctrl+Shift+R`) |
| **Wake Word Sensitivity** | Low / Medium (default) / High — how easily "Hey Jen" triggers |
| **Microphone** | Choose the input device for the wake word and speech (default: system default) |
| **Speaker** | Choose the output device for voice responses (default: system default) |
| **Follow-Up Conversation** | Keep listening after each reply for back-and-forth (off by default: the open mic can pick up Jen's own voice) |
| **Personality** | Minimal (answers only) or Conversational (confirms every action) |
| **AI Backend** | Local (llama-server), Cloud (OpenAI-compatible), or Off |
| **Local Model** | Choose which GGUF model the local llama-server loads |
| **GPU Acceleration** | Run the model on your GPU (Vulkan) — one-click 30 MB runtime download |
| **Cloud API Key** | Your API key for cloud backends (stored locally in settings) |

---

## Roadmap

- [x] **LLM Integration:** Local (llama-server) and cloud (OpenAI-compatible) backends with unified chat/completions API.
- [x] **Web Search:** DuckDuckGo lookup with LLM-summarized answers for weather, news, places, and other live questions.
- [x] **Persistent Memory:** SQLite fact store (persisted) + in-session conversation history (never persisted, so stale turns can never poison behavior).
- [x] **Tool Calling:** 16 tools covering apps, browser, window management, media, clipboard, search, volume, brightness, memory, and power.
- [x] **Personality:** Minimal and conversational modes controlling speech behavior and follow-up window.
- [ ] **Voice Cloning:** Clone your own voice for TTS responses.
- [ ] **Native Rust STT:** Migrate from the Python sidecar to a pure Rust implementation.
- [ ] **Context-Aware Actions:** Ability for Jen to understand what's on your screen and provide relevant assistance.
- [ ] **Calendar & Mail:** Integration with Windows productivity apps for scheduling and reminders.
- [ ] **Custom Skins:** More visual variations for the orb and interaction animations.

---

## Architecture

```
jen/
├── src-tauri/           # Rust backend (Tauri v2)
│   ├── src/lib.rs       # IPC commands, sidecar lifecycle, audio loop
│   ├── sidecar/         # Python agent package
│   │   ├── main.py      # Entry point (--simulate / --dry-run CLI)
│   │   ├── agent.py     # Agent: process() → tool calls or text
│   │   ├── client.py    # LLMClient: OpenAI-compatible chat/completions
│   │   ├── tools.py     # 16 tools with dry-run support
│   │   ├── memory.py    # SQLite facts + session-only history
│   │   ├── config.py    # SidecarConfig dataclass
│   │   ├── protocol.py  # emit() JSON-lines over stdout
│   │   └── tts.py       # Edge TTS wrapper
│   ├── binaries/        # llama-server DLLs (gitignored)
│   ├── tests/           # pytest suite (101 tests)
│   │   └── dev tools: check_wake.py, check_mic.py, eval_tools.py
├── src/                 # React frontend (Three.js orb)
└── tauri.conf.json      # Sidecar + resource bundling config
```

---

## Installation

Jen is currently optimized for **Windows**.

1. Go to the [**Releases**](https://github.com/sehaz/jen/releases) page.
2. Download the latest `.msi` or `.exe` installer.
3. Run the installer and follow the prompts.
4. Launch **Jen** from your Start Menu.
5. (Optional) Right-click the tray icon to enable **Launch on Startup**.

---

## System Requirements

Jen runs the language model locally on CPU — no GPU, no API key, no internet needed for inference (speech recognition and web search still use the network).

| | Minimum | Recommended | Pro |
| :--- | :--- | :--- | :--- |
| **RAM** | 8 GB | 16 GB | 32 GB |
| **CPU** | x86-64 with AVX2 (2013+), 4 cores | 6+ cores | 8+ cores |
| **Disk** | ~2 GB app + model | ~2 GB app + model | ~2 GB app + model |
| **Model** | Qwen 3 1.7B (~1.2 GB) | Qwen 3.5 4B (~2.7 GB) | Qwen 3 8B (~5 GB) |
| **Command latency** | ~1–1.5 s | ~2–2.5 s | ~3.5–4 s |
| **Tool accuracy** | good | excellent | very good |

> AVX2 is required by the bundled llama-server build. Every CPU since Intel Haswell / AMD Excavator (2013+) supports it.
> Q4_K_M quantization is the quality floor for reliable tool calling — avoid smaller quants.
> **Optional GPU:** any Vulkan-capable GPU (NVIDIA, AMD, or Intel) gets ~4x faster commands. Enable it in Settings → AI → GPU Acceleration; Jen downloads a 30 MB Vulkan runtime. The first run compiles GPU shaders once (~40 s, absorbed in the background), after that it is cached.

---

## Built With

- **[Tauri v2](https://v2.tauri.app/):** The core cross-platform framework.
- **[React](https://reactjs.org/) & [Three.js](https://threejs.org/):** For the interactive 3D orb UI.
- **[Python (Sidecar)](https://www.python.org/):** Agent brain, STT (Speech-to-Text), and tool execution.
- **[OpenWakeWord](https://github.com/dscripka/openWakeWord):** Robust, local wake word detection.
- **[llama-server](https://github.com/ggml-org/llama.cpp):** Local LLM inference via llama.cpp binaries.
- **[Rust](https://www.rust-lang.org/):** High-performance system backend, sidecar lifecycle management.

---

## Development

### Prerequisites
- [Node.js](https://nodejs.org/) (LTS)
- [Rust](https://www.rust-lang.org/tools/install)
- [Python 3.10+](https://www.python.org/downloads/)
- [pnpm](https://pnpm.io/installation)

### Setup
1. Clone the repository:
   ```bash
   git clone https://github.com/sehaz/jen.git
   cd jen
   ```
2. Install frontend dependencies:
   ```bash
   pnpm install
   ```
3. Install Python dependencies:
   ```bash
   pip install -r requirements.txt
   ```
4. Fetch llama-server binaries (one-time setup):
   ```bash
   python src-tauri/fetch_llama_server.py
   ```
5. Run in development mode:
   ```bash
   pnpm tauri dev
   ```

### Testing

Run the Python test suite (voice-free, no GPU required):
```bash
pip install pytest
pytest tests/
```

Diagnostics and evaluation tools:
```bash
# Wake word scores (say "Hey Jen" while it runs)
python src-tauri/sidecar/check_wake.py --seconds 20

# Microphone levels per device
python src-tauri/sidecar/check_mic.py --seconds 2

# Tool-selection accuracy against a running llama-server
python src-tauri/sidecar/eval_tools.py --url http://127.0.0.1:58931/v1
```

Test the agent with simulated input (no microphone needed):
```bash
python src-tauri/sidecar/main.py --simulate "open notepad" --dry-run
python src-tauri/sidecar/main.py --simulate "remember my name is Jen" --dry-run
python src-tauri/sidecar/main.py --simulate "what's my name" --dry-run
```

---

## License

This project is licensed under the GNU GPLv3 License - see the [LICENSE](LICENSE) file for details.

---

<div align="center">
  Created with ❤️ by <a href="https://github.com/SehajveerSingh2005">sehaz</a>
</div>
