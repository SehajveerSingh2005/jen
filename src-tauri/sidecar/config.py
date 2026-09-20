"""Sidecar configuration, mutated at runtime via the stdin command protocol.

The Rust host owns persistence (settings.json); this object is the live view
the sidecar operates from. All fields have safe defaults so the sidecar can
also run standalone (tests, --simulate) with zero configuration.
"""

from dataclasses import dataclass

DEFAULT_LOCAL_BASE_URL = "http://127.0.0.1:58931/v1"
DEFAULT_LOCAL_MODEL = "jen-local"  # llama-server is spawned with --alias jen-local
DEFAULT_CLOUD_BASE_URL = "https://api.openai.com/v1"
DEFAULT_CLOUD_MODEL = "gpt-4o-mini"
DEFAULT_TTS_VOICE = "en-US-JennyNeural"

AI_MODES = ("off", "local", "cloud")
PERSONALITIES = ("minimal", "conversational")
WAKE_SENSITIVITIES = ("low", "medium", "high")

# (peak score, per-frame score) — medium matches the tuned v0.4.0b values.
_WAKE_THRESHOLDS = {
    "low": (0.65, 0.45),
    "medium": (0.55, 0.38),
    "high": (0.45, 0.30),
}


@dataclass
class SidecarConfig:
    protect_sensitive: bool = True
    tts_enabled: bool = True
    tts_voice: str = DEFAULT_TTS_VOICE
    ai_mode: str = "off"
    personality: str = "minimal"
    wake_sensitivity: str = "medium"
    followup_seconds: float = 12.0
    followup_enabled: bool = False
    local_base_url: str = DEFAULT_LOCAL_BASE_URL
    local_model: str = DEFAULT_LOCAL_MODEL
    cloud_api_key: str = ""
    cloud_base_url: str = DEFAULT_CLOUD_BASE_URL
    cloud_model: str = DEFAULT_CLOUD_MODEL
    memory_path: str = "memory.db"
    input_device_index: int | None = None

    def set_ai_mode(self, mode: str) -> None:
        self.ai_mode = mode if mode in AI_MODES else "off"

    def set_personality(self, personality: str) -> None:
        if personality in PERSONALITIES:
            self.personality = personality

    def set_wake_sensitivity(self, value: str) -> None:
        if value in WAKE_SENSITIVITIES:
            self.wake_sensitivity = value

    def wake_thresholds(self) -> tuple[float, float]:
        """(peak_score, frame_score) for the current sensitivity level."""
        return _WAKE_THRESHOLDS.get(self.wake_sensitivity, _WAKE_THRESHOLDS["medium"])
