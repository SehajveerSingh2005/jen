import sys
import os
import json
import time
import random
import numpy as np
import openwakeword
from openwakeword.model import Model
import speech_recognition as sr
import pyaudio
import re
from thefuzz import process, fuzz
import pyautogui
import pygetwindow as gw
import threading
import traceback
try:
    import screen_brightness_control as sbc
    SBC_AVAILABLE = True
except ImportError:
    SBC_AVAILABLE = False

try:
    from tts import generate_tts_audio
    TTS_AVAILABLE = True
except ImportError:
    TTS_AVAILABLE = False

try:
    from ai_model import local_engine, cloud_engine
    AI_AVAILABLE = True
except ImportError:
    AI_AVAILABLE = False

# Disable TQDM progress bars
os.environ["TQDM_DISABLE"] = "1"

# Disable pyautogui failsafe to prevent crashes from rapid mouse movements
pyautogui.FAILSAFE = False

# Global flags
trigger_manual = False
protect_sensitive = True  # Default: on; controlled via stdin from Rust
tts_enabled = True  # Default: on; controlled via stdin from Rust
tts_voice = "en-US-JennyNeural"  # Default voice; controlled via stdin from Rust
ai_mode = "off"  # off | local | cloud; controlled via stdin from Rust

def log_debug(msg):
    try:
        with open("stt_debug.log", "a") as f:
            f.write(f"{time.ctime()}: {msg}\n")
    except:
        pass

def listen_stdin():
    global trigger_manual, protect_sensitive, tts_enabled, tts_voice, ai_mode
    while True:
        try:
            line = sys.stdin.readline()
            if not line:
                os._exit(0)
            cmd = line.strip()
            if cmd == "trigger":
                trigger_manual = True
            elif cmd == "protect:1":
                protect_sensitive = True
            elif cmd == "protect:0":
                protect_sensitive = False
            elif cmd == "tts:1":
                tts_enabled = True
            elif cmd == "tts:0":
                tts_enabled = False
            elif cmd.startswith("tts_voice:"):
                tts_voice = cmd.split(":", 1)[1].strip() or "en-US-JennyNeural"
            elif cmd.startswith("preview_voice:"):
                preview_voice = cmd.split(":", 1)[1].strip()
                if preview_voice and TTS_AVAILABLE:
                    def _preview():
                        try:
                            data, _ = generate_tts_audio("Hello! I'm Jen, your desktop assistant.", preview_voice)
                            if data:
                                print(json.dumps({"status": "tts_audio", "data": data}), flush=True)
                        except Exception as e:
                            log_debug(f"Preview TTS error: {e}")
                    threading.Thread(target=_preview, daemon=True).start()
            elif cmd.startswith("ai_mode:"):
                ai_mode = cmd.split(":", 1)[1].strip() or "off"
                log_debug(f"AI mode set to: {ai_mode}")
            elif cmd.startswith("ai_local_model:"):
                model_path = cmd.split(":", 1)[1].strip()
                if AI_AVAILABLE and model_path:
                    local_engine.configure(model_path)
                    local_engine.preload()
                    log_debug(f"Local AI model path set to: {model_path}")
            elif cmd.startswith("ai_cloud:"):
                # Format: ai_cloud:<api_key>:<base_url>:<model>
                parts = cmd.split(":", 2)
                if len(parts) >= 4 and AI_AVAILABLE:
                    cloud_engine.configure(parts[1], parts[2], parts[3])
                    log_debug(f"Cloud AI configured: {parts[2]} / {parts[3]}")
        except:
            os._exit(0)

# Start stdin listener thread
threading.Thread(target=listen_stdin, daemon=True).start()

