"""Process-level regression tests for the sidecar entry point.

Guards against the Windows deadlock where a thread blocked on
``sys.stdin.readline()`` prevents the first ``import numpy`` from ever
completing. That bug froze the sidecar before it emitted ``ready``, so the
wake word loop and manual trigger never ran.
"""

import json
import os
import queue
import subprocess
import sys
import threading
import time

import pytest

import main as sidecar_main

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SIDECAR = os.path.join(REPO_ROOT, "src-tauri", "sidecar", "main.py")

READY_TIMEOUT = 25.0
EVENT_TIMEOUT = 8.0


def _audio_deps_available() -> bool:
    try:
        import numpy  # noqa: F401
        import onnxruntime  # noqa: F401
        import pyaudio  # noqa: F401
        import speech_recognition  # noqa: F401
        import openwakeword  # noqa: F401
    except Exception:
        return False
    return True


def _read_events(stream, out: "queue.Queue[str]"):
    for line in stream:
        out.put(line.decode("utf-8", errors="replace").strip())


def _wait_for_event(lines, deadline, predicate):
    """Pull stdout lines until an event matches, or the deadline passes."""
    while time.time() < deadline:
        remaining = deadline - time.time()
        try:
            line = lines.get(timeout=max(0.1, min(1.0, remaining)))
        except queue.Empty:
            continue
        if not line.startswith("{"):
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if predicate(event):
            return event
    return None


@pytest.mark.skipif(not _audio_deps_available(), reason="audio/LLM deps not installed")
def test_sidecar_starts_and_handles_manual_trigger():
    proc = subprocess.Popen(
        [sys.executable, "-u", SIDECAR],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=REPO_ROOT,
    )
    lines: "queue.Queue[str]" = queue.Queue()

    try:
        reader = threading.Thread(target=_read_events, args=(proc.stdout, lines), daemon=True)
        reader.start()

        ready = _wait_for_event(
            lines,
            time.time() + READY_TIMEOUT,
            lambda e: e.get("status") == "ready",
        )
        assert ready is not None, "sidecar never emitted ready (startup deadlock?)"

        proc.stdin.write(b"trigger\n")
        proc.stdin.flush()

        detected = _wait_for_event(
            lines,
            time.time() + EVENT_TIMEOUT,
            lambda e: e.get("status") == "detected",
        )
        assert detected is not None, "manual trigger was not acknowledged"
        assert detected.get("wakeword") == "manual"
    finally:
        proc.kill()
        proc.wait(timeout=10)


class _FakePyAudio:
    """Minimal PyAudio stand-in for device enumeration tests."""

    _devices = {
        0: {"name": "Speakers", "maxInputChannels": 0, "hostApi": 0},
        1: {"name": "Microphone Array", "maxInputChannels": 2, "hostApi": 0},
        2: {"name": "Headset Mic", "maxInputChannels": 1, "hostApi": 1},
    }
    _host_apis = {0: {"name": "MME"}, 1: {"name": "Windows DirectSound"}}

    def get_device_count(self):
        return len(self._devices)

    def get_device_info_by_index(self, index):
        return self._devices[index]

    def get_host_api_info_by_index(self, index):
        return self._host_apis[index]


def test_handle_input_device_command():
    original = sidecar_main.config.input_device_index
    try:
        sidecar_main.handle_command("input_device:5")
        assert sidecar_main.config.input_device_index == 5

        sidecar_main.handle_command("input_device:default")
        assert sidecar_main.config.input_device_index is None

        sidecar_main.handle_command("input_device:not-a-number")
        assert sidecar_main.config.input_device_index is None
    finally:
        sidecar_main.config.input_device_index = original


def test_handle_followup_command():
    original = sidecar_main.config.followup_enabled
    try:
        sidecar_main.handle_command("followup:1")
        assert sidecar_main.config.followup_enabled is True

        sidecar_main.handle_command("followup:0")
        assert sidecar_main.config.followup_enabled is False
    finally:
        sidecar_main.config.followup_enabled = original


def test_wait_for_tts_returns_immediately_when_idle():
    original = sidecar_main.tts_busy_until
    try:
        sidecar_main.tts_busy_until = 0.0
        started = time.time()
        sidecar_main.wait_for_tts()
        assert time.time() - started < 0.2
    finally:
        sidecar_main.tts_busy_until = original


def test_list_input_devices_filters_outputs():
    devices = sidecar_main.list_input_devices(_FakePyAudio())
    assert [d["index"] for d in devices] == [1, 2]
    assert devices[0]["name"] == "Microphone Array"
    assert devices[0]["host_api"] == "MME"
    assert devices[1]["host_api"] == "Windows DirectSound"


def test_end_phrases_match_short_utterances():
    assert sidecar_main.is_end_phrase("goodbye")
    assert sidecar_main.is_end_phrase("Okay, goodbye!")
    assert sidecar_main.is_end_phrase("never mind then")
    assert sidecar_main.is_end_phrase("no thanks")
    assert not sidecar_main.is_end_phrase(
        "goodbye if you need anything in the future don't hesitate to ask"
    )
    assert not sidecar_main.is_end_phrase("open chrome")


def test_end_phrases_thanks_variants():
    assert sidecar_main.is_end_phrase("thank you")
    assert sidecar_main.is_end_phrase("Thank you so much!")
    assert sidecar_main.is_end_phrase("thanks a lot")
    assert sidecar_main.is_end_phrase("okay thanks")
    assert sidecar_main.is_end_phrase("see you")
    assert sidecar_main.is_end_phrase("I'm done")
    assert sidecar_main.is_end_phrase("that's everything")


def test_end_phrase_does_not_swallow_commands():
    # A courtesy word followed by a real command must not end the session
    assert not sidecar_main.is_end_phrase("thanks, open chrome")
    assert not sidecar_main.is_end_phrase("thanks now play music")


def test_wait_for_tts_waits_while_pending():
    original_pending = sidecar_main.tts_pending
    original_until = sidecar_main.tts_busy_until
    try:
        sidecar_main.tts_pending = 1
        sidecar_main.tts_busy_until = 0.0
        started = time.time()
        sidecar_main.wait_for_tts(timeout=0.4)
        assert time.time() - started >= 0.35
    finally:
        sidecar_main.tts_pending = original_pending
        sidecar_main.tts_busy_until = original_until


def test_handle_wake_sensitivity_command():
    original = sidecar_main.config.wake_sensitivity
    try:
        sidecar_main.handle_command("wake_sensitivity:high")
        assert sidecar_main.config.wake_sensitivity == "high"

        sidecar_main.handle_command("wake_sensitivity:garbage")
        assert sidecar_main.config.wake_sensitivity == "high"  # unchanged
    finally:
        sidecar_main.config.wake_sensitivity = original


def test_wake_thresholds_match_v040_defaults():
    from config import SidecarConfig

    cfg = SidecarConfig()
    assert cfg.wake_thresholds() == (0.55, 0.38)  # tuned v0.4.0b values
    cfg.set_wake_sensitivity("low")
    assert cfg.wake_thresholds() == (0.65, 0.45)
    cfg.set_wake_sensitivity("high")
    assert cfg.wake_thresholds() == (0.45, 0.30)
