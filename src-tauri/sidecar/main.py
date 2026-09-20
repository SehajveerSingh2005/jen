"""Jen sidecar entry point.

Modes:
  daemon (default): wake word → STT → agent → TTS, with a follow-up window
                    for back-and-forth conversation. Talks JSON-lines with
                    the Rust host over stdin/stdout.
  --simulate TEXT:  run one text turn through the agent and exit (no mic,
                    no wake word). Use --dry-run to touch nothing.

Stdout is the protocol channel — never print() here, use logging (stderr).
"""

import argparse
import json
import logging
import os
import sys
import threading
import time

logging.basicConfig(
    stream=sys.stderr,
    level=logging.INFO,
    format="[jen] %(levelname)s %(message)s",
)
log = logging.getLogger("jen.main")

import protocol
from agent import Agent, AgentResult, looks_like_command
from config import SidecarConfig
from memory import MemoryStore
from protocol import emit

# --- End-of-conversation phrases (closes the follow-up window) ---
END_PHRASES = {
    "never mind", "nevermind", "that's all", "thats all", "that is all",
    "nothing", "no thanks", "no thank you", "thanks", "thank you",
    "thanks a lot", "thank you so much", "appreciate it", "that's it",
    "thats it", "that's everything", "thats everything", "i'm done",
    "im done", "we're done", "were done", "we're good", "were good",
    "all good", "okay thanks", "ok thanks", "thanks bye", "thank you bye",
    "bye bye", "ok bye", "okay bye", "see you", "see ya", "good night",
    "goodnight", "bye", "goodbye", "stop", "go away", "cancel",
    "i'm good", "im good",
}

config = SidecarConfig()
memory: MemoryStore | None = None
agent: Agent | None = None
trigger_manual = False
tts_lock = threading.Lock()
tts_pending = 0
tts_busy_until = 0.0


def get_memory() -> MemoryStore:
    global memory
    if memory is None:
        try:
            memory = MemoryStore(config.memory_path)
        except Exception as e:
            log.warning("memory.db unavailable (%s), using in-memory store", e)
            memory = MemoryStore(":memory:")
    return memory


def get_agent() -> Agent:
    global agent
    if agent is None:
        agent = Agent(config=config, memory=get_memory(), emit=emit)
    return agent


# ---------------------------------------------------------------------------
# TTS
# ---------------------------------------------------------------------------

def _tts_duration(timings: list[dict]) -> float:
    """Playback duration estimate from word timings."""
    if not timings:
        return 0.0
    last = timings[-1]
    return float(last.get("offset", 0.0)) + float(last.get("duration", 0.0)) + float(last.get("extra", 0.0))


def send_tts_async(text: str) -> None:
    """Generate TTS audio in a background thread, emit when ready.

    Tracks both generation (pending) and playback (busy_until) so the mic
    never opens while Jen is about to speak — otherwise she transcribes
    her own voice and answers herself.
    """
    if not config.tts_enabled or not text:
        return

    def _worker():
        global tts_pending, tts_busy_until
        with tts_lock:
            tts_pending += 1
        try:
            from tts import generate_tts_audio

            data, timings = generate_tts_audio(text, config.tts_voice)
            if data:
                with tts_lock:
                    tts_busy_until = time.time() + _tts_duration(timings) + 0.5
                emit({"status": "tts_audio", "data": data, "words": timings, "text": text})
        except Exception as e:
            log.warning("TTS error: %s", e)
        finally:
            with tts_lock:
                tts_pending -= 1

    threading.Thread(target=_worker, daemon=True).start()