# --- Intent Configuration ---
INTENTS = {
    "open_app": ["open {app}", "launch {app}", "start {app}", "run {app}"],
    "google_search": ["search google for {query}", "google {query}", "search for {query}", "look up {query}"],
    "volume_control": ["volume up", "volume down", "increase volume", "decrease volume", "mute", "unmute"],
    "window_control": [
        "close window", "minimize window", "maximize window", "minimise window", "maximise window",
        "switch window", "next window", "focus window {app}", "focus {app}", "switch to {app}",
        "minimize {app}", "minimise {app}", "maximize {app}", "maximise {app}", "close {app}",
        "change window", "switch", "focus", "maximize", "maximise", "minimize", "minimise", "close"
    ],
    "play_music": ["play {song}", "play music {song}", "search and play {song}", "listen to {song}"],
    "media_control": [
        "pause", "resume", "next", "skip", "previous", "back", "stop music", "pause music",
        "play music", "resume music", "skip 5 seconds", "rewind 5 seconds", "forward", "rewind", "play"
    ],
    # --- System commands ---
    "screenshot": [
        "take a screenshot", "screenshot", "take screenshot", "capture screen",
        "capture the screen", "snap screen", "take a snap"
    ],
    "clipboard": [
        "copy", "paste", "cut", "copy that", "paste that", "cut that"
    ],
    "keyboard_shortcut": [
        "undo", "redo", "select all", "save", "save file", "new tab", "close tab",
        "reopen tab", "open new tab", "close current tab", "refresh", "reload",
        "find", "open find", "zoom in", "zoom out", "reset zoom", "go back", "go forward",
        "open settings", "open task manager", "task manager", "open run", "run dialog",
        "show desktop", "new window", "open new window", "close application", "force close",
        "switch tab", "next tab", "previous tab"
    ],
    "quick_launch": [
        "open calculator", "calculator", "open file explorer", "file explorer", "files",
        "open browser", "open chrome", "open edge", "open firefox",
        "open notepad", "notepad", "open paint", "open snipping tool", "snipping tool",
        "open terminal", "open command prompt", "open powershell", "open task manager",
        "open system settings", "open windows settings", "system settings", "settings",
        "open control panel", "control panel", "open device manager"
    ],
    "power_control": [
        "lock screen", "lock", "lock computer", "lock pc",
        "sleep", "sleep mode", "put to sleep", "go to sleep",
        "hibernate", "hibernation",
        "restart", "reboot", "restart computer", "reboot computer",
        "shutdown", "shut down", "turn off", "power off", "shut down computer"
    ],
    "brightness_control": [
        "brightness up", "increase brightness", "brighter",
        "brightness down", "decrease brightness", "dimmer", "dim screen"
    ],
    "dictation": [
        "type {text}", "type out {text}", "dictate {text}", "write {text}",
        "type text {text}", "type this {text}"
    ],
    "weather": [
        "what's the weather", "what is the weather", "how's the weather", "how is the weather",
        "weather today", "weather outside", "is it raining", "is it sunny",
        "temperature outside", "what's the temperature"
    ],
    "button_press": [
        "press enter", "hit enter", "enter key", "press space", "hit space", "spacebar", "press spacebar",
        "press tab", "hit tab", "press escape", "hit escape", "press esc", "escape key",
        "press backspace", "hit backspace", "backspace", "press delete", "hit delete",
        "press up", "press down", "press left", "press right", "press {key}", "hit {key}"
    ]
}

GREETINGS = ["Yes?", "Hmm?", "Yes", "Go ahead", "I'm listening"]

def send_tts(text):
    """Generate TTS audio and send to Rust for playback."""
    if not tts_enabled or not TTS_AVAILABLE:
        return
    try:
        data, timings = generate_tts_audio(text, tts_voice)
        if data:
            print(json.dumps({"status": "tts_audio", "data": data, "words": timings, "text": text}), flush=True)
    except Exception as e:
        log_debug(f"TTS error: {e}")

def send_tts_async(text):
    """Generate TTS in background, send when ready."""
    if not tts_enabled or not TTS_AVAILABLE:
        return
    def _worker():
        try:
            data, timings = generate_tts_audio(text, tts_voice)
            if data:
                print(json.dumps({"status": "tts_audio", "data": data, "words": timings, "text": text}), flush=True)
        except Exception as e:
            log_debug(f"TTS async error: {e}")
    threading.Thread(target=_worker, daemon=True).start()

_weather_cache = {"lat": None, "lon": None, "city": None}

def _handle_weather(params):
    """Fetch weather from Open-Meteo and speak it."""
    def _fetch():
        try:
            import urllib.request

            # Use cached location or fetch new one
            if _weather_cache["lat"] is None:
                loc_resp = urllib.request.urlopen("http://ip-api.com/json/?fields=lat,lon,city", timeout=5)
                loc = json.loads(loc_resp.read())
                _weather_cache["lat"] = loc["lat"]
                _weather_cache["lon"] = loc["lon"]
                _weather_cache["city"] = loc.get("city", "your area")

            lat, lon, city = _weather_cache["lat"], _weather_cache["lon"], _weather_cache["city"]

            # Fetch weather with retry
            url = (
                f"https://api.open-meteo.com/v1/forecast?"
                f"latitude={lat}&longitude={lon}"
                f"&current=temperature_2m,weather_code,wind_speed_10m,relative_humidity_2m"
                f"&temperature_unit=celsius"
                f"&windspeed_unit=kmh"
            )
            w_data = None
            for attempt in range(3):
                try:
                    w_resp = urllib.request.urlopen(url, timeout=5)
                    w_data = json.loads(w_resp.read())["current"]
                    break
                except Exception as e:
                    log_debug(f"Weather attempt {attempt+1} failed: {e}")
                    if attempt == 2:
                        raise
                    time.sleep(0.5)

            temp = round(w_data["temperature_2m"])
            humidity = w_data["relative_humidity_2m"]
            wind = round(w_data["wind_speed_10m"])
            code = w_data["weather_code"]

            WMO = {
                0: "clear sky", 1: "mainly clear", 2: "partly cloudy", 3: "overcast",
                45: "foggy", 48: "rime fog", 51: "light drizzle", 53: "drizzle",
                55: "heavy drizzle", 61: "light rain", 63: "rain", 65: "heavy rain",
                71: "light snow", 73: "snow", 75: "heavy snow", 80: "light showers",
                81: "showers", 82: "heavy showers", 95: "thunderstorm",
            }
            condition = WMO.get(code, "unknown")

            msg = f"In {city}, it's {temp} degrees Celsius and {condition}. Humidity is {humidity} percent with wind at {wind} kilometers per hour."
            log_debug(f"Weather: {msg}")
            send_tts(msg)
        except Exception as e:
            log_debug(f"Weather fetch error: {e}")
            send_tts("Sorry, I couldn't get the weather right now.")
    threading.Thread(target=_fetch, daemon=True).start()

