"""Agent: turn handling, tool dispatch, speaking policy, memory integration."""

import pytest

from agent import Agent
from client import ChatResult, LLMError, ToolCall


class FakeClient:
    """Scripted LLM stand-in. Records the messages it received."""

    def __init__(self, *results):
        self._queue = list(results)
        self.received: list[list[dict]] = []
        self.received_tools: list = []
        self.received_tool_choice: list[str] = []
        self.classifier_answer = "NO"

    def chat(self, messages, tools=None, max_tokens=180, temperature=0.2, tool_choice="auto"):
        self.received.append(messages)
        self.received_tools.append(tools)
        self.received_tool_choice.append(tool_choice)
        # Fresh-info classifier: tiny call without tools. Not scripted.
        if tools is None and max_tokens <= 4:
            return ChatResult(text=self.classifier_answer)
        if not self._queue:
            return ChatResult(text="NO")
        item = self._queue.pop(0)
        if isinstance(item, Exception):
            raise item
        return item

    def main_calls(self) -> int:
        """Calls that were part of the scripted flow (not classifier)."""
        return sum(1 for t in self.received_tools if t is not None)


def make_agent(cfg, mem, *results, events=None):
    fake = FakeClient(*results)
    agent = Agent(
        config=cfg,
        memory=mem,
        emit=(events.append if events is not None else lambda p: None),
        dry_run=True,
        llm_client=fake,
    )
    return agent, fake


def tool_result(name, args=None):
    return ChatResult(tool_calls=[ToolCall(name=name, arguments=args or {})])


def test_text_answer_is_spoken(cfg, mem):
    cfg.ai_mode = "local"
    agent, _ = make_agent(cfg, mem, ChatResult(text="The sky is blue."))
    result = agent.process("why is the sky blue")
    assert result.ok is True
    assert result.spoken == "The sky is blue."
    assert result.tools_run == []


def test_tool_call_minimal_mode_is_silent(cfg, mem):
    cfg.ai_mode = "local"
    cfg.personality = "minimal"
    agent, _ = make_agent(cfg, mem, tool_result("open_app", {"app": "chrome"}))
    result = agent.process("open chrome")
    assert result.ok is True
    assert result.tools_run == ["open_app"]
    assert result.spoken is None  # chime is the confirmation


def test_tool_call_conversational_mode_confirms(cfg, mem):
    cfg.ai_mode = "local"
    cfg.personality = "conversational"
    agent, _ = make_agent(cfg, mem, tool_result("open_app", {"app": "chrome"}))
    result = agent.process("open chrome")
    assert result.spoken == "Would open chrome."  # dry-run confirmation message


def test_speak_flag_overrides_minimal_mode(cfg, mem):
    cfg.ai_mode = "local"
    cfg.personality = "minimal"
    agent, _ = make_agent(cfg, mem, tool_result("weather"))
    result = agent.process("what's the weather")
    assert result.spoken is not None  # dry-run weather message (speak=True)


def test_multiple_tool_calls_in_one_turn(cfg, mem):
    cfg.ai_mode = "local"
    result_in = ChatResult(tool_calls=[
        ToolCall(name="open_app", arguments={"app": "spotify"}),
        ToolCall(name="volume_control", arguments={"action": "up"}),
    ])
    agent, _ = make_agent(cfg, mem, result_in)
    result = agent.process("open spotify and turn the volume up")
    assert result.tools_run == ["open_app", "volume_control"]


def test_llm_error_gives_spoken_fallback(cfg, mem):
    cfg.ai_mode = "local"
    agent, _ = make_agent(cfg, mem, LLMError("connection refused"))
    result = agent.process("open chrome")
    assert result.ok is False
    assert result.spoken is not None
    assert result.error is not None


def test_ai_mode_off_short_circuits(cfg, mem):
    cfg.ai_mode = "off"
    agent, _ = make_agent(cfg, mem)  # no client results queued: must not be called
    result = agent.process("open chrome")
    assert result.ok is False
    assert "settings" in result.spoken.lower()


def test_tools_schema_sent_to_model(cfg, mem):
    cfg.ai_mode = "local"
    agent, fake = make_agent(cfg, mem, ChatResult(text="hi"))
    agent.process("hello")
    assert len(fake.received_tools[0]) >= 15
    names = {s["function"]["name"] for s in fake.received_tools[0]}
    assert "open_app" in names and "remember_fact" in names


def test_memory_facts_injected_into_system_prompt(cfg, mem):
    cfg.ai_mode = "local"
    mem.add_fact("name", "Sehaj")
    agent, fake = make_agent(cfg, mem, ChatResult(text="hi"))
    agent.process("hello")
    system = fake.received[0][0]["content"]
    assert "About the user:" in system
    assert "name: Sehaj" in system


