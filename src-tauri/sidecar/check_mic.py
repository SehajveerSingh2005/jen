"""Microphone diagnostic for Jen.

Reports capture-device RMS levels so you can tell whether the OS is
delivering real audio or pure silence (muted mic, privacy block, wrong
default device, or a dead sample-rate config).

Run while talking normally for best results:
    python src-tauri/sidecar/check_mic.py --seconds 3
"""

import argparse
import sys

import numpy as np
import pyaudio

CHUNK = 1280


def rms_of(buf: bytes) -> float:
    a = np.frombuffer(buf, dtype=np.int16).astype(np.float32)
    if a.size == 0:
        return 0.0
    return float(np.sqrt(np.mean(a * a)))


def probe(pa, idx, rate, seconds):
    try:
        stream = pa.open(
            format=pyaudio.paInt16,
            channels=1,
            rate=rate,
            input=True,
            input_device_index=idx,
            frames_per_buffer=CHUNK,
        )
    except Exception as e:
        return None, str(e)

    peak = 0.0
    chunks = max(1, int(seconds * rate / CHUNK))
    try:
        for _ in range(chunks):
            buf = stream.read(CHUNK, exception_on_overflow=False)
            peak = max(peak, rms_of(buf))
    finally:
        stream.stop_stream()
        stream.close()
    return peak, None


def verdict(peak):
    if peak == 0.0:
        return "SILENT (all zeros)"
    if peak < 20:
        return "near-silent"
    if peak < 80:
        return "quiet (below wake gate)"
    return "OK"


def main():
    ap = argparse.ArgumentParser(description="Jen microphone diagnostic")
    ap.add_argument("--seconds", type=float, default=2.0, help="capture seconds per probe")
    args = ap.parse_args()

    pa = pyaudio.PyAudio()
    try:
        try:
            default_idx = pa.get_default_input_device_info()["index"]
        except Exception:
            default_idx = None

        print("=== Input devices ===")
        inputs = []
        for i in range(pa.get_device_count()):
            info = pa.get_device_info_by_index(i)
            if info.get("maxInputChannels", 0) > 0:
                inputs.append(i)
                mark = "  <-- default" if i == default_idx else ""
                print(f"  [{i}] {info['name']}{mark}")
                print(f"       channels={info['maxInputChannels']} defaultRate={int(info['defaultSampleRate'])}")

        if not inputs:
            print("No input devices found.")
            return 1

        if default_idx is not None:
            print(f"\n=== Default device [{default_idx}] (speak now) ===")
            for rate in (16000, 48000):
                peak, err = probe(pa, default_idx, rate, args.seconds)
                if err:
                    print(f"  {rate} Hz: open failed: {err}")
                else:
                    print(f"  {rate} Hz: peak rms={peak:.0f}  -> {verdict(peak)}")

        print(f"\n=== All inputs at 16000 Hz (speak now) ===")
        for i in inputs:
            peak, err = probe(pa, i, 16000, args.seconds)
            if err:
                print(f"  [{i}] open failed: {err}")
            else:
                print(f"  [{i}] peak rms={peak:.0f}  -> {verdict(peak)}")
    finally:
        pa.terminate()

    print("\nIf every device shows SILENT: check Windows Settings > Privacy & security >")
    print("Microphone (enable for desktop apps) and the mic mute key / input level slider.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