def execute_automation(intent_data):
    try:
        intent = intent_data["intent"]
        params = intent_data["params"]
        raw_text = params.get("raw_text", "").lower()
        
        if intent == "open_app":
            app_name = params.get("app", "")
            if app_name:
                pyautogui.press('win')
                time.sleep(0.3)
                pyautogui.write(app_name, interval=0.05)
                time.sleep(0.3)
                pyautogui.press('enter')
        elif intent == "window_control":
            app_name = params.get("app", "")
            is_close = any(k in raw_text for k in ["close", "exit", "quit"])
            is_minimize = any(k in raw_text for k in ["minimize", "minimise"])
            is_maximize = any(k in raw_text for k in ["maximize", "maximise"])
            is_focus = any(k in raw_text for k in ["focus", "switch", "open window", "change window"])

            target_win = None
            if app_name:
                windows = gw.getWindowsWithTitle('')
                windows = [w for w in windows if w.title.strip() and w.width > 0 and w.height > 0]
                titles = [w.title for w in windows]
                if titles:
                    res = process.extractOne(app_name, titles, scorer=fuzz.partial_ratio)
                    if res and res[1] > 60:
                        for win in windows:
                            if win.title == res[0]:
                                target_win = win
                                break
            
            if not target_win:
                print(json.dumps({"status": "hide"}), flush=True)
                time.sleep(0.3)
                active = gw.getActiveWindow()
                if active and "jen" not in active.title.lower():
                    target_win = active

            if target_win:
                if is_close: target_win.close()
                elif is_minimize: target_win.minimize()
                elif is_maximize:
                    if target_win.isMinimized: target_win.restore()
                    target_win.maximize()
                    target_win.activate()
                elif is_focus:
                    if target_win.isMinimized: target_win.restore()
                    pyautogui.press('alt') 
                    target_win.activate()
        elif intent == "media_control":
            cmd = "toggle"
            if any(k in raw_text for k in ["pause", "stop"]): cmd = "pause"
            elif any(k in raw_text for k in ["resume", "play"]): cmd = "play"
            elif any(k in raw_text for k in ["next", "skip"]): cmd = "next"
            elif any(k in raw_text for k in ["previous", "back", "rewind"]): cmd = "prev"
            print(json.dumps({"status": "media_control", "command": cmd}), flush=True)
        elif intent == "volume_control":
            if "up" in raw_text or "increase" in raw_text: pyautogui.press('volumeup')
            elif "down" in raw_text or "decrease" in raw_text: pyautogui.press('volumedown')
            elif "mute" in raw_text: pyautogui.press('volumemute')
        elif intent == "google_search":
            query = params.get("query", "")
            if query:
                import webbrowser
                webbrowser.open(f"https://www.google.com/search?q={query}")
        elif intent == "weather":
            _handle_weather(params)
        elif intent == "play_music":
            song = params.get("song", "")
            if song:
                import webbrowser
                search_query = f"site:youtube.com {song} official audio"
                url = f"https://www.google.com/search?q={search_query}&btnI=1&autoplay=1&mute=0"
                webbrowser.open(url)
        elif intent == "screenshot":
            # Win+PrintScreen saves to ~/Pictures/Screenshots automatically
            pyautogui.hotkey('win', 'prtsc')
        elif intent == "clipboard":
            if any(k in raw_text for k in ["paste"]):
                pyautogui.hotkey('ctrl', 'v')
            elif any(k in raw_text for k in ["cut"]):
                pyautogui.hotkey('ctrl', 'x')
            else:  # copy (default)
                pyautogui.hotkey('ctrl', 'c')
        elif intent == "keyboard_shortcut":
            if "undo" in raw_text:
                pyautogui.hotkey('ctrl', 'z')
            elif "redo" in raw_text:
                pyautogui.hotkey('ctrl', 'y')
            elif "select all" in raw_text:
                pyautogui.hotkey('ctrl', 'a')
            elif any(k in raw_text for k in ["save file", "save"]):
                pyautogui.hotkey('ctrl', 's')
            elif any(k in raw_text for k in ["reopen tab"]):
                pyautogui.hotkey('ctrl', 'shift', 't')
            elif any(k in raw_text for k in ["new tab", "open new tab"]):
                pyautogui.hotkey('ctrl', 't')
            elif any(k in raw_text for k in ["close tab", "close current tab"]):
                pyautogui.hotkey('ctrl', 'w')
            elif any(k in raw_text for k in ["new window", "open new window"]):
                pyautogui.hotkey('ctrl', 'n')
            elif any(k in raw_text for k in ["close application", "force close"]):
                pyautogui.hotkey('alt', 'f4')
            elif any(k in raw_text for k in ["refresh", "reload"]):
                pyautogui.press('f5')
            elif any(k in raw_text for k in ["find", "open find"]):
                pyautogui.hotkey('ctrl', 'f')
            elif "zoom in" in raw_text:
                pyautogui.hotkey('ctrl', '+')
            elif "zoom out" in raw_text:
                pyautogui.hotkey('ctrl', '-')
            elif "reset zoom" in raw_text:
                pyautogui.hotkey('ctrl', '0')
            elif "go back" in raw_text:
                pyautogui.hotkey('alt', 'left')
            elif "go forward" in raw_text:
                pyautogui.hotkey('alt', 'right')
            elif any(k in raw_text for k in ["task manager"]):
                pyautogui.hotkey('ctrl', 'shift', 'esc')
            elif any(k in raw_text for k in ["run dialog", "open run"]):
                pyautogui.hotkey('win', 'r')
            elif "show desktop" in raw_text:
                pyautogui.hotkey('win', 'd')
            elif any(k in raw_text for k in ["open settings", "settings"]):
                pyautogui.hotkey('win', 'i')
            elif "next tab" in raw_text:
                pyautogui.hotkey('ctrl', 'tab')
            elif any(k in raw_text for k in ["previous tab", "switch tab"]):
                pyautogui.hotkey('ctrl', 'shift', 'tab')
        elif intent == "quick_launch":
            if any(k in raw_text for k in ["calculator", "calc"]):
                import subprocess
                subprocess.Popen(["calc.exe"])
            elif any(k in raw_text for k in ["file explorer", "files", "explorer"]):
                import subprocess
                subprocess.Popen(["explorer.exe"])
            elif any(k in raw_text for k in ["notepad"]):
                import subprocess
                subprocess.Popen(["notepad.exe"])
            elif any(k in raw_text for k in ["paint"]):
                import subprocess
                subprocess.Popen(["mspaint.exe"])
            elif any(k in raw_text for k in ["snipping tool", "snip"]):
                import subprocess
                subprocess.Popen(["snippingtool.exe"])
            elif any(k in raw_text for k in ["powershell"]):
                import subprocess
                subprocess.Popen(["powershell.exe"])
            elif any(k in raw_text for k in ["command prompt", "cmd"]):
                import subprocess
                subprocess.Popen(["cmd.exe"])
            elif any(k in raw_text for k in ["terminal"]):
                import subprocess
                subprocess.Popen(["wt.exe"])  # Windows Terminal
            elif any(k in raw_text for k in ["task manager"]):
                import subprocess
                subprocess.Popen(["taskmgr.exe"])
            elif any(k in raw_text for k in ["control panel"]):
                import subprocess
                subprocess.Popen(["control.exe"])
            elif any(k in raw_text for k in ["device manager"]):
                import subprocess
                subprocess.Popen(["devmgmt.msc"])
            elif any(k in raw_text for k in ["system settings", "windows settings", "settings"]):
                import subprocess
                subprocess.Popen(["ms-settings:"], shell=True)
            elif any(k in raw_text for k in ["chrome"]):
                import subprocess
                subprocess.Popen(["chrome.exe"])
            elif any(k in raw_text for k in ["edge"]):
                import subprocess
                subprocess.Popen(["msedge.exe"])
            elif any(k in raw_text for k in ["firefox"]):
                import subprocess
                subprocess.Popen(["firefox.exe"])
            elif any(k in raw_text for k in ["browser"]):
                import webbrowser
                webbrowser.open("about:newtab")
        elif intent == "power_control":
            if protect_sensitive:
                print(json.dumps({"status": "blocked_sensitive", "intent": "power_control", "text": raw_text}), flush=True)
                return
            import subprocess
            if any(k in raw_text for k in ["lock screen", "lock computer", "lock pc", "lock"]):
                subprocess.Popen(["rundll32.exe", "user32.dll,LockWorkStation"])
            elif any(k in raw_text for k in ["sleep mode", "put to sleep", "go to sleep", "sleep"]):
                subprocess.Popen(["rundll32.exe", "powrprof.dll,SetSuspendState", "0", "1", "0"])
            elif any(k in raw_text for k in ["hibernate", "hibernation"]):
                subprocess.Popen(["shutdown.exe", "/h"])
            elif any(k in raw_text for k in ["restart", "reboot"]):
                subprocess.Popen(["shutdown.exe", "/r", "/t", "5"])
            elif any(k in raw_text for k in ["shutdown", "shut down", "turn off", "power off"]):
                subprocess.Popen(["shutdown.exe", "/s", "/t", "5"])
        elif intent == "brightness_control":
            direction = "up" if any(k in raw_text for k in ["up", "increase", "brighter"]) else "down"
            def _do_brightness(d=direction):
                try:
                    if SBC_AVAILABLE:
                        current = sbc.get_brightness(display=0)
                        if isinstance(current, list): current = current[0]
                        delta = 10 if d == "up" else -10
                        new_val = max(0, min(100, current + delta))
                        sbc.set_brightness(new_val, display=0)
                    else:
                        log_debug("screen_brightness_control not available; brightness command skipped")
                except Exception as e:
                    log_debug(f"Brightness error: {e}")
            threading.Thread(target=_do_brightness, daemon=True).start()
        elif intent == "dictation":
            text_to_type = params.get("text", "")
            if not text_to_type:
                for prefix in ["type out ", "type text ", "type this ", "type ", "dictate ", "write "]:
                    if raw_text.startswith(prefix):
                        text_to_type = raw_text[len(prefix):].strip()
                        break
            if text_to_type:
                print(json.dumps({"status": "hide"}), flush=True)
                time.sleep(0.15)
                pyautogui.write(text_to_type, interval=0.01)
        elif intent == "button_press":
            key_name = params.get("key", "").lower()
            if not key_name:
                key_name = raw_text.lower()
            
            mapped_key = None
            if "enter" in key_name: mapped_key = "enter"
            elif "space" in key_name: mapped_key = "space"
            elif "tab" in key_name: mapped_key = "tab"
            elif "escape" in key_name or "esc" in key_name: mapped_key = "escape"
            elif "backspace" in key_name: mapped_key = "backspace"
            elif "delete" in key_name: mapped_key = "delete"
            elif "up" in key_name: mapped_key = "up"
            elif "down" in key_name: mapped_key = "down"
            elif "left" in key_name: mapped_key = "left"
            elif "right" in key_name: mapped_key = "right"
            
            if mapped_key:
                print(json.dumps({"status": "hide"}), flush=True)
                time.sleep(0.15)
                pyautogui.press(mapped_key)
        elif intent == "ai_response":
            # No automation — just a conversational response for TTS
            pass
    except Exception as e:
        log_debug(f"Error executing automation: {e}")

