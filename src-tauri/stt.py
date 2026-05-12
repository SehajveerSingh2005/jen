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

# Disable TQDM progress bars
os.environ["TQDM_DISABLE"] = "1"

# Disable pyautogui failsafe to prevent crashes from rapid mouse movements
pyautogui.FAILSAFE = False

# Global flag for manual trigger
trigger_manual = False

def log_debug(msg):
    try:
        with open("stt_debug.log", "a") as f:
            f.write(f"{time.ctime()}: {msg}\n")
    except:
        pass

def listen_stdin():
    global trigger_manual
    while True:
        try:
            line = sys.stdin.readline()
            if not line:
                os._exit(0)
            if line.strip() == "trigger":
                trigger_manual = True
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
                    prediction = oww_model.predict(audio_data)
                    for wakeword, prob in prediction.items():
                        if prob > 0.3:
                            print(json.dumps({"status": "detected", "wakeword": wakeword}), flush=True)
                            detected = True
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
