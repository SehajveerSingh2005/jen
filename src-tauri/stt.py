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

# Disable TQDM progress bars
os.environ["TQDM_DISABLE"] = "1"

# Disable pyautogui failsafe to prevent crashes from rapid mouse movements
pyautogui.FAILSAFE = False

# Global flag for manual trigger
trigger_manual = False

def listen_stdin():
    global trigger_manual
    while True:
        line = sys.stdin.readline()
        if not line:
            break
        if line.strip() == "trigger":
            trigger_manual = True

# Start stdin listener thread
threading.Thread(target=listen_stdin, daemon=True).start()

# --- Intent Configuration ---
INTENTS = {
    "open_app": [
        "open {app}",
        "launch {app}",
        "start {app}",
        "run {app}"
    ],
    "google_search": [
        "search google for {query}",
        "google {query}",
        "search for {query}",
        "look up {query}"
    ],
    "volume_control": [
        "volume up",
        "volume down",
        "increase volume",
        "decrease volume",
        "mute",
        "unmute"
    ],
    "window_control": [
        "close window",
        "minimize window",
        "maximize window",
        "minimise window",
        "maximise window",
        "switch window",
        "next window",
        "focus window {app}",
        "focus {app}",
        "switch to {app}",
        "minimize {app}",
        "minimise {app}",
        "maximize {app}",
        "maximise {app}",
        "close {app}",
        "change window",
        "switch",
        "focus",
        "maximize",
        "maximise",
        "minimize",
        "minimise",
        "close"
    ],
    "play_music": [
        "play {song}",
        "play music {song}",
        "search and play {song}",
        "listen to {song}"
    ],
    "media_control": [
        "pause",
        "resume",
        "next",
        "skip",
        "previous",
        "back",
        "stop music",
        "pause music",
        "play music",
        "resume music",
        "skip 5 seconds",
        "rewind 5 seconds",
        "forward",
        "rewind",
        "play"
    ]
}