def parse_intent(text):
    text = text.lower().strip()
    params = {"raw_text": text}

    # --- Keyword-based matching (deterministic, fast) ---
    # Commands with arguments
    for prefix, intent in [
        ("open ", "open_app"), ("launch ", "open_app"), ("start ", "open_app"), ("run ", "open_app"),
        ("search ", "google_search"), ("google ", "google_search"), ("look up ", "google_search"),
        ("play ", "play_music"),
        ("type ", "dictation"), ("dictate ", "dictation"), ("write ", "dictation"),
        ("press ", "button_press"), ("hit ", "button_press"),
    ]:
        if text.startswith(prefix):
            arg = text[len(prefix):].strip()
            if intent == "open_app":
                params["app"] = arg
            elif intent == "google_search":
                params["query"] = arg
            elif intent == "play_music":
                params["song"] = arg
            elif intent == "dictation":
                params["text"] = arg
            elif intent == "button_press":
                params["key"] = arg
            return {"intent": intent, "params": params, "score": 100}

    # Weather (exact phrase match, not partial)
    WEATHER_KEYWORDS = [
        "what's the weather", "what is the weather", "how's the weather", "how is the weather",
        "whats the weather", "weather report", "weather today", "weather outside",
        "is it raining", "is it sunny", "is it snowing",
        "temperature outside", "what's the temperature", "what is the temperature",
    ]
    for kw in WEATHER_KEYWORDS:
        if kw in text:
            return {"intent": "weather", "params": {"query": text, "raw_text": text}, "score": 100}

    # Single-word commands (require exact word match, not substring)
    EXACT_WORDS = {
        "mute": ("volume_control", {"action": "mute"}),
        "unmute": ("volume_control", {"action": "unmute"}),
        "screenshot": ("screenshot", {}),
        "copy": ("clipboard", {}),
        "paste": ("clipboard", {}),
        "cut": ("clipboard", {}),
        "undo": ("keyboard_shortcut", {"shortcut": "undo"}),
        "redo": ("keyboard_shortcut", {"shortcut": "redo"}),
        "refresh": ("keyboard_shortcut", {"shortcut": "refresh"}),
        "reload": ("keyboard_shortcut", {"shortcut": "reload"}),
        "find": ("keyboard_shortcut", {"shortcut": "find"}),
    }
    words = text.split()
    if len(words) == 1 and words[0] in EXACT_WORDS:
        intent, p = EXACT_WORDS[words[0]]
        return {"intent": intent, "params": {**p, "raw_text": text}, "score": 100}

    # Multi-word commands (fuzzy match against known phrases)
    PHRASE_INTENTS = {
        "volume up": ("volume_control", {"action": "up"}),
        "volume down": ("volume_control", {"action": "down"}),
        "increase volume": ("volume_control", {"action": "up"}),
        "decrease volume": ("volume_control", {"action": "down"}),
        "pause": ("media_control", {"action": "pause"}),
        "resume": ("media_control", {"action": "play"}),
        "next": ("media_control", {"action": "next"}),
        "skip": ("media_control", {"action": "next"}),
        "previous": ("media_control", {"action": "prev"}),
        "back": ("media_control", {"action": "prev"}),
        "stop music": ("media_control", {"action": "pause"}),
        "play music": ("media_control", {"action": "play"}),
        "take a screenshot": ("screenshot", {}),
        "take screenshot": ("screenshot", {}),
        "close window": ("window_control", {"action": "close"}),
        "minimize window": ("window_control", {"action": "minimize"}),
        "maximize window": ("window_control", {"action": "maximize"}),
        "minimise window": ("window_control", {"action": "minimize"}),
        "maximise window": ("window_control", {"action": "maximize"}),
        "select all": ("keyboard_shortcut", {"shortcut": "select_all"}),
        "save file": ("keyboard_shortcut", {"shortcut": "save"}),
        "new tab": ("keyboard_shortcut", {"shortcut": "new_tab"}),
        "close tab": ("keyboard_shortcut", {"shortcut": "close_tab"}),
        "show desktop": ("keyboard_shortcut", {"shortcut": "show_desktop"}),
        "open settings": ("keyboard_shortcut", {"shortcut": "open_settings"}),
        "task manager": ("keyboard_shortcut", {"shortcut": "task_manager"}),
        "lock screen": ("power_control", {"action": "lock"}),
        "shut down": ("power_control", {"action": "shutdown"}),
        "turn off": ("power_control", {"action": "shutdown"}),
    }
    best_score = 0
    best_intent = None
    best_params = None
    for phrase, (intent, p) in PHRASE_INTENTS.items():
        score = fuzz.ratio(text, phrase)
        if score > best_score:
            best_score = score
            best_intent = intent
            best_params = p
    if best_score >= 80:
        return {"intent": best_intent, "params": {**best_params, "raw_text": text}, "score": best_score}

    # Window control with app name: "focus chrome", "close notepad", "switch to spotify"
    WIN_ACTIONS = {
        "focus": "focus", "switch to": "focus", "open window": "focus",
        "minimize": "minimize", "minimise": "minimize",
        "maximize": "maximize", "maximise": "maximize",
        "close": "close", "exit": "close", "quit": "close",
    }
    for trigger, action in WIN_ACTIONS.items():
        rest = text
        if text.startswith(trigger):
            rest = text[len(trigger):].strip()
        elif f"{trigger} " in text:
            rest = text.split(trigger, 1)[1].strip()
        else:
            continue
        # Filter out generic words that aren't app names
        if rest and rest not in ("window", "this", "that", "the", "it", "app", "application", "program"):
            return {"intent": "window_control", "params": {"action": action, "app": rest, "raw_text": text}, "score": 90}

    # Fallback: try fuzzy match against all INTENTS patterns (with higher threshold)
    best_match, highest_score, detected_intent = None, 0, None
    for intent, patterns in INTENTS.items():
        for pattern in patterns:
            clean_pattern = re.sub(r"\{.*?\}", "", pattern).strip()
            # Use ratio (full string match) instead of partial_ratio
            score = fuzz.ratio(text, clean_pattern)
            if score > highest_score:
                highest_score, detected_intent, best_match = score, intent, pattern
    if highest_score >= 85:
        # Extract parameters from matched pattern
        if detected_intent == "google_search":
            for p in INTENTS["google_search"]:
                m = re.search(p.replace("{query}", "(.*)"), text)
                if m: params["query"] = m.group(1).strip(); break
        elif detected_intent == "play_music":
            for p in INTENTS["play_music"]:
                m = re.search(p.replace("{song}", "(.*)"), text)
                if m: params["song"] = m.group(1).strip(); break
        elif detected_intent == "dictation":
            for p in INTENTS["dictation"]:
                if "{text}" in p:
                    m = re.search(p.replace("{text}", "(.*)"), text)
                    if m: params["text"] = m.group(1).strip(); break
        return {"intent": detected_intent, "params": params, "score": highest_score}

    # No command matched — try AI if enabled
    if ai_mode != "off" and AI_AVAILABLE:
        engine = local_engine if ai_mode == "local" else cloud_engine
        ai_result = engine.process(text)
        log_debug(f"AI result: {ai_result}")

        if ai_result.get("type") == "tool_call":
            return _map_tool_to_intent(ai_result, text)
        elif ai_result.get("type") == "response":
            return {
                "intent": "ai_response",
                "params": {"text": ai_result["text"], "raw_text": text},
                "score": 100,
            }

    return None


