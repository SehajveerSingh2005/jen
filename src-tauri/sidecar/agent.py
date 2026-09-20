"""The agent: conversation loop + tool dispatch + memory assembly.

Single-hop by design (speed): the model returns text OR tool call(s).
Executors return their own confirmation strings, so no second LLM round-trip
is needed to narrate what happened.
"""

import logging
import re
from dataclasses import dataclass, field
from typing import Callable

import protocol
import tools as tools_mod
from client import ChatResult, LLMClient, LLMError, ToolCall
from config import SidecarConfig
from memory import MemoryStore

log = logging.getLogger("jen.agent")

# Phrases that only make sense if a tool actually ran. If the model replies
# with one of these and no tool call, the reply is a lie — retry once.
_ACTION_CLAIM_RE = re.compile(
    r"\b("
    r"opening|launching|starting|playing|searching|taking a screenshot|"
    r"screenshotting|typing|pressing|adjusting|turning (?:up|down)|"
    r"muting|unmuting|locking|shutting down|restarting|closing|"
    r"minimizing|maximizing|switching|focusing|copying|pasting|cutting|"
    r"saving|undoing|redoing|"
    r"i(?:'ve| have) (?:opened|launched|started|played|searched|typed|pressed|"
    r"set|turned|noted|remembered|saved|closed|copied|pasted|adjusted|muted)|"
    r"i(?:'ll| will) (?:open|launch|start|play|search|type|press|set|turn|"
    r"mute|unmute|close|minimize|maximize|switch|focus|copy|paste|save|"
    r"remember|note)|"
    r"let me (?:open|launch|start|play|search|type|press|set|turn|close|"
    r"minimize|maximize|switch|focus|copy|paste|save|remember|note)|"
    r"let'?s (?:open|launch|start|play|search|call|use)|"
    r"i(?:'m| am) (?:opening|launching|starting|playing|searching|typing|"
    r"pressing|closing|copying|pasting|saving)|"
    r"(?:already|now) (?:open|opened|closed|running|playing|paused|muted|done|set)\b|"
    r"noted"
    r")\b",
    re.IGNORECASE,
)

# Bare confirmations like "Done." are also lies when nothing ran.
_DONE_RE = re.compile(
    r"^\s*(?:done|all done|it(?:'s| is) done|okay,? done)[.!]?\s*$", re.IGNORECASE
)

# Imperative echoes ("Pause the music.") and result confirmations
# ("Enter pressed.") are action claims too.
_IMPERATIVE_CLAIM_RE = re.compile(
    r"^\s*(?:pause|resume|stop|skip|play|open|close|mute|unmute|copy|paste|"
    r"cut|undo|redo|save|lock|minimize|maximize|brighten|dim)\b",
    re.IGNORECASE,
)
_GERUND_START_RE = re.compile(
    r"^\s*(?:pausing|resuming|stopping|skipping|playing|opening|closing|"
    r"minimizing|maximizing|copying|pasting|cutting|saving|typing|pressing|"
    r"muting|unmuting|locking)\b",
    re.IGNORECASE,
)
_RESULT_CONFIRM_RE = re.compile(
    r"^\s*\w+\s+(?:pressed|done|opened|closed|saved|copied|pasted|muted|"
    r"typed|played|paused|resumed|skipped)\b",
    re.IGNORECASE,
)


def _claims_action(text: str) -> bool:
    text = text or ""
    return (
        bool(_ACTION_CLAIM_RE.search(text))
        or bool(_DONE_RE.match(text))
        or bool(_IMPERATIVE_CLAIM_RE.match(text))
        or bool(_GERUND_START_RE.match(text))
        or bool(_RESULT_CONFIRM_RE.match(text))
    )


# Models that lack real-time data tend to refuse ("I don't have the ability
# to...") instead of searching. If a tool can answer, retry once with a nudge.
_REFUSAL_RE = re.compile(
    r"\b("
    r"i (?:do not|don't|cannot|can't) (?:have|access|provide|perform|calculate|know|browse)"
    r"|i (?:cannot|can't) (?:open|launch|start|play|close|do|control|access|provide|help)"
    r"|i don'?t have (?:the )?(?:ability|access|information|real-?time)"
    r"|i (?:am|'m) (?:not able|unable) to"
    r"|not able to (?:provide|answer|help|access|give|open|launch)"
    r"|i cannot access|i can'?t access|i can'?t provide real"
    r"|(?:is|isn'?t|not) (?:in|among) my tools"
    r"|don'?t have (?:a )?tool"
    r"|as an ai"
    r")\b",
    re.IGNORECASE,
)