def execute_automation(intent_data):
    intent = intent_data["intent"]
    params = intent_data["params"]
    raw_text = params.get("raw_text", "").lower()
    
    try:
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
            
            # Determine action
            is_close = any(k in raw_text for k in ["close", "exit", "quit"])
            is_minimize = any(k in raw_text for k in ["minimize", "minimise"])
            is_maximize = any(k in raw_text for k in ["maximize", "maximise"])
            is_focus = any(k in raw_text for k in ["focus", "switch", "open window", "change window"])

            # Find target window
            target_win = None
            if app_name:
                windows = gw.getWindowsWithTitle('')
                windows = [w for w in windows if w.title.strip()]
                titles = [w.title for w in windows]
                best_title, score = process.extractOne(app_name, titles, scorer=fuzz.partial_ratio)
                
                if score > 60:
                    for win in windows:
                        if win.title == best_title:
                            target_win = win
                            break
            
            if not target_win:
                print(json.dumps({"status": "hide"}), flush=True)
                time.sleep(0.3)
                active = gw.getActiveWindow()
                if active and "jen" not in active.title.lower():
                    target_win = active

            if target_win:
                try:
                    # Use Native Window Management via JSON signal to Rust (or directly via pygetwindow which uses Win32)
                    if is_close:
                        target_win.close()
                    elif is_minimize:
                        target_win.minimize()
                    elif is_maximize:
                        if target_win.isMinimized:
                            target_win.restore()
                        target_win.maximize()
                        target_win.activate()
                    elif is_focus:
                        if target_win.isMinimized:
                            target_win.restore()
                        target_win.activate()
                    return True
                except Exception as e:
                    print(f"DEBUG Error manipulating window: {e}", file=sys.stderr)
            
            # Fallback to direct hotkeys only for generic actions
            if not target_win:
                if is_close: pyautogui.hotkey('alt', 'f4')
                elif is_minimize: pyautogui.hotkey('win', 'down')
                elif is_maximize: pyautogui.hotkey('win', 'up')
                elif is_focus: pyautogui.hotkey('alt', 'tab')
            return True
                
        elif intent == "media_control":
            cmd = "toggle"
            if any(k in raw_text for k in ["pause", "stop"]): cmd = "pause"
            elif any(k in raw_text for k in ["resume", "play"]): cmd = "play"
            elif any(k in raw_text for k in ["next", "skip"]): cmd = "next"
            elif any(k in raw_text for k in ["previous", "back", "rewind"]): cmd = "prev"
            
            # Send native media control signal to Rust
            print(json.dumps({"status": "media_control", "command": cmd}), flush=True)
                
        elif intent == "volume_control":
            if "up" in raw_text or "increase" in raw_text:
                pyautogui.press('volumeup')
            elif "down" in raw_text or "decrease" in raw_text:
                pyautogui.press('volumedown')
            elif "mute" in raw_text:
                pyautogui.press('volumemute')
                
        elif intent == "google_search":
            query = params.get("query", "")
            if query:
                import webbrowser
                webbrowser.open(f"https://www.google.com/search?q={query}")
                
        elif intent == "play_music":
            song = params.get("song", "")
            if song:
                import webbrowser
                # Use Lucky search but with a more direct query
                # We add the SO suggested parameters to the end of the query 
                # to see if Google/YouTube respects them upon redirect
                search_query = f"site:youtube.com {song} official audio"
                url = f"https://www.google.com/search?q={search_query}&btnI=1&autoplay=1&mute=0"
                webbrowser.open(url)
                
                # Robustness thread: Find the browser window, activate it, and force play
                def robust_play():
                    # Wait for redirect and load
                    start_time = time.time()
                    while time.time() - start_time < 25: # 25 seconds total polling
                        time.sleep(1.0)
                        active = gw.getActiveWindow()
                        
                        if active and "jen" in active.title.lower():
                            print(json.dumps({"status": "hide"}), flush=True)
                            continue

                        found_win = None
                        if active and ("youtube" in active.title.lower() or "google" in active.title.lower()):
                            found_win = active
                        else:
                            all_windows = gw.getWindowsWithTitle('')
                            for win in all_windows:
                                if "youtube" in win.title.lower():
                                    found_win = win
                                    break
                        
                        if found_win:
                            try:
                                if found_win.isMinimized:
                                    found_win.restore()
                                found_win.activate()
                                
                                # 1. Single 'k' press to kickstart the video player
                                if "youtube" in found_win.title.lower():
                                    time.sleep(1.5) # wait for focus to settle
                                    pyautogui.press('k')
                                    
                                    # 2. Follow up with explicit "Play" signals (non-toggling)
                                    # If 'k' worked, these do nothing. If 'k' was too early, 
                                    # these will start the video once the media session is ready.
                                    for _ in range(4):
                                        time.sleep(3.0)
                                        # Use the native signal to Rust (non-toggling)
                                        print(json.dumps({"status": "media_control", "command": "play"}), flush=True)
                                    break 
                                else:
                                    # If we are still on Google, just wait for the redirect
                                    pass
                            except:
                                pass
                
                threading.Thread(target=robust_play, daemon=True).start()
                
        return True
                
        return True
    except Exception as e:
        print(f"DEBUG Error executing automation: {e}", file=sys.stderr)
        return False