def _map_tool_to_intent(ai_result, raw_text):
    """Map an LLM tool call to the existing intent format."""
    func = ai_result["function"]
    args = ai_result.get("args", {})

    if func == "open_app":
        return {"intent": "open_app", "params": {"app": args.get("app", ""), "raw_text": raw_text}, "score": 100}
    elif func == "google_search":
        return {"intent": "google_search", "params": {"query": args.get("query", ""), "raw_text": raw_text}, "score": 100}
    elif func == "play_music":
        return {"intent": "play_music", "params": {"song": args.get("song", ""), "raw_text": raw_text}, "score": 100}
    elif func == "volume_control":
        return {"intent": "volume_control", "params": {"raw_text": args.get("action", "up")}, "score": 100}
    elif func == "media_control":
        return {"intent": "media_control", "params": {"raw_text": args.get("action", "play")}, "score": 100}
    elif func == "window_control":
        action = args.get("action", "focus")
        app = args.get("app", "")
        return {"intent": "window_control", "params": {"raw_text": f"{action} {app}".strip()}, "score": 100}
    elif func == "brightness_control":
        direction = args.get("action", "up")
        return {"intent": "brightness_control", "params": {"raw_text": f"brightness {direction}"}, "score": 100}
    elif func == "screenshot":
        return {"intent": "screenshot", "params": {"raw_text": "screenshot"}, "score": 100}
    elif func == "dictate":
        return {"intent": "dictation", "params": {"text": args.get("text", ""), "raw_text": raw_text}, "score": 100}
    elif func == "keyboard_shortcut":
        return {"intent": "keyboard_shortcut", "params": {"shortcut_name": args.get("shortcut", ""), "raw_text": raw_text}, "score": 100}
    elif func == "weather":
        return {"intent": "weather", "params": {"query": args.get("query", "today"), "raw_text": raw_text}, "score": 100}

    return None