def _looks_like_refusal(text: str) -> bool:
    return bool(_REFUSAL_RE.search(text))


# Small models sometimes narrate their intent ("Let's call the weather
# tool...") without emitting the call. Convert that into a real call.
_TOOL_INTENT_RE = re.compile(
    r"\b(call|use|using|invoke|run)\b[^.!?]{0,60}\btool\b",
    re.IGNORECASE,
)


def _mentions_tool_intent(text: str) -> bool:
    return bool(_TOOL_INTENT_RE.search(text))


def _short(text: str, limit: int = 160) -> str:
    text = " ".join((text or "").split())
    return text if len(text) <= limit else text[:limit] + "..."


# Small models sometimes emit near-miss tool-call syntax as text, e.g.
# "/media_control {"action": "next"}" or "media_control({...})". Recover it.
_PSEUDO_CALL_RES = (
    re.compile(r'<tool_call>\s*(\{.*?\})\s*</tool_call>', re.DOTALL),
    re.compile(r'^\s*/([a-z_]+)\s*(\{.*\})\s*$', re.DOTALL),
    re.compile(r'^\s*([a-z_]+)\s*\(\s*(\{.*\})\s*\)\s*$', re.DOTALL),
)


def _recover_pseudo_tool_call(text: str):
    """Parse a malformed tool call out of text. Returns ToolCall or None."""
    import json as _json

    candidates: list[tuple[str | None, str]] = []
    for pattern in _PSEUDO_CALL_RES:
        match = pattern.search(text)
        if match:
            groups = match.groups()
            if len(groups) == 1:
                candidates.append((None, groups[0]))
            else:
                candidates.append((groups[0], groups[1]))

    # Plain JSON with a name field (some templates emit it without markers)
    stripped = text.strip()
    if stripped.startswith("{"):
        candidates.append((None, stripped))

    for name, payload in candidates:
        try:
            data = _json.loads(payload)
        except (ValueError, TypeError):
            continue
        if isinstance(data, dict) and ("name" in data or name):
            fn = name or data.get("name")
            args = data.get("arguments", data.get("parameters", {}))
            if isinstance(args, str):
                try:
                    args = _json.loads(args)
                except ValueError:
                    args = {}
            if isinstance(fn, str) and isinstance(args, dict):
                return ToolCall(name=fn, arguments=args)
    return None


def _known_tool(name: str) -> bool:
    return name in {t.name for t in tools_mod.TOOLS}


# Inputs that may need live data: questions and weather-ish requests.
_QUESTION_RE = re.compile(
    r"^\s*(what|when|where|who|whom|whose|which|why|how|is|are|was|were|"
    r"do|does|did|can|could|will|would|should)\b",
    re.IGNORECASE,
)
_WEATHER_RE = re.compile(
    r"\b(weather|forecast|temperature|raining|rain|snow|humid)\b", re.IGNORECASE
)
# If a command verb is present, let the model drive: it can chain tools
# (e.g. "what's the weather and open chrome") instead of the fast path.
_COMMAND_VERB_RE = re.compile(
    r"\b(open|launch|start|play|pause|resume|close|minimize|maximize|focus|"
    r"type|write|press|hit|set|turn|mute|unmute|volume|brightness|"
    r"screenshot|copy|paste|cut|lock|shut ?down|restart|sleep|hibernate|"
    r"remind|remember)\b",
    re.IGNORECASE,
)


def _looks_like_question(text: str) -> bool:
    stripped = text.strip()
    return stripped.endswith("?") or bool(_QUESTION_RE.match(stripped))


def _may_need_live_data(text: str) -> bool:
    if _COMMAND_VERB_RE.search(text):
        return False
    return _looks_like_question(text) or bool(_WEATHER_RE.search(text))


def looks_like_command(text: str) -> bool:
    """True when the utterance contains a system-command verb."""
    return bool(_COMMAND_VERB_RE.search(text or ""))


