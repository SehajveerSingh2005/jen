<div align="center">
  <img src="src-tauri/icons/128x128.png" alt="Jen Logo" width="128" height="128" />
  <h1>Jen</h1>
  <p><b>Your Minimalist, Voice-Powered AI Assistant for Windows</b></p>

  <p>
    <a href="https://github.com/SehajveerSingh2005/jen/releases/latest">
      <img src="https://img.shields.io/github/v/release/SehajveerSingh2005/jen?style=flat-square&color=6366f1" alt="Latest Release" />
    </a>
    <img src="https://img.shields.io/badge/platform-windows-blue?style=flat-square" alt="Platform: Windows" />
    <img src="https://img.shields.io/badge/built_with-tauri_v2-brightgreen?style=flat-square" alt="Built with Tauri v2" />
    <img src="https://img.shields.io/badge/license-GPLv3-yellow?style=flat-square" alt="License: GPLv3" />
  </p>

  <p>
    <i>Jen is a lightweight, non-intrusive AI companion designed to live at the bottom of your screen. She listens for your wake word, executes commands, and stays out of your way.</i>
  </p>
</div>

---

## Features

- **Always Listening:** Hands-free interaction with a custom wake word ("Hey Jen").
- **Global Hotkey:** Quick manual trigger with `Ctrl+Shift+R` (customizable).
- **Media Control:** Control Spotify, YouTube, or system media with voice (Play/Pause/Next/Prev).
- **Smart Search:** Instant Google searches or "I'm Feeling Lucky" navigation.
- **Window Management:** Quickly focus or hide application windows.
- **Minimalist UI:** A beautiful, transparent orb that reacts to your voice.
- **Auto-Start:** Optionally launch Jen automatically when you sign in to Windows.

---

## Preview

<div align="center">
  <!-- Replace these with actual GIFs/Screenshots -->
  <img src="https://via.placeholder.com/600x300.png?text=Jen+Orb+Interaction+Preview" alt="Jen Interaction" width="600" />
  <p><i>Jen responding to a voice command at the bottom of the screen.</i></p>
</div>

---

## Supported Commands

Jen understands a variety of natural language intents. Here are some examples of what you can say:

| Category | Example Commands |
| :--- | :--- |
| **Media** | "Pause the music", "Play next song", "Previous track", "Resume playback" |
| **Search** | "Search Google for latest space news", "Look up how to make pasta" |
| **Navigation** | "Google 'GitHub'", "Search for 'Tauri documentation'" |
| **App Control** | "Open Notepad", "Launch Chrome", "Start Spotify" |
| **System** | "Focus on Discord", "Hide Jen", "Go away" |

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
   pip install numpy openwakeword SpeechRecognition pyaudio thefuzz PyAutoGUI PyGetWindow onnxruntime
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
