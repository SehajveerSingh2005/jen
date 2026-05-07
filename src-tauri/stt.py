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

# Disable pyautogui failsafe to prevent crashes from rapid mouse movements
pyautogui.FAILSAFE = False

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
    "media_control": [
        "pause",
        "resume",
        "next",
        "skip",
        "previous",
        "back",
        "play",
        "stop music",
        "pause music",
        "play music",
        "resume music",
        "skip 5 seconds",
        "rewind 5 seconds",
        "forward",
        "rewind"
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
                for win in windows:
                    if app_name.lower() in win.title.lower():
                        target_win = win
                        break
            else:
                target_win = gw.getActiveWindow()

            if target_win:
                try:
                    if is_close:
                        target_win.close()
                    elif is_minimize:
                        target_win.minimize()
                    elif is_maximize:
                        target_win.maximize()
                    elif is_focus:
                        if target_win.isMinimized:
                            target_win.restore()
                        # Tap Alt to ensure we can set foreground window on Windows
                        pyautogui.press('alt')
                        target_win.activate()
                    return True
                except Exception as e:
                    print(f"DEBUG Error manipulating window: {e}", file=sys.stderr)
            
            # Fallback to Alt+Tab for generic "switch" if no target found
            if is_focus and not app_name:
                pyautogui.hotkey('alt', 'tab')
                
        elif intent == "media_control":
            if any(k in raw_text for k in ["pause", "resume", "play", "stop"]):
                pyautogui.press('playpause')
            elif any(k in raw_text for k in ["next", "skip"]) and "5 seconds" not in raw_text:
                pyautogui.press('nexttrack')
            elif any(k in raw_text for k in ["previous", "back", "rewind"]) and "5 seconds" not in raw_text:
                pyautogui.press('prevtrack')
            elif "skip 5 seconds" in raw_text or "forward" in raw_text:
                pyautogui.press('right')
            elif "rewind 5 seconds" in raw_text or "rewind" in raw_text:
                pyautogui.press('left')
                
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
                    params["app"] = match.group(1).strip()
                    break
    elif detected_intent == "google_search":
        for p in INTENTS["google_search"]:
            regex = p.replace("{query}", "(.*)")
            match = re.search(regex, text)
            if match:
                params["query"] = match.group(1).strip()
                break

    if highest_score > 70:
        return {"intent": detected_intent, "params": params, "score": highest_score}
    return None

def listen_and_transcribe():
    try:
        from openwakeword.utils import download_models
        download_models()
    except:
        pass

    script_dir = os.path.dirname(os.path.abspath(__file__))
    model_path = os.path.join(script_dir, "hey_jen.onnx")
    wakeword_models = [model_path] if os.path.exists(model_path) else ["hey_jarvis"]
    
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

            while True:
                data = stream.read(CHUNK, exception_on_overflow=False)
                audio_data = np.frombuffer(data, dtype=np.int16)
                prediction = oww_model.predict(audio_data)
                
                detected = False
                for wakeword, probability in prediction.items():
                    if probability > 0.5:
                        print(json.dumps({"status": "detected", "wakeword": wakeword}), flush=True)
                        detected = True
                        break
                
                if detected:
                    stream.stop_stream()
                    stream.close()
                    
                    with sr.Microphone(sample_rate=16000) as source:
                        try:
                            print(json.dumps({"status": "recording"}), flush=True)
                            audio_clip = r.listen(source, timeout=5, phrase_time_limit=5)
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
                        break 
    except KeyboardInterrupt:
        pass
    finally:
        audio.terminate()

if __name__ == "__main__":
    listen_and_transcribe()