def _lookup_query_kind(text: str) -> str:
    """Pick the lookup tool deterministically: local weather vs web search.

    A location in the question ("weather in Paris") means the local-weather
    tool is wrong, so that goes to search.
    """
    if not _WEATHER_RE.search(text):
        return "search"
    location = re.search(
        r"\b(?:in|at|for)\s+(?!the\b|my\b|our\b|a\b|an\b|this\b|that\b)(\w+)",
        text,
        re.IGNORECASE,
    )
    return "search" if location else "weather"

SYSTEM_PROMPT = """You are Jen, a personal voice assistant living on the user's Windows desktop.

How to behave:
- Use tools to perform actions. Never claim you did something without calling the tool.
- For questions and conversation, reply in one or two short sentences, natural for speech. No markdown, no lists, no emojis.
- Weather questions ("how's the weather", "will it rain") → call the weather tool. Never answer weather from memory.
- RULE: if the question mentions real-world places, distances, travel, news, prices, sports, people, or anything that may have changed since your training, you MUST call web_search first. Never answer those from memory.
- When the user shares durable facts about themselves (name, preferences, habits, app aliases), call remember_fact.
- If a request is ambiguous, ask one short clarifying question instead of guessing.
- Chain multiple tool calls in one response when the user asks for several things at once.

Routing guide for common commands:
- open, launch, start, run an app → open_app
- pause, resume, stop, skip, next, previous (something playing) → media_control
- play a song or artist → play_music
- volume up/down, louder, quieter, mute → volume_control
- brightness up/down, brighter, dimmer → brightness_control
- minimize, maximize, close, focus an app window → window_control
- take a screenshot, capture screen → screenshot
- copy, paste, cut → clipboard
- undo, redo, save, new tab, close tab, refresh, find, zoom → keyboard_shortcut
- type, write, dictate text → dictate
- press enter, space, tab, escape, backspace, arrow → press_key
- lock, sleep, restart, shut down → power_control
- weather question → weather
- search, look up, who, what, when, how (facts) → web_search
- remember a fact → remember_fact
{memory_block}"""

HISTORY_TURNS = 6

# Few-shot examples teach the tool-call format by demonstration, which small
# models follow far better than instructions alone. Kept short on purpose.
_FEW_SHOT: list[dict] = [
    {"role": "user", "content": "pause the music"},
    {
        "role": "assistant",
        "content": "",
        "tool_calls": [{
            "id": "call_ex1",
            "type": "function",
            "function": {"name": "media_control", "arguments": '{"action": "pause"}'},
        }],
    },
    {"role": "tool", "tool_call_id": "call_ex1", "content": "Done."},
    {"role": "user", "content": "open chrome"},
    {
        "role": "assistant",
        "content": "",
        "tool_calls": [{
            "id": "call_ex2",
            "type": "function",
            "function": {"name": "open_app", "arguments": '{"app": "chrome"}'},
        }],
    },
    {"role": "tool", "tool_call_id": "call_ex2", "content": "Opening chrome."},
    {"role": "user", "content": "undo"},
    {
        "role": "assistant",
        "content": "",
        "tool_calls": [{
            "id": "call_ex3",
            "type": "function",
            "function": {"name": "keyboard_shortcut", "arguments": '{"shortcut": "undo"}'},
        }],
    },
    {"role": "tool", "tool_call_id": "call_ex3", "content": "Done."},
    {"role": "user", "content": "press enter"},
    {
        "role": "assistant",
        "content": "",
        "tool_calls": [{
            "id": "call_ex4",
            "type": "function",
            "function": {"name": "press_key", "arguments": '{"key": "enter"}'},
        }],
    },
    {"role": "tool", "tool_call_id": "call_ex4", "content": "Done."},
]

# Tiny classifier used only when the model answered a question from memory:
# if the request needs up-to-date facts, force a tool call instead of
# accepting a possibly-hallucinated answer.
_FRESH_INFO_PROMPT = (
    "Decide whether answering the user request needs live, up-to-date data. "
    "Reply YES for weather, news, sports results, prices, distances, travel, "
    "events, or current facts about places or people. Reply NO for stable "
    "knowledge (math, coding, definitions) or casual talk (greetings, thanks).\n\n"
    "Examples:\n"
    "- how is the weather -> YES\n"
    "- will it rain tomorrow -> YES\n"
    "- who won the match yesterday -> YES\n"
    "- how far is Delhi from Chandigarh -> YES\n"
    "- what is 2 plus 2 -> NO\n"
    "- explain recursion -> NO\n"
    "- good morning -> NO\n\n"
    "Reply with one word: YES or NO."
)


