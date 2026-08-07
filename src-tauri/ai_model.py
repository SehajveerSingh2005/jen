import json
import os
import logging

log = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are Jen, a voice assistant. Respond with EXACTLY one line.

For ACTIONS (opening apps, searching, playing, volume, etc):
COMMAND: action | argument
Examples:
- "open chrome" → COMMAND: open | chrome
- "search restaurants" → COMMAND: search | restaurants
- "play some music" → COMMAND: play | some music
- "volume up" → COMMAND: volume | up
- "take a screenshot" → COMMAND: screenshot
- "what's the weather" → COMMAND: weather | today

For QUESTIONS (definitions, facts, explanations, math, opinions):
ANSWER: your short answer
Examples:
- "what's 29 times 37" → ANSWER: 1073
- "what is a dicot" → ANSWER: A dicot is a flowering plant with two seed leaves.
- "why is the sky blue" → ANSWER: The sky is blue because of how sunlight scatters in the atmosphere.

Rules:
- ONE line only. Start with COMMAND: or ANSWER:
- For COMMAND: use the exact action word, then |, then the argument
- For ANSWER: be brief, 1-2 sentences max
- NEVER use weather for non-weather questions
- NEVER use COMMAND: for questions, math, definitions, or explanations
- NEVER add extra text, explanations, or formatting"""


def _parse_response(text):
    """Parse a COMMAND: or ANSWER: response from the LLM."""
    text = text.strip()
    if not text:
        return {"type": "response", "text": "I'm not sure."}

    # Take first non-empty line only
    for line in text.strip().split("\n"):
        line = line.strip()
        if line:
            break
    else:
        return {"type": "response", "text": "I'm not sure."}

    # ANSWER: response
    upper = line.upper()
    if upper.startswith("ANSWER:"):
        answer = line[7:].strip()
        return {"type": "response", "text": answer or "I'm not sure."}

    # COMMAND: response
    if upper.startswith("COMMAND:"):
        cmd_part = line[8:].strip()
        if "|" in cmd_part:
            action, arg = cmd_part.split("|", 1)
        else:
            parts = cmd_part.split(" ", 1)
            action = parts[0]
            arg = parts[1] if len(parts) > 1 else ""
        action = action.strip().lower()
        arg = arg.strip()

        CMD_MAP = {
            "open": ("open_app", {"app": arg}),
            "search": ("google_search", {"query": arg}),
            "play": ("play_music", {"song": arg}),
            "volume": ("volume_control", {"action": arg or "up"}),
            "media": ("media_control", {"action": arg or "play"}),
            "window": ("window_control", {"action": arg.split()[0] if arg else "focus", "app": arg.split(maxsplit=1)[1] if arg and len(arg.split()) > 1 else ""}),
            "brightness": ("brightness_control", {"action": arg or "up"}),
            "shortcut": ("keyboard_shortcut", {"shortcut": arg}),
            "screenshot": ("screenshot", {}),
            "type": ("dictate", {"text": arg}),
            "weather": ("weather", {"query": arg or "today"}),
        }
        if action in CMD_MAP:
            intent, params = CMD_MAP[action]
            return {"type": "tool_call", "function": intent, "args": params}

    # Fallback: treat the whole line as a response
    return {"type": "response", "text": line}


class LocalAIEngine:
    def __init__(self):
        self.llm = None
        self.model_path = None

    def configure(self, model_path):
        self.model_path = model_path
        self.llm = None

    def preload(self):
        import threading
        def _load():
            self.load()
        threading.Thread(target=_load, daemon=True).start()

    def load(self):
        if self.llm is not None:
            return True
        if not self.model_path or not os.path.exists(self.model_path):
            return False
        try:
            from llama_cpp import Llama
            log.info(f"Loading local model: {self.model_path}")
            self.llm = Llama(
                model_path=self.model_path,
                n_ctx=2048,
                n_threads=max(2, (os.cpu_count() or 4) - 1),
                n_gpu_layers=0,
                verbose=False,
            )
            log.info("Local model loaded")
            return True
        except Exception as e:
            log.error(f"Failed to load local model: {e}")
            return False

    def process(self, text):
        if not self.load():
            return {"type": "error", "text": "Local model not available"}

        try:
            response = self.llm.create_chat_completion(
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": text},
                ],
                max_tokens=100,
                temperature=0.2,
                top_p=0.9,
            )
            content = response["choices"][0]["message"].get("content", "")
            log.debug(f"LLM raw: {content}")
            return _parse_response(content)
        except Exception as e:
            log.error(f"Local AI error: {e}")
            return {"type": "error", "text": str(e)}


class CloudAIEngine:
    def __init__(self):
        self.api_key = ""
        self.base_url = "https://api.openai.com/v1"
        self.model = "gpt-4o-mini"

    def configure(self, api_key, base_url, model):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model

    def process(self, text):
        if not self.api_key:
            return {"type": "error", "text": "API key not configured"}

        try:
            import httpx
            resp = httpx.post(
                f"{self.base_url}/chat/completions",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json={
                    "model": self.model,
                    "messages": [
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": text},
                    ],
                    "max_tokens": 100,
                    "temperature": 0.3,
                },
                timeout=10.0,
            )
            resp.raise_for_status()
            content = resp.json()["choices"][0]["message"].get("content", "")
            return _parse_response(content)
        except Exception as e:
            log.error(f"Cloud AI error: {e}")
            return {"type": "error", "text": str(e)}


local_engine = LocalAIEngine()
cloud_engine = CloudAIEngine()
