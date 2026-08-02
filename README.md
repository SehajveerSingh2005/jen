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

Jen understands a variety of natural language intents. Here are some examples of what you can say:

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
| **Power** *(protection off)* | "Lock screen", "Sleep", "Hibernate", "Restart", "Shut down", "Turn off" |

> **Note:** Power commands (lock, sleep, hibernate, restart, shutdown) are **blocked by default**. Toggle **Sensitive Command Protection** off in Settings to enable them.

---

## Settings

Open Settings from the system tray icon (right-click → Settings).

| Setting | Description |
| :--- | :--- |
| **Launch on Startup** | Start Jen automatically when Windows boots |
| **Audio Feedback** | Play chime sounds when Jen detects a wake word or finishes a command |
| **Sensitive Command Protection** | Block voice-triggered power commands (lock, sleep, restart, shutdown). Toggle off to allow them. When a blocked command is attempted, the orb flashes red as feedback. |
| **Activation Hotkey** | Customize the keyboard shortcut to manually trigger Jen (default: `Ctrl+Shift+R`) |

---

## Roadmap

The vision for Jen is to become a deeply integrated, privacy-first Windows companion.

- [ ] **LLM Integration:** Connect Jen to local (Ollama) or cloud-based LLMs for complex reasoning and natural conversations.
- [ ] **Native Rust STT:** Migrate from the Python sidecar to a pure Rust implementation for even lower latency and smaller bundle sizes.
- [ ] **Context-Aware Actions:** Ability for Jen to understand what's on your screen and provide relevant assistance.
- [ ] **Calendar & Mail:** Integration with Windows productivity apps for scheduling and reminders.
- [ ] **Custom Skins:** More visual variations for the orb and interaction animations.

---

## Installation

Jen is currently optimized for **Windows**.

1. Go to the [**Releases**](https://github.com/sehaz/jen/releases) page.
2. Download the latest `.msi` or `.exe` installer.
3. Run the installer and follow the prompts.
4. Launch **Jen** from your Start Menu.
5. (Optional) Right-click the tray icon to enable **Launch on Startup**.

---

## Built With

- **[Tauri v2](https://v2.tauri.app/):** The core cross-platform framework.
- **[React](https://reactjs.org/) & [Three.js](https://threejs.org/):** For the interactive 3D orb UI.
- **[Python (Sidecar)](https://www.python.org/):** Powering the STT (Speech-to-Text) and intent engine.
- **[OpenWakeWord](https://github.com/dscripka/openWakeWord):** Robust, local wake word detection.
- **[Rust](https://www.rust-lang.org/):** High-performance system backend.

---

## Development

Want to contribute or build Jen yourself?

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
3. Install Python dependencies (for the STT sidecar):
   ```bash
   pip install numpy openwakeword SpeechRecognition pyaudio thefuzz PyAutoGUI PyGetWindow onnxruntime screen-brightness-control
   ```
4. Run in development mode:
   ```bash
   pnpm tauri dev
   ```

---

## License

This project is licensed under the GNU GPLv3 License - see the [LICENSE](LICENSE) file for details.

---

<div align="center">
  Created with ❤️ by <a href="https://github.com/SehajveerSingh2005">sehaz</a>
</div>