@dataclass
class AgentResult:
    ok: bool
    spoken: str | None = None
    tools_run: list[str] = field(default_factory=list)
    tool_results: list[tools_mod.ToolResult] = field(default_factory=list)
    error: str | None = None


class Agent:
    def __init__(
        self,
        config: SidecarConfig,
        memory: MemoryStore | None = None,
        emit: Callable[[dict], None] = protocol.emit,
        dry_run: bool = False,
        llm_client: LLMClient | None = None,
    ):
        self.config = config
        self.memory = memory
        self.emit = emit
        self.dry_run = dry_run
        self._client = llm_client

    def reset_client(self) -> None:
        """Drop the cached client (call when AI config changes)."""
        self._client = None

    def _needs_fresh_info(self, text: str) -> bool:
        """YES/NO classifier: is this a question that needs live data?"""
        try:
            out = self._get_client().chat(
                [
                    {"role": "system", "content": _FRESH_INFO_PROMPT},
                    {"role": "user", "content": text},
                ],
                max_tokens=4,
                temperature=0.0,
            )
        except LLMError as e:
            log.warning("fresh-info classifier failed: %s", e)
            return False
        answer = (out.text or "").strip()
        log.info("fresh-info classifier: %r", _short(answer, 20))
        return answer.lower().startswith("yes")

    def warmup(self) -> None:
        """Prime the local server's KV cache with the system prompt + tools.

        First request after model load costs several seconds of prompt
        evaluation; doing it in the background at startup makes the first
        real command fast. No memory turn is recorded.
        """
        if self.config.ai_mode != "local":
            return
        try:
            llm = self._get_client()
            llm.chat(self._build_messages("hello"), tools=tools_mod.tool_schemas())
            log.info("LLM warmup complete")
        except Exception as e:
            log.warning("LLM warmup failed: %s", e)

    def _get_client(self) -> LLMClient:
        if self._client is None:
            if self.config.ai_mode == "local":
                self._client = LLMClient(
                    base_url=self.config.local_base_url,
                    model=self.config.local_model,
                    timeout=60.0,  # local CPU inference can be slow on first token
                    # Qwen3.x models think before answering by default; for a
                    # voice assistant that costs seconds. Templates of other
                    # models ignore the extra kwarg.
                    extra_body={"chat_template_kwargs": {"enable_thinking": False}},
                )
            else:
                self._client = LLMClient(
                    base_url=self.config.cloud_base_url,
                    api_key=self.config.cloud_api_key,
                    model=self.config.cloud_model,
                )
        return self._client

    def _build_messages(self, text: str) -> list[dict]:
        memory_block = self.memory.context_block() if self.memory else ""
        system = SYSTEM_PROMPT.format(memory_block=memory_block)
        messages: list[dict] = [{"role": "system", "content": system}]
        messages.extend(_FEW_SHOT)
        if self.memory:
            # Refusals and false action claims must not be replayed as
            # history — they teach the model it lacks tools it actually has.
            # Refusals, false claims, and legacy "[called x]" markers must not
            # be replayed as history — they teach the model it lacks tools or
            # that text answers are acceptable. Drop the user turn that the
            # filtered reply answered, so pairs stay coherent.
            kept: list[dict] = []
            for turn in self.memory.recent_turns(HISTORY_TURNS * 3):
                content = turn["content"] or ""
                if turn["role"] == "assistant" and (
                    _looks_like_refusal(content)
                    or _claims_action(content)
                    or content.strip().startswith("[called ")
                ):
                    if kept and kept[-1]["role"] == "user":
                        kept.pop()
                    continue
                kept.append({"role": turn["role"], "content": content})
            messages.extend(kept[-HISTORY_TURNS:])
        messages.append({"role": "user", "content": text})
        return messages

    def process(self, text: str) -> AgentResult:
        """Run one conversational turn: text in → tools and/or spoken reply out."""
        text = text.strip()
        if not text:
            return AgentResult(ok=False, error="empty input")

        if self.config.ai_mode == "off":
            msg = "I don't have a brain yet. Set up local or cloud AI in Jen's settings."
            return self._finish(text, AgentResult(ok=False, spoken=msg, error="ai_mode_off"))

        llm = self._get_client()
        try:
            messages = self._build_messages(text)

            # Deterministic fast path for information questions: classify
            # first, then run the lookup ourselves. Small models routinely
            # refuse or narrate instead of calling a tool (and llama.cpp's
            # tool_choice=required is not honored by every chat template),
            # so we don't leave the lookup to the model at all.
            if _may_need_live_data(text) and self._needs_fresh_info(text):
                log.info("question needs live data; running lookup fast path")
                return self._finish(text, self._answer_from_lookup(text, messages))

            result = llm.chat(messages, tools=tools_mod.tool_schemas())
            if not result.tool_calls and result.text:
                log.info("LLM reply (no tool call): %s", _short(result.text))
                recovered = self._recover_text_response(result, messages, text)
                if isinstance(recovered, AgentResult):
                    return self._finish(text, recovered)
                result = recovered
        except LLMError as e:
            log.warning("LLM request failed: %s", e)
            msg = "My brain is unreachable right now." if self.config.ai_mode == "local" else "The AI service rejected the request."
            return self._finish(text, AgentResult(ok=False, spoken=msg, error=str(e)))

        return self._finish(text, self._handle_result(result, messages))

    def _failed_action(self) -> AgentResult:
        """The model claimed an action but never emitted a tool call."""
        log.warning("model claimed an action without calling a tool; refusing to lie")
        return AgentResult(
            ok=False, spoken="Sorry, I couldn't do that.", error="no_tool_call"
        )

    def _answer_from_lookup(self, text: str, messages: list[dict]) -> AgentResult:
        """Run the appropriate lookup tool directly, then synthesize an answer."""
        if _lookup_query_kind(text) == "weather":
            log.info("lookup: weather tool")
            result = ChatResult(tool_calls=[ToolCall(name="weather", arguments={})])
        else:
            log.info("lookup: web_search")
            result = ChatResult(
                tool_calls=[ToolCall(name="web_search", arguments={"query": text})]
            )
        return self._handle_result(result, messages)

    def _recover_text_response(
        self, result: ChatResult, messages: list[dict], text: str
    ):
        """The model answered with text instead of calling a tool.

        Recoveries, in order:
          - it claimed an action or narrated tool use → force a tool call;
            if the model still won't act, never speak the lie
          - the question needs live data → lookup, run by us if needed
          - it refused but a tool could serve → one nudge retry

        Returns a ChatResult, or an AgentResult for the honest-failure case.
        """
        llm = self._get_client()

        # Near-miss tool-call syntax in text -> a real tool call.
        pseudo = _recover_pseudo_tool_call(result.text)
        if pseudo is not None and _known_tool(pseudo.name):
            log.info("recovered malformed tool call: %s(%s)", pseudo.name, pseudo.arguments)
            return ChatResult(tool_calls=[pseudo])

        wants_tool = _claims_action(result.text) or _mentions_tool_intent(result.text)
        refusal = _looks_like_refusal(result.text)
        command_input = bool(_COMMAND_VERB_RE.search(text))

        if wants_tool:
            log.info("forcing tool call (model implied an action)")
            forced = llm.chat(
                messages,
                tools=tools_mod.tool_schemas(),
                temperature=0.0,
                tool_choice="required",
            )
            if forced.tool_calls:
                return forced
            log.info("forced retry returned text: %s", _short(forced.text or ""))
            # The model won't act. Run a lookup if that is what is needed;
            # otherwise fail honestly instead of speaking a lie.
            if not command_input and self._needs_fresh_info(text):
                pass  # fall through to the lookup path
            else:
                return self._failed_action()

        elif refusal:
            log.info("model refused a request a tool could serve; nudging")
            nudged = messages + [
                {
                    "role": "system",
                    "content": (
                        "A tool can answer this. Use weather for weather and "
                        "web_search for current facts, news, places, or anything "
                        "you are unsure about. Call the tool now if it applies; "
                        "otherwise give your best short answer."
                    ),
                }
            ]
            retry = llm.chat(nudged, tools=tools_mod.tool_schemas(), temperature=0.0)
            if retry.tool_calls:
                return retry
            log.info("nudge retry returned text: %s", _short(retry.text or ""))
            # A command that can't be executed fails honestly; an information
            # question falls through to the live-data path.
            if command_input:
                return self._failed_action()

        elif not self._needs_fresh_info(text):
            return result

        # Live-data path: prefer the model's own choice of lookup tool.
        log.info("answer needs live data; forcing a lookup tool call")
        lookup_tools = [
            s for s in tools_mod.tool_schemas()
            if s["function"]["name"] in ("weather", "web_search")
        ]
        forced = llm.chat(
            messages, tools=lookup_tools, temperature=0.0, tool_choice="required"
        )
        if forced.tool_calls:
            return forced
        log.info("forced lookup returned text: %s", _short(forced.text or ""))

        # The model won't emit the call — run the lookup ourselves.
        if _lookup_query_kind(text) == "weather":
            log.info("model would not call a lookup tool; using the weather tool directly")
            return ChatResult(tool_calls=[ToolCall(name="weather", arguments={})])
        log.info("model would not call a lookup tool; searching the question directly")
        return ChatResult(tool_calls=[ToolCall(name="web_search", arguments={"query": text})])

    def _handle_result(self, result: ChatResult, messages: list[dict]) -> AgentResult:
        # Pure text answer / question
        if not result.tool_calls:
            return AgentResult(ok=True, spoken=result.text or "I'm not sure.")

        # Tool call(s) — possibly several in one response
        ctx = tools_mod.ExecutorContext(
            config=self.config, memory=self.memory, emit=self.emit, dry_run=self.dry_run
        )
        tools_run: list[str] = []
        results: list[tools_mod.ToolResult] = []
        for call in result.tool_calls:
            log.info("tool call: %s(%s)", call.name, call.arguments)
            tr = tools_mod.execute(ctx, call.name, call.arguments)
            log.info("tool result: %s", _short(tr.message))
            tools_run.append(call.name)
            results.append(tr)

        spoken = self._pick_spoken(results)
        if spoken is None:
            data = [r for r in results if r.needs_llm and r.message]
            if data:
                spoken = self._synthesize(messages, data)

        return AgentResult(
            ok=all(r.ok for r in results),
            spoken=spoken,
            tools_run=tools_run,
            tool_results=results,
        )

    def _synthesize(self, messages: list[dict], results: list[tools_mod.ToolResult]) -> str | None:
        """Second hop: turn tool data (search results) into a spoken answer."""
        content = "\n\n".join(r.message for r in results)
        synth = messages + [
            {
                "role": "system",
                "content": (
                    "Tool results:\n" + content + "\n\n"
                    "Answer the user's question using only these results. One or two "
                    "short sentences, natural for speech, no markdown. If the results "
                    "don't answer it, say you couldn't find it."
                ),
            }
        ]
        try:
            out = self._get_client().chat(synth, tools=None, temperature=0.2)
        except LLMError as e:
            log.warning("answer synthesis failed: %s", e)
            return None
        log.info("synthesized answer: %s", _short(out.text or ""))
        return (out.text or "").strip() or None

    def _pick_spoken(self, results: list[tools_mod.ToolResult]) -> str | None:
        """Speaking policy:
        - Any result flagged speak=True (answers, weather, errors) → always spoken.
        - personality=conversational → speak the first confirmation.
        - personality=minimal → silence (the orb chime is the confirmation).
        """
        for r in results:
            if r.speak and r.message:
                return r.message
        if self.config.personality == "conversational":
            for r in results:
                if r.message:
                    return r.message
            return "Done."
        return None

    def _finish(self, user_text: str, result: AgentResult) -> AgentResult:
        if self.memory:
            self.memory.add_turn("user", user_text)
            spoken_is_noise = bool(result.spoken) and (
                _looks_like_refusal(result.spoken) or _claims_action(result.spoken)
            )
            if result.spoken and not spoken_is_noise:
                self.memory.add_turn("assistant", result.spoken)
            # Tool-only turns are deliberately NOT recorded: replaying fake
            # text like "[called open_app]" taught the model to answer
            # commands with text instead of calling tools.
        return result