def parse_intent(text):
    text = text.lower().strip()
    
    # 1. Direct Matching / Fuzzy Match
    best_match = None
    highest_score = 0
    detected_intent = None
    
    for intent, patterns in INTENTS.items():
        for pattern in patterns:
            clean_pattern = re.sub(r"\{.*?\}", "", pattern).strip()
            score = fuzz.partial_ratio(text, clean_pattern)
            
            if score > highest_score:
                highest_score = score
                detected_intent = intent
                best_match = pattern

    params = {"raw_text": text}
    
    # Extraction logic
    if detected_intent == "open_app":
        for p in INTENTS["open_app"]:
            regex = p.replace("{app}", "(.*)")
            match = re.search(regex, text)
            if match:
                params["app"] = match.group(1).strip()
                break
    elif detected_intent == "window_control":
        # Specific extraction for "{action} {app}"
        for p in INTENTS["window_control"]:
            if "{app}" in p:
                regex = p.replace("{app}", "(.*)")
                # Remove common verbs from regex start to isolate app name
                for verb in ["focus window", "focus", "switch to", "minimize", "minimise", "maximize", "maximise", "close"]:
                    if regex.startswith(verb):
                        regex = regex[len(verb):].strip()
                        break
                match = re.search(regex, text)
                if match:
                    extracted = match.group(1).strip()
                    # If extracted is just "window", ignore it as an app name
                    if extracted != "window":
                        params["app"] = extracted
                        break
    elif detected_intent == "google_search":
        for p in INTENTS["google_search"]:
            regex = p.replace("{query}", "(.*)")
            match = re.search(regex, text)
            if match:
                params["query"] = match.group(1).strip()
                break
    elif detected_intent == "play_music":
        for p in INTENTS["play_music"]:
            regex = p.replace("{song}", "(.*)")
            match = re.search(regex, text)
            if match:
                params["song"] = match.group(1).strip()
                break

    if highest_score > 70:
        return {"intent": detected_intent, "params": params, "score": highest_score}
    return None

def get_resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_path, relative_path)

def listen_and_transcribe():
    model_path = os.path.abspath(get_resource_path("hey_jen.onnx"))
    wakeword_models = [model_path] if os.path.exists(model_path) else ["hey_jarvis"]
    
    # Load model from resource path or fallback
    oww_model = Model(wakeword_models=wakeword_models, inference_framework="onnx")
    r = sr.Recognizer()
    
    FORMAT = pyaudio.paInt16
    CHANNELS = 1
    RATE = 16000
    CHUNK = 1280
    
    audio = pyaudio.PyAudio()
    
    print(json.dumps({"status": "ready"}), flush=True)

    try:
        while True:
            stream = audio.open(format=FORMAT, channels=CHANNELS, rate=RATE, input=True, frames_per_buffer=CHUNK)
            
            # Initial "flush" to ignore old audio
            for _ in range(10):
                stream.read(CHUNK, exception_on_overflow=False)

            detected = False
            while True:
                global trigger_manual
                if trigger_manual:
                    trigger_manual = False
                    print(json.dumps({"status": "detected", "wakeword": "manual"}), flush=True)
                    detected = True
                    break

                data = stream.read(CHUNK, exception_on_overflow=False)
                audio_data = np.frombuffer(data, dtype=np.int16)
                prediction = oww_model.predict(audio_data)
                
                for wakeword, probability in prediction.items():
                    if probability > 0.3:
                        print(json.dumps({"status": "detected", "wakeword": wakeword}), flush=True)
                        detected = True
                        break
                
                if detected:
                    break

            if detected:
                stream.stop_stream()
                stream.close()
                
                with sr.Microphone(sample_rate=16000) as source:
                    try:
                        print(json.dumps({"status": "recording"}), flush=True)
                        # Increase phrase_time_limit to 10s and add non_speaking_duration
                        # This allows for longer commands like "play god's plan by drake"
                        r.adjust_for_ambient_noise(source, duration=0.2)
                        audio_clip = r.listen(source, timeout=7, phrase_time_limit=10)
                        print(json.dumps({"status": "transcribing"}), flush=True)
                        text = r.recognize_google(audio_clip)
                        
                        result = parse_intent(text)
                        if result:
                            execute_automation(result)
                            print(json.dumps({"status": "success", "text": text}), flush=True)
                        else:
                            print(json.dumps({"status": "success", "text": text}), flush=True)
                            
                    except sr.UnknownValueError:
                        print(json.dumps({"status": "error", "message": "unknown"}), flush=True)
                    except Exception as e:
                        print(json.dumps({"status": "error", "message": str(e)}), flush=True)
                    
                    # Cooldown to prevent immediate re-triggering (feedback loop)
                    print(json.dumps({"status": "ready"}), flush=True)
                    
                    # CRITICAL: Reset model state to clear internal audio buffers
                    oww_model.reset()
                    
                    time.sleep(2.0)
    except KeyboardInterrupt:
        pass
    finally:
        audio.terminate()

if __name__ == "__main__":
    listen_and_transcribe()
