import asyncio
import base64
import edge_tts
import os
import tempfile
import threading

DEFAULT_VOICE = "en-US-JennyNeural"

def generate_tts_audio(text, voice=None):
    """Generate TTS audio and return base64-encoded MP3 bytes. Thread-safe."""
    if voice is None:
        voice = os.environ.get("JEN_TTS_VOICE", DEFAULT_VOICE)

    async def _generate():
        communicate = edge_tts.Communicate(text, voice)
        tmp = tempfile.mktemp(suffix=".mp3")
        try:
            await communicate.save(tmp)
            with open(tmp, "rb") as f:
                return base64.b64encode(f.read()).decode("ascii")
        finally:
            if os.path.exists(tmp):
                os.remove(tmp)

    return asyncio.run(_generate())


def generate_tts_audio_threaded(text, voice=None, callback=None):
    """Generate TTS in a background thread, call callback(base64_data) when done."""
    def _worker():
        try:
            data = generate_tts_audio(text, voice)
            if callback:
                callback(data)
        except Exception as e:
            if callback:
                callback(None)

    thread = threading.Thread(target=_worker, daemon=True)
    thread.start()
    return thread