def test_turns_recorded_in_history(cfg, mem):
    cfg.ai_mode = "local"
    agent, _ = make_agent(cfg, mem, ChatResult(text="Nice to meet you."))
    agent.process("hi, I'm Sehaj")
    turns = mem.recent_turns(10)
    assert turns[-2] == {"role": "user", "content": "hi, I'm Sehaj", "tool_name": None}
    assert turns[-1]["role"] == "assistant"
    assert turns[-1]["content"] == "Nice to meet you."


def test_tool_turns_are_not_recorded_as_text_history(cfg, mem):
    """Fake text turns like "[called open_app]" used to teach the model to
    answer commands with text. Tool-only turns must not be recorded."""
    cfg.ai_mode = "local"
    agent, _ = make_agent(cfg, mem, tool_result("open_app", {"app": "chrome"}))
    agent.process("open chrome")
    assistant_turns = [t for t in mem.recent_turns(10) if t["role"] == "assistant"]
    assert assistant_turns == []


def test_fake_tool_markers_are_filtered_from_history(cfg, mem):
    cfg.ai_mode = "local"
    agent, _ = make_agent(cfg, mem)
    mem.add_turn("user", "open chrome")
    mem.add_turn("assistant", "[called open_app]")  # legacy row from old builds
    messages = agent._build_messages("open firefox")
    contents = [m["content"] for m in messages]
    assert not any(c.startswith("[called ") for c in contents)


def test_action_claim_never_lies_when_tool_wont_run(cfg, mem):
    cfg.ai_mode = "local"
    fake = FakeClient(
        ChatResult(text="I have opened Chrome."),
        ChatResult(text="I have opened Chrome. Anything else?"),  # forced retry still text
    )
    agent = Agent(config=cfg, memory=mem, emit=lambda p: None, dry_run=True, llm_client=fake)
    result = agent.process("open chrome")
    assert result.tools_run == []
    assert result.ok is False
    assert "couldn't" in result.spoken


def test_history_sent_as_messages(cfg, mem):
    cfg.ai_mode = "local"
    agent, fake = make_agent(cfg, mem, ChatResult(text="hi"), ChatResult(text="your name is Sehaj"))
    agent.process("my name is Sehaj")
    agent.process("what is my name")
    main_calls = [m for m, t in zip(fake.received, fake.received_tools) if t is not None]
    second_call_messages = main_calls[1]
    roles = [m["role"] for m in second_call_messages]
    assert roles[0] == "system"
    # earlier turn present before the new user message
    assert {"role": "user", "content": "my name is Sehaj"} in second_call_messages[:-1]


def test_remember_fact_round_trip(cfg, mem):
    """Model remembers a fact → next prompt carries it."""
    cfg.ai_mode = "local"
    agent, fake = make_agent(
        cfg, mem,
        tool_result("remember_fact", {"key": "editor", "value": "VS Code"}),
        ChatResult(text="VS Code."),
    )
    agent.process("remember that my editor is VS Code")
    assert dict(mem.facts())["editor"] == "VS Code"
    agent.process("what's my editor?")
    main_calls = [m for m, t in zip(fake.received, fake.received_tools) if t is not None]
    assert "editor: VS Code" in main_calls[-1][0]["content"]


def test_action_claim_without_tool_call_triggers_retry(cfg, mem):
    cfg.ai_mode = "local"
    agent, fake = make_agent(
        cfg,
        mem,
        ChatResult(text="Opening Chrome."),
        tool_result("open_app", {"app": "chrome"}),
    )
    result = agent.process("open chrome")
    assert result.tools_run == ["open_app"]
    scripted_choices = [
        tc for tc, tools in zip(fake.received_tool_choice, fake.received_tools) if tools is not None
    ]
    assert scripted_choices == ["auto", "required"]


def test_normal_answer_does_not_trigger_retry(cfg, mem):
    cfg.ai_mode = "local"
    agent, fake = make_agent(cfg, mem, ChatResult(text="The capital of France is Paris."))
    result = agent.process("what is the capital of france")
    assert result.tools_run == []
    assert "required" not in fake.received_tool_choice


def test_warmup_skipped_when_not_local(cfg, mem):
    cfg.ai_mode = "cloud"
    agent, fake = make_agent(cfg, mem)
    agent.warmup()
    assert fake.received == []


def test_warmup_hits_llm_without_recording_history(cfg, mem):
    cfg.ai_mode = "local"
    agent, fake = make_agent(cfg, mem, ChatResult(text="Hi!"))
    agent.warmup()
    assert len(fake.received) == 1
    assert fake.received_tools[0] is not None
    assert mem.recent_turns(10) == []


