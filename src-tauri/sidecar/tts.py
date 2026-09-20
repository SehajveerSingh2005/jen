import asyncio
import base64
import edge_tts
import os
import tempfile
import threading
import struct

DEFAULT_VOICE = "en-US-JennyNeural"

def _get_mp3_duration(filepath):
    """Estimate MP3 duration from file size. Edge TTS outputs ~48kbps."""
    size = os.path.getsize(filepath)
    return size / 6000.0  # 48kbps = 6000 bytes/sec

def generate_tts_audio(text, voice=None):
    """Generate TTS audio and return (base64_data, word_timings).
    word_timings is estimated from audio duration and word count.
    """
    if voice is None:
        voice = os.environ.get("JEN_TTS_VOICE", DEFAULT_VOICE)

    async def _generate():
        communicate = edge_tts.Communicate(text, voice)
        tmp = tempfile.mktemp(suffix=".mp3")
        try:
            await communicate.save(tmp)
            duration = _get_mp3_duration(tmp)
            with open(tmp, "rb") as f:
                audio_b64 = base64.b64encode(f.read()).decode("ascii")

            # Estimate word timings with pauses at punctuation
            words = text.split()
            if not words:
                return audio_b64, []
            interval = duration / len(words)
            # Punctuation that warrants a pause
            pause_suffixes = {".", "!", "?", ";", ":"}
            comma_suffixes = {",", "—"}
            word_timings = []
            for i, w in enumerate(words):
                extra = 0.0
                stripped = w.rstrip(".,!?;:\"'")
                if any(w.endswith(p) for p in pause_suffixes):
                    extra = interval * 1.3  # ~1.3x pause for full stops
                elif any(w.endswith(p) for p in comma_suffixes):
                    extra = interval * 0.6  # ~0.6x pause for commas
                word_timings.append({
                    "text": w,
                    "offset": i * interval + sum(t["extra"] for t in word_timings),
                    "duration": interval,
                    "extra": extra,
                })
            return audio_b64, word_timings
        finally:
            if os.path.exists(tmp):
                os.remove(tmp)

    return asyncio.run(_generate())


def generate_tts_audio_threaded(text, voice=None, callback=None):
    """Generate TTS in a background thread, call callback(base64_data, word_timings) when done."""
    def _worker():
        try:
            data, timings = generate_tts_audio(text, voice)
            if callback:
                callback(data, timings)
        except Exception as e:
            if callback:
                callback(None, [])

    thread = threading.Thread(target=_worker, daemon=True)
    thread.start()
    return thread
