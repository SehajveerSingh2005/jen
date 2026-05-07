import sys
import os
import json
import numpy as np
import openwakeword
from openwakeword.model import Model
import speech_recognition as sr
import pyaudio
import re
from thefuzz import process, fuzz

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
    "system_status": [
        "how are you",
        "what's your name",
        "who are you",
        "status check"
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
        "resume music"
    ]
}

def parse_intent(text):
    text = text.lower().strip()
    
    # 1. Direct Matching / Fuzzy Match
    best_match = None
    highest_score = 0
    detected_intent = None
    
    for intent, patterns in INTENTS.items():
        # Check against patterns
        for pattern in patterns:
            # Simple template matching
            clean_pattern = re.sub(r"\{.*?\}", "", pattern).strip()
            score = fuzz.partial_ratio(text, clean_pattern)
            
            if score > highest_score:
                highest_score = score
                detected_intent = intent
                best_match = pattern

    # 2. Parameter Extraction
    params = {}
    if detected_intent == "open_app":
        # Extract app name
        for p in INTENTS["open_app"]:
            regex = p.replace("{app}", "(.*)")
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
    # Ensure models are downloaded
    try:
        from openwakeword.utils import download_models
        download_models()
    except:
        pass

    # Initialize openWakeWord
    script_dir = os.path.dirname(os.path.abspath(__file__))
    model_path = os.path.join(script_dir, "hey_jen.onnx")
    
    if os.path.exists(model_path):
        wakeword_models = [model_path]
    else:
        # Fallback to absolute path or default
        wakeword_models = ["hey_jarvis"]
    
    oww_model = Model(
        wakeword_models=wakeword_models, 
        inference_framework="onnx"
    )
    
    r = sr.Recognizer()
    
    FORMAT = pyaudio.paInt16
    CHANNELS = 1
    RATE = 16000
    CHUNK = 1280
    
    audio = pyaudio.PyAudio()
    
    print(json.dumps({"status": "ready"}), flush=True)

    try:
        while True:
            # Open stream for wake word detection
            stream = audio.open(format=FORMAT, channels=CHANNELS, rate=RATE, input=True, frames_per_buffer=CHUNK)
            
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
                    # Close stream to free microphone for SpeechRecognition
                    stream.stop_stream()
                    stream.close()
                    
                    with sr.Microphone(sample_rate=16000) as source:
                        try:
                            # Immediate feedback to Rust
                            print(json.dumps({"status": "recording"}), flush=True)
                            audio_clip = r.listen(source, timeout=5, phrase_time_limit=5)
                            print(json.dumps({"status": "transcribing"}), flush=True)
                            text = r.recognize_google(audio_clip)
                            
                            # Parse Intent
                            result = parse_intent(text)
                            if result:
                                if result["intent"] == "open_app":
                                    command_text = f"open {result['params'].get('app', '')}"
                                elif result["intent"] == "google_search":
                                    command_text = f"search google for {result['params'].get('query', '')}"
                                else:
                                    command_text = text
                                
                                print(json.dumps({"status": "success", "text": command_text, "intent": result}), flush=True)
                            else:
                                print(json.dumps({"status": "success", "text": text}), flush=True)
                                
                        except sr.UnknownValueError:
                            print(json.dumps({"status": "error", "message": "unknown"}), flush=True)
                        except Exception as e:
                            print(json.dumps({"status": "error", "message": str(e)}), flush=True)
                        
                        print(json.dumps({"status": "ready"}), flush=True)
                        # Re-open stream for next detection
                        break 

    except KeyboardInterrupt:
        pass
    finally:
        audio.terminate()

if __name__ == "__main__":
    listen_and_transcribe()