def test_empty_input_rejected(cfg, mem):
    cfg.ai_mode = "local"
    agent, _ = make_agent(cfg, mem)
    assert agent.process("   ").ok is False


# --- Multi-hop answers and refusal retry ---

def test_needs_llm_result_triggers_synthesis(cfg, mem, monkeypatch):
    import tools as tools_mod

    monkeypatch.setattr(tools_mod, "_fetch_search_results", lambda q, limit=5: [
        {"title": "Paris", "snippet": "Paris is the capital of France."},
    ])
    cfg.ai_mode = "local"
    fake = FakeClient(
        tool_result("web_search", {"query": "capital of france"}),
        ChatResult(text="Paris is the capital of France."),
    )
    agent = Agent(config=cfg, memory=mem, emit=lambda p: None, dry_run=False, llm_client=fake)
    result = agent.process("what is the capital of france")
    assert result.tools_run == ["web_search"]
    assert result.spoken == "Paris is the capital of France."
    # Last call is synthesis: no tools, system message with results
    assert fake.received_tools[-1] is None
    assert "Tool results" in fake.received[-1][-1]["content"]


def test_refusal_triggers_tool_retry(cfg, mem, monkeypatch):
    import tools as tools_mod

    monkeypatch.setattr(tools_mod, "_fetch_search_results", lambda q, limit=5: [
        {"title": "Distance", "snippet": "About 250 km."},
    ])
    cfg.ai_mode = "local"
    fake = FakeClient(
        ChatResult(text="I am sorry but I don't have the ability to calculate distances."),
        tool_result("web_search", {"query": "distance chandigarh delhi"}),
        ChatResult(text="It's about 250 kilometers."),
    )
    agent = Agent(config=cfg, memory=mem, emit=lambda p: None, dry_run=False, llm_client=fake)
    result = agent.process("how far is chandigarh from delhi")
    assert result.tools_run == ["web_search"]
    assert result.spoken == "It's about 250 kilometers."
    main_calls = fake.main_calls()
    assert main_calls == 2  # refusal reply, nudge retry


def test_synthesis_failure_falls_back_to_none(cfg, mem, monkeypatch):
    import tools as tools_mod

    monkeypatch.setattr(tools_mod, "_fetch_search_results", lambda q, limit=5: [
        {"title": "T", "snippet": "S"},
    ])
    cfg.ai_mode = "local"
    fake = FakeClient(
        tool_result("web_search", {"query": "x"}),
        LLMError("synthesis blew up"),
    )
    agent = Agent(config=cfg, memory=mem, emit=lambda p: None, dry_run=False, llm_client=fake)
    result = agent.process("what is x")
    assert result.tools_run == ["web_search"]
    assert result.spoken is None


def test_tool_intent_narration_forces_tool_call(cfg, mem, monkeypatch):
    import tools as tools_mod

    monkeypatch.setattr(tools_mod, "_fetch_search_results", lambda q, limit=5: [
        {"title": "Distance", "snippet": "About 250 km."},
    ])
    cfg.ai_mode = "local"
    fake = FakeClient(
        ChatResult(text="Let's call the web_search tool to find out."),
        tool_result("web_search", {"query": "distance chandigarh delhi"}),
        ChatResult(text="It's about 250 kilometers."),
    )
    agent = Agent(config=cfg, memory=mem, emit=lambda p: None, dry_run=False, llm_client=fake)
    result = agent.process("how far is chandigarh from delhi")
    assert result.tools_run == ["web_search"]
    assert result.spoken == "It's about 250 kilometers."
    scripted_choices = [
        tc for tc, tools in zip(fake.received_tool_choice, fake.received_tools) if tools is not None
    ]
    assert scripted_choices == ["auto", "required"]  # forced retry after intent narration


def test_fresh_info_question_uses_lookup_fast_path(cfg, mem, monkeypatch):
    import tools as tools_mod

    monkeypatch.setattr(tools_mod, "_fetch_search_results", lambda q, limit=5: [
        {"title": "Distance", "snippet": "About 250 km by road."},
    ])
    cfg.ai_mode = "local"
    fake = FakeClient(ChatResult(text="It's about 250 kilometers."))  # synthesis only
    fake.classifier_answer = "YES"
    agent = Agent(config=cfg, memory=mem, emit=lambda p: None, dry_run=False, llm_client=fake)
    result = agent.process("how far is chandigarh from delhi")
    assert result.tools_run == ["web_search"]
    assert result.spoken == "It's about 250 kilometers."
    assert fake.main_calls() == 0  # synthesis only: no planning call at all


