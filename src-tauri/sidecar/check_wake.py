"""Wake-word diagnostic: prints live "hey jen" scores.

Run it, say "Hey Jen" a few times, and watch the scores:
    python src-tauri/sidecar/check_wake.py --seconds 20
    python src-tauri/sidecar/check_wake.py --device 5

Scores above 0.5 mean the model hears the phrase; the app triggers at
>= 0.5 with two supporting frames.
"""

import argparse
import os
import sys
import time

import numpy as np
import pyaudio
from openwakeword.model import Model

CHUNK = 1280
RATE = 16000


def get_resource_path(relative_path: str) -> str:
    base_path = os.path.dirname(os.path.abspath(__file__))
    candidates = [
        os.path.join(base_path, relative_path),
        os.path.join(os.path.dirname(base_path), relative_path),
    ]
    for c in candidates:
        if os.path.exists(c):
            return c
    return candidates[0]


def main():
    ap = argparse.ArgumentParser(description="Jen wake word diagnostic")
    ap.add_argument("--seconds", type=float, default=20.0)
    ap.add_argument("--device", type=int, default=None, help="PyAudio input device index")
    args = ap.parse_args()

    model_path = get_resource_path("hey_jen.onnx")
    if not os.path.exists(model_path):
        print(f"ERROR: hey_jen.onnx not found at {model_path}")
        return 1
    print(f"model: {model_path}")

    model = Model(wakeword_models=[model_path], inference_framework="onnx")

    pa = pyaudio.PyAudio()
    try:
        stream = pa.open(
            format=pyaudio.paInt16,
            channels=1,
            rate=RATE,
            input=True,
            input_device_index=args.device,
            frames_per_buffer=CHUNK,
        )
    except Exception as e:
        print(f"ERROR: could not open input device: {e}")
        pa.terminate()
        return 1

    print(f'listening {args.seconds:.0f}s - say "Hey Jen" now...')
    peak_overall = 0.0
    peak_window = 0.0
    last_print = time.time()
    started = time.time()

    try:
        while time.time() - started < args.seconds:
            data = stream.read(CHUNK, exception_on_overflow=False)
            frame = np.frombuffer(data, dtype=np.int16)
            rms = float(np.sqrt(np.mean(frame.astype(np.float32) ** 2)))

            prediction = model.predict(frame)
            for name, prob in prediction.items():
                peak_overall = max(peak_overall, prob)
                peak_window = max(peak_window, prob)

            now = time.time()
            if now - last_print >= 1.0:
                print(f"  peak {peak_window:.3f}   mic rms {rms:.0f}")
                peak_window = 0.0
                last_print = now
    except KeyboardInterrupt:
        pass
    finally:
        stream.stop_stream()
        stream.close()
        pa.terminate()

    print(f"\nhighest score in this run: {peak_overall:.3f}")
    if peak_overall >= 0.5:
        print("Wake word is detectable. If the app misses it, lower the app thresholds.")
    elif peak_overall >= 0.2:
        print("Marginal: the model hears something but below threshold. Try speaking")
        print("closer to the mic, or use a different input device in Settings.")
    else:
        print("Not recognized: the model did not match your pronunciation/mic.")
        print("Try a different input device, or retrain hey_jen.onnx.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