def wait_for_tts(timeout: float = 30.0) -> None:
    """Block until Jen has finished generating and speaking (or timeout)."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        with tts_lock:
            busy = tts_pending > 0 or tts_busy_until > time.time()
        if not busy:
            return
        time.sleep(0.1)


def _preview_voice(voice: str) -> None:
    def _worker():
        try:
            from tts import generate_tts_audio

            data, _ = generate_tts_audio("Hello! I'm Jen, your desktop assistant.", voice)
            if data:
                emit({"status": "tts_audio", "data": data})
        except Exception as e:
            log.warning("preview TTS error: %s", e)

    threading.Thread(target=_worker, daemon=True).start()


# ---------------------------------------------------------------------------
# stdin command protocol (from Rust)
# ---------------------------------------------------------------------------

def handle_command(cmd: str) -> None:
    """Handle one stdin command line. Exposed for tests."""
    global trigger_manual, agent

    if cmd == "trigger":
        trigger_manual = True
    elif cmd == "protect:1":
        config.protect_sensitive = True
    elif cmd == "protect:0":
        config.protect_sensitive = False
    elif cmd == "tts:1":
        config.tts_enabled = True
    elif cmd == "tts:0":
        config.tts_enabled = False
    elif cmd.startswith("tts_voice:"):
        config.tts_voice = cmd.split(":", 1)[1].strip() or config.tts_voice
    elif cmd.startswith("preview_voice:"):
        voice = cmd.split(":", 1)[1].strip()
        if voice:
            _preview_voice(voice)
    elif cmd.startswith("ai_mode:"):
        config.set_ai_mode(cmd.split(":", 1)[1].strip())
        if agent:
            agent.reset_client()
        log.info("ai_mode → %s", config.ai_mode)
    elif cmd.startswith("ai_local_url:"):
        config.local_base_url = cmd.split(":", 1)[1].strip()
        if agent:
            agent.reset_client()
        log.info("local LLM url → %s", config.local_base_url)
        # Prime the KV cache so the first real command is fast
        threading.Thread(target=lambda: get_agent().warmup(), daemon=True).start()
    elif cmd.startswith("ai_cloud:"):
        # Format: ai_cloud:<api_key>:<base_url>:<model>
        parts = cmd.split(":", 3)
        if len(parts) >= 4:
            config.cloud_api_key = parts[1]
            config.cloud_base_url = parts[2].rstrip("/")
            config.cloud_model = parts[3]
            if agent:
                agent.reset_client()
            log.info("cloud AI configured: %s / %s", config.cloud_base_url, config.cloud_model)
    elif cmd.startswith("input_device:"):
        raw = cmd.split(":", 1)[1].strip()
        if raw in ("", "default"):
            config.input_device_index = None
        else:
            try:
                config.input_device_index = int(raw)
            except ValueError:
                config.input_device_index = None
        log.info(
            "input device → %s",
            "default" if config.input_device_index is None else config.input_device_index,
        )
    elif cmd.startswith("personality:"):
        config.set_personality(cmd.split(":", 1)[1].strip())
        log.info("personality → %s", config.personality)
    elif cmd.startswith("followup:"):
        config.followup_enabled = cmd.split(":", 1)[1].strip() == "1"
        log.info("follow-up window → %s", "on" if config.followup_enabled else "off")
    elif cmd.startswith("wake_sensitivity:"):
        config.set_wake_sensitivity(cmd.split(":", 1)[1].strip())
        log.info(
            "wake sensitivity → %s %s",
            config.wake_sensitivity,
            config.wake_thresholds(),
        )
    elif cmd.startswith("memory_path:"):
        global memory
        path = cmd.split(":", 1)[1].strip()
        if path and path != config.memory_path:
            config.memory_path = path
            if memory is not None:
                memory.close()
                memory = None
            if agent is not None:
                agent.memory = get_memory()
            log.info("memory path → %s", path)


def listen_stdin() -> None:
    while True:
        try:
            line = sys.stdin.readline()
            if not line:
                os._exit(0)
            handle_command(line.strip())
        except Exception:
            os._exit(0)


# ---------------------------------------------------------------------------
# Conversation turn
# ---------------------------------------------------------------------------

def run_turn(text: str) -> AgentResult:
    """One full turn: agent processes text, status events + TTS go out."""
    result = get_agent().process(text)
    if result.ok:
        emit({"status": "success", "text": text})
    else:
        emit({"status": "error", "message": result.error or "agent_error"})
    if result.spoken:
        log.info("spoken: %s", result.spoken)
        send_tts_async(result.spoken)
    return result


def is_end_phrase(text: str) -> bool:
    cleaned = text.lower().strip().strip(".!?, ")
    if cleaned in END_PHRASES:
        return True
    # Short utterances like "okay goodbye" or "never mind then". Guard against
    # commands that merely start with a courtesy word ("thanks, open chrome").
    if len(cleaned.split()) <= 4 and not looks_like_command(cleaned):
        return any(
            cleaned.startswith(p + " ") or cleaned.endswith(" " + p)
            for p in END_PHRASES
        )
    return False


def run_followup_window(r, source) -> None:
    """Optional back-and-forth window after a turn (off by default).

    Disabled by default because the open mic can pick up Jen's own TTS
    replies and start a feedback loop. When enabled, we wait for TTS
    playback to finish before listening again.
    """
    if not config.followup_enabled:
        return
    while True:
        emit({"status": "followup"})
        wait_for_tts()
        text = _record_and_transcribe(r, source, timeout=config.followup_seconds)
        if text is None:
            break  # silence → session over
        log.info("follow-up: %s", text)
        if is_end_phrase(text):
            if config.personality == "conversational":
                send_tts_async("Okay!")
            break
        run_turn(text)


# ---------------------------------------------------------------------------
# Daemon mode: wake word + follow-up conversation window
# ---------------------------------------------------------------------------

def get_resource_path(relative_path: str) -> str:
    if hasattr(sys, "_MEIPASS"):
        base_path = sys._MEIPASS
    else:
        base_path = os.path.dirname(os.path.abspath(__file__))
    candidates = [
        os.path.join(base_path, relative_path),
        os.path.join(os.path.dirname(base_path), relative_path),
    ]
    for c in candidates:
        if os.path.exists(c):
            return c
    return candidates[0]


def list_input_devices(pa) -> list[dict]:
    """Enumerate capture devices for the Settings UI."""
    devices = []
    for i in range(pa.get_device_count()):
        try:
            info = pa.get_device_info_by_index(i)
        except Exception:
            continue
        if info.get("maxInputChannels", 0) <= 0:
            continue
        try:
            host_api = str(pa.get_host_api_info_by_index(info["hostApi"])["name"])
        except Exception:
            host_api = ""
        devices.append({
            "index": i,
            "name": " ".join(str(info.get("name", "")).split()),
            "host_api": host_api,
        })
    return devices


def default_input_index(pa) -> int | None:
    try:
        return int(pa.get_default_input_device_info()["index"])
    except Exception:
        return None


def _record_and_transcribe(r, source, timeout: float, phrase_limit: float = 20):
    """Returns transcribed text, or None on timeout/unintelligible."""
    import speech_recognition as sr

    emit({"status": "recording"})
    r.adjust_for_ambient_noise(source, duration=0.3)
    r.pause_threshold = 1.2
    r.energy_threshold = 300
    try:
        audio_clip = r.listen(source, timeout=timeout, phrase_time_limit=phrase_limit)
    except sr.WaitTimeoutError:
        return None
    emit({"status": "transcribing"})
    try:
        return r.recognize_google(audio_clip)
    except sr.UnknownValueError:
        return None
    except sr.RequestError as e:
        log.warning("STT service unavailable: %s", e)
        return None


def listen_and_transcribe() -> None:
    global trigger_manual

    import numpy as np
    import speech_recognition as sr
    from openwakeword.model import Model

    hey_jen_path = get_resource_path("hey_jen.onnx")
    hey_jarvis_path = get_resource_path(os.path.join("models", "hey_jarvis.onnx"))
    melspec_path = get_resource_path(os.path.join("models", "melspectrogram.onnx"))
    embedding_path = get_resource_path(os.path.join("models", "embedding_model.onnx"))

    wakeword_models = []
    if os.path.exists(hey_jen_path):
        wakeword_models.append(hey_jen_path)
    if not wakeword_models:
        wakeword_models.append(hey_jarvis_path if os.path.exists(hey_jarvis_path) else "hey_jarvis")

    model_kwargs = {"wakeword_models": wakeword_models, "inference_framework": "onnx"}
    if os.path.exists(melspec_path):
        model_kwargs["melspec_model_path"] = melspec_path
    if os.path.exists(embedding_path):
        model_kwargs["embedding_model_path"] = embedding_path

    oww_model = Model(**model_kwargs)
    r = sr.Recognizer()

    import pyaudio

    FORMAT, CHANNELS, RATE, CHUNK = pyaudio.paInt16, 1, 16000, 1280

    try:
        audio = pyaudio.PyAudio()
    except Exception:
        audio = None

    if audio is not None:
        try:
            emit({
                "status": "input_devices",
                "devices": list_input_devices(audio),
                "default": default_input_index(audio),
            })
        except Exception as e:
            log.warning("input device enumeration failed: %s", e)

    emit({"status": "ready"})
    log.info("sidecar ready (ai_mode=%s, personality=%s)", config.ai_mode, config.personality)

    while True:
        # Manual trigger bypasses audio pipeline entirely
        if trigger_manual:
            trigger_manual = False
            emit({"status": "detected", "wakeword": "manual"})
            try:
                with sr.Microphone(device_index=config.input_device_index, sample_rate=16000) as source:
                    text = _record_and_transcribe(r, source, timeout=7)
                    if text:
                        log.info("heard: %s", text)
                        run_turn(text)
                    else:
                        emit({"status": "error", "message": "unknown"})
                        if config.personality == "conversational":
                            send_tts_async("Sorry, I didn't catch that.")

                    run_followup_window(r, source)

                    emit({"status": "hide"})
            except Exception:
                emit({"status": "error", "message": "mic_init_fail"})
            emit({"status": "ready"})
            oww_model.reset()
            time.sleep(1.0)
            continue

        try:
            if audio is None:
                try:
                    audio = pyaudio.PyAudio()
                except Exception:
                    time.sleep(3.0)
                    continue

            stream = None
            try:
                stream = audio.open(
                    format=FORMAT,
                    channels=CHANNELS,
                    rate=RATE,
                    input=True,
                    input_device_index=config.input_device_index,
                    frames_per_buffer=CHUNK,
                )
                for _ in range(10):
                    try:
                        stream.read(CHUNK, exception_on_overflow=False)
                    except Exception:
                        pass

                detected = False
                history: dict[str, list[float]] = {}
                last_rms_log = 0.0
                while True:
                    if trigger_manual:
                        trigger_manual = False
                        emit({"status": "detected", "wakeword": "manual"})
                        detected = True
                        break

                    try:
                        data = stream.read(CHUNK, exception_on_overflow=False)
                    except Exception:
                        break  # re-init

                    audio_data = np.frombuffer(data, dtype=np.int16)

                    # RMS energy gate: skip silence, but never discard speech.
                    # A hot mic (common with Realtek arrays) produces room noise
                    # around 900 and speech above 9500, so the old upper gate was
                    # silently dropping the exact frames the wake model needs.
                    rms = float(np.sqrt(np.mean(audio_data.astype(np.float32) ** 2)))
                    now = time.time()
                    if now - last_rms_log > 30.0:
                        log.info("mic level rms=%.0f (floor 80, clip 20000)", rms)
                        last_rms_log = now
                    if rms < 80.0:
                        continue
                    if rms > 20000.0:
                        log.info("input clipping (rms=%.0f), frame skipped", rms)
                        continue

                    prediction = oww_model.predict(audio_data)

                    # Multi-frame debounce (transient noises spike 1 frame;
                    # speech sustains). Thresholds come from the user's wake
                    # word sensitivity setting; medium = tuned v0.4.0b values.
                    peak_min, frame_min = config.wake_thresholds()
                    for wakeword, prob in prediction.items():
                        history.setdefault(wakeword, []).append(prob)
                        if len(history[wakeword]) > 4:
                            history[wakeword].pop(0)
                        recent = history[wakeword]
                        peak_prob = max(recent)
                        high_frame_count = sum(1 for p in recent if p > frame_min)
                        if peak_prob >= peak_min and high_frame_count >= 2:
                            log.info("wake word: %s (prob=%.2f)", wakeword, peak_prob)
                            emit({"status": "detected", "wakeword": wakeword})
                            detected = True
                            history.clear()
                            break
                    if detected:
                        break
            except Exception:
                if stream:
                    try:
                        stream.close()
                    except Exception:
                        pass
                if audio:
                    try:
                        audio.terminate()
                    except Exception:
                        pass
                audio = None
                time.sleep(2.0)
                continue
            finally:
                if stream:
                    try:
                        stream.stop_stream()
                        stream.close()
                    except Exception:
                        pass

            if detected:
                try:
                    with sr.Microphone(device_index=config.input_device_index, sample_rate=16000) as source:
                        # First turn
                        text = _record_and_transcribe(r, source, timeout=7)
                        if text:
                            log.info("heard: %s", text)
                            run_turn(text)
                        else:
                            emit({"status": "error", "message": "unknown"})
                            if config.personality == "conversational":
                                send_tts_async("Sorry, I didn't catch that.")

                        run_followup_window(r, source)

                        emit({"status": "hide"})
                except Exception:
                    emit({"status": "error", "message": "mic_init_fail"})
                    if audio:
                        try:
                            audio.terminate()
                        except Exception:
                            pass
                    audio = None

                emit({"status": "ready"})
                oww_model.reset()
                time.sleep(1.0)
        except BaseException as e:
            log.exception("audio loop error: %s", e)
            audio = None
            time.sleep(5.0)


# ---------------------------------------------------------------------------
# Simulate mode: voice-free testing of the full agent pipeline
# ---------------------------------------------------------------------------

def run_simulation(args) -> int:
    if args.personality:
        config.set_personality(args.personality)
    config.set_ai_mode(args.mode)
    if args.local_url:
        config.local_base_url = args.local_url
    if args.cloud_key:
        config.cloud_api_key = args.cloud_key
    if args.cloud_url:
        config.cloud_base_url = args.cloud_url
    if args.cloud_model:
        config.cloud_model = args.cloud_model

    events: list[dict] = []
    captured_emit = events.append if args.dry_run else emit

    mem = MemoryStore(args.memory)
    sim_agent = Agent(config=config, memory=mem, emit=captured_emit, dry_run=args.dry_run)

    texts = [args.simulate] if args.simulate else [l.strip() for l in sys.stdin if l.strip()]
    exit_code = 0

    for text in texts:
        started = time.perf_counter()
        result = sim_agent.process(text)
        elapsed_ms = (time.perf_counter() - started) * 1000

        report = {
            "input": text,
            "ok": result.ok,
            "tools_run": result.tools_run,
            "spoken": result.spoken,
            "elapsed_ms": round(elapsed_ms, 1),
        }
        if args.dry_run:
            report["tool_messages"] = [r.message for r in result.tool_results]
            report["events"] = list(events)
            events.clear()
            facts = mem.facts()
            if facts:
                report["facts"] = [{"key": k, "value": v} for k, v in facts]

        sys.stdout.write(json.dumps(report) + "\n")
        sys.stdout.flush()
        if not result.ok:
            exit_code = 1

    mem.close()
    return exit_code


# ---------------------------------------------------------------------------
# Dependency preloading
# ---------------------------------------------------------------------------

def preload_deps() -> None:
    """Import heavy native dependencies before the stdin thread starts.

    On Windows, the first `import numpy` deadlocks if another thread is
    blocked in a pipe read (numpy/OpenMP init vs. the blocked read on fd 0).
    Importing everything up front on the main thread avoids this entirely.
    """
    import numpy  # noqa: F401
    import onnxruntime  # noqa: F401
    import pyaudio  # noqa: F401
    import speech_recognition  # noqa: F401
    from openwakeword.model import Model  # noqa: F401

    try:
        import edge_tts  # noqa: F401
    except Exception:
        log.warning("edge_tts unavailable, TTS disabled")


def main() -> None:
    parser = argparse.ArgumentParser(description="Jen sidecar")
    parser.add_argument("--simulate", metavar="TEXT", help="run one text turn through the agent and exit")
    parser.add_argument("--simulate-stdin", action="store_true", help="like --simulate, but read turns from stdin lines")
    parser.add_argument("--dry-run", action="store_true", help="report what tools WOULD do without touching the OS")
    parser.add_argument("--mode", default="local", choices=["off", "local", "cloud"], help="AI mode (default: local)")
    parser.add_argument("--local-url", help="local LLM base URL", default=None)
    parser.add_argument("--cloud-key", help="cloud API key", default=None)
    parser.add_argument("--cloud-url", help="cloud base URL", default=None)
    parser.add_argument("--cloud-model", help="cloud model id", default=None)
    parser.add_argument("--personality", choices=["minimal", "conversational"], default=None)
    parser.add_argument("--memory", default=":memory:", help="memory db path (default: in-memory)")
    args = parser.parse_args()

    if args.simulate or args.simulate_stdin:
        sys.exit(run_simulation(args))

    preload_deps()
    threading.Thread(target=listen_stdin, daemon=True).start()
    try:
        listen_and_transcribe()
    except BaseException as e:
        log.exception("FATAL: %s", e)
        os._exit(0)


if __name__ == "__main__":
    main()
