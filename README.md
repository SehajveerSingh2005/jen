# Jen Assistant V1

Jen is a modern, minimal, soft-tech desktop assistant powered by **Tauri v2**, **React**, and **Python**. It features a high-fidelity 3D Orb visualizer from ElevenLabs and robust OS-level automation for app launching, window management, and media control.

## 🚀 Key Features

- **Wake Word Detection:** Responds instantly to "Hey Jen" (or "Hey Jarvis" as fallback).
- **Modern UI:** Small, transparent, always-on-top window with a reactive 3D Orb.
- **Resolution Independent:** Automatically centers itself 48px from the bottom of your screen on any resolution or scale.
- **Robust Automation:** Controls your OS using native keyboard shortcuts—no fragile pathing or blocked commands.

## 🎙️ Command Documentation

### 📱 App Launching
Uses Windows Search to find and open any installed application.
- *"Open VS Code"*
- *"Launch Google Chrome"*
- *"Start Spotify"*

### 🪟 Window Management
- *"Close window"* / *"Close"* (`Alt + F4`)
- *"Minimize window"* / *"Minimize"* (`Win + Down`)
- *"Maximize window"* / *"Maximize"* (`Win + Up`)
- *"Switch window"* / *"Focus"* / *"Next window"* (`Alt + Tab`)

### 🎵 Media Controls
Universal controls for YouTube, Spotify, VLC, and browser players.
- *"Pause music"* / *"Resume"* / *"Play"* (`Media Play/Pause`)
- *"Next"* / *"Skip"* (`Media Next`)
- *"Previous"* / *"Back"* (`Media Previous`)
- *"Skip 5 seconds"* / *"Forward"* (`Right Arrow`)
- *"Rewind 5 seconds"* / *"Rewind"* (`Left Arrow`)

### 🔊 System Controls
- *"Volume up"* / *"Increase volume"*
- *"Volume down"* / *"Decrease volume"*
- *"Mute"* / *"Unmute"*

### 🔍 Web Search
- *"Search Google for [query]"*
- *"Google [query]"*

---

## 🛠️ Technical Stack

- **Frontend:** React (TypeScript) + Three.js + React Three Fiber + Tailwind CSS.
- **Backend:** Rust (Tauri v2) - Manages window lifecycle, IPC, and OS events.
- **Sidecar:** Python - Handles Speech-to-Text (Google), Wake Word detection (openWakeWord), and Automation (PyAutoGUI).

## ⚙️ Setup & Installation

1. **Install Dependencies:**
   - Node.js & pnpm
   - Rust (latest)
   - Python 3.x
2. **Python Setup:**
   ```bash
   pip install openwakeword speechrecognition pyaudio pyautogui thefuzz numpy
   ```
3. **Run Application:**
   ```bash
   pnpm install
   pnpm tauri dev
   ```

## 📝 License
GNU GPL v3