def get_resource_path(relative_path):
    try: base_path = sys._MEIPASS
    except: base_path = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_path, relative_path)

def listen_and_transcribe():
    hey_jen_path = get_resource_path("hey_jen.onnx")
    hey_jarvis_path = get_resource_path("models/hey_jarvis.onnx")
    melspec_path = get_resource_path("models/melspectrogram.onnx")
    embedding_path = get_resource_path("models/embedding_model.onnx")
    
    wakeword_models = []
    if os.path.exists(hey_jen_path): wakeword_models.append(hey_jen_path)
    if not wakeword_models:
        if os.path.exists(hey_jarvis_path): wakeword_models.append(hey_jarvis_path)
        else: wakeword_models.append("hey_jarvis")
    
    # Load model with explicit base model paths ONLY if they exist
    model_kwargs = {
        "wakeword_models": wakeword_models,
        "inference_framework": "onnx"
    }
    if os.path.exists(melspec_path):
        model_kwargs["melspec_model_path"] = melspec_path
    if os.path.exists(embedding_path):
        model_kwargs["embedding_model_path"] = embedding_path
    
    oww_model = Model(**model_kwargs)
    r = sr.Recognizer()
    
    FORMAT, CHANNELS, RATE, CHUNK = pyaudio.paInt16, 1, 16000, 1280
    audio = None
    
    print(json.dumps({"status": "ready"}), flush=True)

    while True:
        try:
            if audio is None:
                try:
                    audio = pyaudio.PyAudio()
                except:
                    time.sleep(3.0)
                    continue

            stream = None
            try:
                stream = audio.open(format=FORMAT, channels=CHANNELS, rate=RATE, input=True, frames_per_buffer=CHUNK)
                for _ in range(10):
                    try: stream.read(CHUNK, exception_on_overflow=False)
                    except: pass

                detected = False
                history = {}
                while True:
                    global trigger_manual
                    if trigger_manual:
                        trigger_manual = False
                        print(json.dumps({"status": "detected", "wakeword": "manual"}), flush=True)
                        detected = True
                        break

                    try:
                        data = stream.read(CHUNK, exception_on_overflow=False)
                    except:
                        break # Re-init

                    audio_data = np.frombuffer(data, dtype=np.int16)
                    
                    # 1. RMS Energy Check (filters silence/static and mic clipping from sneezes)
                    rms = float(np.sqrt(np.mean(audio_data.astype(np.float32)**2)))
                    if rms < 80.0 or rms > 9500.0:
                        continue

                    # 2. OpenWakeWord Prediction
                    prediction = oww_model.predict(audio_data)
                    
                    # 3. Multi-Frame History Verification (Debouncing transient sneezes, coughs & inhales)
                    for wakeword, prob in prediction.items():
                        if wakeword not in history:
                            history[wakeword] = []
                        
                        history[wakeword].append(prob)
                        if len(history[wakeword]) > 4:
                            history[wakeword].pop(0)

                        # Trigger criteria:
                        # Genuine speech ("Hey Jen") lasts 400-800ms (5-10 frames), producing sustained high scores.
                        # Sneezes/coughs produce a single 80ms transient spike.
                        recent = history[wakeword]
                        peak_prob = max(recent)
                        high_frame_count = sum(1 for p in recent if p > 0.38)
                        
                        # Require peak >= 0.55 AND at least 2 frames > 0.38 in the last 4 frames
                        if peak_prob >= 0.55 and high_frame_count >= 2:
                            log_debug(f"Wake word confirmed: {wakeword} (prob={peak_prob:.2f}, rms={rms:.0f}, high_frames={high_frame_count})")
                            print(json.dumps({"status": "detected", "wakeword": wakeword}), flush=True)
                            detected = True
                            history.clear()
                            break
                    if detected: break
            except:
                if stream:
                    try: stream.close()
                    except: pass
                if audio:
                    try: audio.terminate()
                    except: pass
                audio = None
                time.sleep(2.0)
                continue
            finally:
                if stream:
                    try:
                        stream.stop_stream()
                        stream.close()
                    except: pass

            if detected:
                try:
                    with sr.Microphone(sample_rate=16000) as source:
                        try:
                            print(json.dumps({"status": "recording"}), flush=True)
                            r.adjust_for_ambient_noise(source, duration=0.3)
                            r.pause_threshold = 1.5
                            r.energy_threshold = 300
                            audio_clip = r.listen(source, timeout=7, phrase_time_limit=20)
                            print(json.dumps({"status": "transcribing"}), flush=True)
                            text = r.recognize_google(audio_clip)
                            res = parse_intent(text)
                            if res:
                                intent_name = res.get("intent", "")
                                execute_automation(res)
                                # Speak a response
                                if intent_name == "ai_response":
                                    response_text = res.get("params", {}).get("text", "")
                                    if response_text:
                                        send_tts_async(response_text)
                                elif intent_name != "weather":
                                    send_tts_async("Done!")
                            else:
                                send_tts_async("I didn't catch that. Try again.")
                            print(json.dumps({"status": "success", "text": text}), flush=True)
                        except sr.UnknownValueError:
                            send_tts_async("Sorry, I didn't catch that.")
                            print(json.dumps({"status": "error", "message": "unknown"}), flush=True)
                        except Exception as e:
                            send_tts_async("Something went wrong.")
                            print(json.dumps({"status": "error", "message": str(e)}), flush=True)
                            if audio:
                                try: audio.terminate()
                                except: pass
                            audio = None
                except:
                    print(json.dumps({"status": "error", "message": "mic_init_fail"}), flush=True)
                    if audio:
                        try: audio.terminate()
                        except: pass
                    audio = None
                
                print(json.dumps({"status": "ready"}), flush=True)
                oww_model.reset()
                time.sleep(2.0)
        except BaseException as e:
            log_debug(f"Global loop error: {e}")
            audio = None
            time.sleep(5.0)

if __name__ == "__main__":
    try:
        listen_and_transcribe()
    except BaseException as e:
        log_debug(f"FATAL STARTUP ERROR: {e}\n{traceback.format_exc()}")
        os._exit(0)
