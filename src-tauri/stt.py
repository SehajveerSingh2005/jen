import sys
import os
import json
import time
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

# Disable TQDM progress bars
os.environ["TQDM_DISABLE"] = "1"

# Disable pyautogui failsafe to prevent crashes from rapid mouse movements
pyautogui.FAILSAFE = False

# Global flags
trigger_manual = False
protect_sensitive = True  # Default: on; controlled via stdin from Rust

def log_debug(msg):
    try:
        with open("stt_debug.log", "a") as f:
            f.write(f"{time.ctime()}: {msg}\n")
    except:
        pass

def listen_stdin():
    global trigger_manual, protect_sensitive
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
    "button_press": [
        "press enter", "hit enter", "enter key", "press space", "hit space", "spacebar", "press spacebar",
        "press tab", "hit tab", "press escape", "hit escape", "press esc", "escape key",
        "press backspace", "hit backspace", "backspace", "press delete", "hit delete",
        "press up", "press down", "press left", "press right", "press {key}", "hit {key}"
    ]
}

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
    except Exception as e:
        log_debug(f"Error executing automation: {e}")

def parse_intent(text):
    text = text.lower().strip()
    best_match, highest_score, detected_intent = None, 0, None
    for intent, patterns in INTENTS.items():
        for pattern in patterns:
            clean_pattern = re.sub(r"\{.*?\}", "", pattern).strip()
            score = fuzz.partial_ratio(text, clean_pattern)
            if score > highest_score:
                highest_score, detected_intent, best_match = score, intent, pattern
    params = {"raw_text": text}
    if detected_intent == "open_app":
        for p in INTENTS["open_app"]:
            m = re.search(p.replace("{app}", "(.*)"), text)
            if m: params["app"] = m.group(1).strip(); break
    elif detected_intent == "window_control":
        for p in INTENTS["window_control"]:
            if "{app}" in p:
                regex = p.replace("{app}", "(.*)")
                for verb in ["focus window", "focus", "switch to", "minimize", "minimise", "maximize", "maximise", "close"]:
                    if regex.startswith(verb): regex = regex[len(verb):].strip(); break
                m = re.search(regex, text)
                if m:
                    ex = m.group(1).strip()
                    if ex != "window": params["app"] = ex; break
    elif detected_intent == "google_search":
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
    elif detected_intent == "button_press":
        for p in INTENTS["button_press"]:
            if "{key}" in p:
                m = re.search(p.replace("{key}", "(.*)"), text)
                if m: params["key"] = m.group(1).strip(); break
    if highest_score > 70:
        return {"intent": detected_intent, "params": params, "score": highest_score}
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
                            r.adjust_for_ambient_noise(source, duration=0.2)
                            audio_clip = r.listen(source, timeout=7, phrase_time_limit=10)
                            print(json.dumps({"status": "transcribing"}), flush=True)
                            text = r.recognize_google(audio_clip)
                            res = parse_intent(text)
                            if res: execute_automation(res)
                            print(json.dumps({"status": "success", "text": text}), flush=True)
                        except sr.UnknownValueError:
                            print(json.dumps({"status": "error", "message": "unknown"}), flush=True)
                        except Exception as e:
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