def test_stable_question_keeps_direct_answer(cfg, mem):
    cfg.ai_mode = "local"
    fake = FakeClient(
        ChatResult(text="2 plus 2 equals 4."),
        ChatResult(text="NO"),
    )
    agent = Agent(config=cfg, memory=mem, emit=lambda p: None, dry_run=False, llm_client=fake)
    result = agent.process("what is 2 plus 2")
    assert result.tools_run == []
    assert result.spoken == "2 plus 2 equals 4."


def test_lookup_fast_path_routes_weather_vs_search(cfg, mem, monkeypatch):
    import tools as tools_mod

    monkeypatch.setattr(tools_mod, "_fetch_search_results", lambda q, limit=5: [
        {"title": "Paris weather", "snippet": "12 degrees and cloudy."},
    ])
    cfg.ai_mode = "local"

    fake = FakeClient(ChatResult(text="It's 12 degrees in Paris."))
    fake.classifier_answer = "YES"
    agent = Agent(config=cfg, memory=mem, emit=lambda p: None, dry_run=True, llm_client=fake)
    result = agent.process("what is the weather in Paris")
    assert result.tools_run == ["web_search"]  # location -> search, not local weather

    fake2 = FakeClient(ChatResult(text="It's 26 degrees."))
    fake2.classifier_answer = "YES"
    agent2 = Agent(config=cfg, memory=mem, emit=lambda p: None, dry_run=True, llm_client=fake2)
    result2 = agent2.process("how is the weather")
    assert result2.tools_run == ["weather"]  # no location -> local weather tool


def test_direct_search_fallback_when_model_wont_call(cfg, mem, monkeypatch):
    import tools as tools_mod

    monkeypatch.setattr(tools_mod, "_fetch_search_results", lambda q, limit=5: [
        {"title": "Distance", "snippet": "About 250 km."},
    ])
    cfg.ai_mode = "local"
    fake = FakeClient(
        ChatResult(text="Chandigarh is about 110 kilometers from Delhi."),
        ChatResult(text="I'm not sure how to proceed."),  # forced lookup returns text, not a call
        ChatResult(text="It's about 250 kilometers."),    # synthesis
    )
    fake.classifier_answer = "YES"
    agent = Agent(config=cfg, memory=mem, emit=lambda p: None, dry_run=False, llm_client=fake)
    # Not a question, so no fast path: exercises the recovery fallback.
    result = agent.process("tell me the distance from chandigarh to delhi")
    assert result.tools_run == ["web_search"]
    assert result.spoken == "It's about 250 kilometers."


def test_refusals_are_not_replayed_as_history(cfg, mem):
    cfg.ai_mode = "local"
    agent, _ = make_agent(cfg, mem)
    mem.add_turn("user", "how is the weather")
    mem.add_turn(
        "assistant",
        "I am sorry but I'm not able to provide that because it's not in my tools.",
    )
    messages = agent._build_messages("open chrome")
    contents = [m["content"] for m in messages]
    assert not any("not able to provide" in c for c in contents)


def test_weather_question_falls_back_to_weather_tool(cfg, mem):
    cfg.ai_mode = "local"
    fake = FakeClient(
        ChatResult(text="I'm sorry, but I don't have access to weather information."),
        ChatResult(text="I'm sorry, I don't have a function to check the weather."),
        ChatResult(text="I'm sorry, I still can't help with that."),
    )
    agent = Agent(config=cfg, memory=mem, emit=lambda p: None, dry_run=True, llm_client=fake)
    result = agent.process("how is the weather")
    assert result.tools_run == ["weather"]


def test_mixed_question_and_command_skips_fast_path(cfg, mem):
    cfg.ai_mode = "local"
    fake = FakeClient(
        ChatResult(tool_calls=[
            ToolCall(name="weather", arguments={}),
            ToolCall(name="open_app", arguments={"app": "chrome"}),
        ]),
    )
    fake.classifier_answer = "YES"
    agent = Agent(config=cfg, memory=mem, emit=lambda p: None, dry_run=True, llm_client=fake)
    result = agent.process("what's the weather and open chrome")
    # Model drives: both tools chained in one response
    assert result.tools_run == ["weather", "open_app"]


def test_state_claim_never_accepted_without_tool(cfg, mem):
    cfg.ai_mode = "local"
    fake = FakeClient(
        ChatResult(text="Chrome is already open."),
        ChatResult(text="Done."),  # forced retry still text
    )
    agent = Agent(config=cfg, memory=mem, emit=lambda p: None, dry_run=True, llm_client=fake)
    result = agent.process("open chrome")
    assert result.tools_run == []
    assert result.ok is False
    assert "couldn't" in result.spoken
