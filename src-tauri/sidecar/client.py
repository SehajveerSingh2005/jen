"""OpenAI-compatible chat client.

One code path for every backend Jen supports:
  - local  → bundled llama-server (http://127.0.0.1:<port>/v1)
  - cloud  → any OpenAI-compatible API (OpenAI, Groq, OpenRouter, ...)
  - other  → Ollama / LM Studio via their /v1 endpoints

Kept deliberately thin: retries, timeouts, and response normalization.
The `_post` method is the single network seam — tests monkeypatch it.
"""

import json
import time
from dataclasses import dataclass, field

import httpx


class LLMError(Exception):
    """Fatal request failure (bad config, 4xx, or retries exhausted)."""


class TransientLLMError(Exception):
    """Retryable failure (timeout, connection error, 5xx)."""


@dataclass
class ToolCall:
    name: str
    arguments: dict = field(default_factory=dict)


@dataclass
class ChatResult:
    text: str | None = None
    tool_calls: list[ToolCall] = field(default_factory=list)


class LLMClient:
    def __init__(
        self,
        base_url: str,
        api_key: str = "",
        model: str = "local",
        timeout: float = 30.0,
        max_retries: int = 2,
        extra_body: dict | None = None,
    ):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.timeout = timeout
        self.max_retries = max_retries
        self.extra_body = extra_body or {}

    def _post(self, payload: dict) -> dict:
        """Single network seam. Raises TransientLLMError or LLMError."""
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        try:
            resp = httpx.post(
                f"{self.base_url}/chat/completions",
                headers=headers,
                json=payload,
                timeout=self.timeout,
            )
        except (httpx.TimeoutException, httpx.TransportError) as e:
            raise TransientLLMError(str(e)) from e

        if resp.status_code >= 500:
            raise TransientLLMError(f"server error {resp.status_code}")
        if resp.status_code >= 400:
            raise LLMError(f"request rejected ({resp.status_code}): {resp.text[:200]}")
        try:
            return resp.json()
        except json.JSONDecodeError as e:
            raise TransientLLMError(f"invalid JSON response: {e}") from e

    def chat(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
        max_tokens: int = 180,
        temperature: float = 0.2,
        tool_choice: str = "auto",
    ) -> ChatResult:
        payload = {
            "model": self.model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "stream": False,
            # Standard OpenAI fields; llama-server honors them too. Keeps
            # small models from falling into repetition loops.
            "frequency_penalty": 0.4,
            "presence_penalty": 0.2,
        }
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = tool_choice
        payload.update(self.extra_body)

        last_err: Exception | None = None
        for attempt in range(self.max_retries + 1):
            try:
                data = self._post(payload)
                return parse_response(data)
            except TransientLLMError as e:
                last_err = e
                if attempt < self.max_retries:
                    time.sleep(0.4 * (2 ** attempt))
        raise LLMError(f"LLM request failed after retries: {last_err}")


def parse_response(data: dict) -> ChatResult:
    """Normalize an OpenAI-style response into ChatResult.

    Handles both native tool_calls and models that inline JSON in content.
    """
    try:
        message = data["choices"][0]["message"]
    except (KeyError, IndexError, TypeError) as e:
        raise LLMError(f"malformed response: {str(data)[:200]}") from e

    tool_calls = _parse_tool_calls(message.get("tool_calls"))
    if tool_calls:
        return ChatResult(text=None, tool_calls=tool_calls)

    content = (message.get("content") or "").strip()

    # Fallback: some small models inline the tool call as JSON text
    inlined = _parse_inlined_tool_call(content)
    if inlined:
        return ChatResult(text=None, tool_calls=[inlined])

    return ChatResult(text=content or None, tool_calls=[])


def _parse_tool_calls(raw) -> list[ToolCall]:
    if not raw:
        return []
    calls = []
    for item in raw:
        try:
            fn = item.get("function", {})
            name = fn.get("name") or item.get("name")
            if not name:
                continue
            args = fn.get("arguments", item.get("arguments", {}))
            if isinstance(args, str):
                try:
                    args = json.loads(args) if args.strip() else {}
                except json.JSONDecodeError:
                    args = {}
            calls.append(ToolCall(name=name, arguments=args if isinstance(args, dict) else {}))
        except AttributeError:
            continue
    return calls


def _parse_inlined_tool_call(content: str) -> ToolCall | None:
    if not content.startswith("{") or '"name"' not in content:
        return None
    try:
        obj = json.loads(content)
    except json.JSONDecodeError:
        # Tolerate trailing junk after the JSON object
        try:
            end = content.rindex("}")
            obj = json.loads(content[: end + 1])
        except (ValueError, json.JSONDecodeError):
            return None
    name = obj.get("name")
    if not isinstance(name, str) or not name:
        return None
    args = obj.get("arguments", obj.get("args", {}))
    return ToolCall(name=name, arguments=args if isinstance(args, dict) else {})
