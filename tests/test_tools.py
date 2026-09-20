"""Tools: registry validity, dispatch, dry-run behavior, protection guards."""

import pytest

import tools
from tools import ExecutorContext, ToolResult, execute, tool_schemas


@pytest.fixture
def ctx(cfg, mem, captured_events):
    return ExecutorContext(config=cfg, memory=mem, emit=captured_events.append, dry_run=True)


# --- Registry sanity ---

def test_registry_names_unique():
    names = [t.name for t in tools.TOOLS]
    assert len(names) == len(set(names))


def test_every_tool_has_valid_schema():
    for t in tools.TOOLS:
        assert t.description.strip(), t.name
        assert t.parameters["type"] == "object", t.name
        assert callable(t.executor), t.name
        for req in t.parameters.get("required", []):
            assert req in t.parameters["properties"], f"{t.name}.{req} not in properties"


def test_tool_schemas_openai_format():
    schemas = tool_schemas()
    assert len(schemas) == len(tools.TOOLS)
    for s in schemas:
        assert s["type"] == "function"
        assert set(s["function"].keys()) == {"name", "description", "parameters"}


def test_expected_tool_surface():
    names = {t.name for t in tools.TOOLS}
    assert {
        "open_app", "google_search", "play_music", "media_control", "volume_control",
        "brightness_control", "window_control", "screenshot", "clipboard",
        "keyboard_shortcut", "dictate", "press_key", "power_control", "weather",
        "remember_fact",
    } <= names


# --- Dispatch ---

def test_execute_unknown_tool(ctx):
    result = execute(ctx, "hack_the_planet", {})
    assert result.ok is False
    assert result.speak is True


def test_execute_filters_unexpected_args(ctx):
    result = execute(ctx, "open_app", {"app": "chrome", "evil": "rm -rf"})
    assert result.ok is True


def test_execute_never_raises_on_executor_exception(ctx, monkeypatch):
    def boom(**kwargs):
        raise RuntimeError("explosion")

    monkeypatch.setitem(tools._BY_NAME["open_app"].__dict__, "executor", boom)
    result = execute(ctx, "open_app", {"app": "x"})
    assert result.ok is False


# --- Dry-run behavior (nothing touches the OS) ---

@pytest.mark.parametrize("name,args", [
    ("open_app", {"app": "chrome"}),
    ("google_search", {"query": "space news"}),
    ("play_music", {"song": "drake"}),
    ("media_control", {"action": "pause"}),
    ("volume_control", {"action": "up"}),
    ("brightness_control", {"direction": "down"}),
    ("window_control", {"action": "close", "app": "notepad"}),
    ("screenshot", {}),
    ("clipboard", {"action": "paste"}),
    ("keyboard_shortcut", {"shortcut": "undo"}),
    ("dictate", {"text": "hello world"}),
    ("press_key", {"key": "enter"}),
    ("weather", {}),
])
def test_dry_run_touches_nothing(ctx, name, args):
    result = execute(ctx, name, args)
    assert isinstance(result, ToolResult)
    assert result.ok is True
    assert "would" in result.message.lower()


def test_dry_run_media_still_reports_command(ctx, captured_events):
    result = execute(ctx, "media_control", {"action": "next"})
    assert result.ok is True
    # Dry-run captures events rather than emitting — nothing leaves the process
    assert captured_events == []


# --- Specific executor logic ---

def test_media_control_alias_normalization(cfg, mem):
    events = []
    ctx = ExecutorContext(config=cfg, memory=mem, emit=events.append, dry_run=False)
    execute(ctx, "media_control", {"action": "previous"})
    assert events == [{"status": "media_control", "command": "prev"}]


def test_power_blocked_by_sensitive_protection(ctx, captured_events):
    ctx.config.protect_sensitive = True
    result = execute(ctx, "power_control", {"action": "shutdown"})
    assert result.ok is False
    assert captured_events[0]["status"] == "blocked_sensitive"


def test_power_allowed_when_protection_off(ctx):
    ctx.config.protect_sensitive = False
    result = execute(ctx, "power_control", {"action": "lock"})
    assert result.ok is True
    assert "would" in result.message.lower()


def test_remember_fact_persists(ctx, mem):
    result = execute(ctx, "remember_fact", {"key": "name", "value": "Sehaj"})
    assert result.ok is True
    assert dict(mem.facts())["name"] == "Sehaj"


def test_remember_fact_without_memory(cfg, captured_events):
    ctx = ExecutorContext(config=cfg, memory=None, emit=captured_events.append, dry_run=True)
    result = execute(ctx, "remember_fact", {"key": "a", "value": "b"})
    assert result.ok is False


def test_window_title_matching():
    titles = ["Document - Notepad", "GitHub - Google Chrome", "Spotify Premium"]
    title, score = tools._best_title_match("chrome", titles)
    assert title == "GitHub - Google Chrome"
    title, score = tools._best_title_match("spotify", titles)
    assert title == "Spotify Premium"
    title, score = tools._best_title_match("zzz-nonexistent", titles)
    assert score < 0.45


def test_keyboard_shortcut_unknown(ctx):
    result = execute(ctx, "keyboard_shortcut", {"shortcut": "explode"})
    assert result.ok is False


def test_weather_formats_message(ctx, monkeypatch):
    monkeypatch.setattr(tools, "_fetch_weather_data", lambda: {
        "city": "Toronto", "temp": 4, "humidity": 60, "wind": 12, "condition": "light snow",
    })
    ctx.dry_run = False
    result = execute(ctx, "weather", {})
    assert result.ok is True
    assert result.speak is True
    assert "Toronto" in result.message and "4 degrees" in result.message


def test_weather_failure_is_spoken(ctx, monkeypatch):
    def fail():
        raise RuntimeError("no network")

    monkeypatch.setattr(tools, "_fetch_weather_data", fail)
    ctx.dry_run = False
    result = execute(ctx, "weather", {})
    assert result.ok is False
    assert result.speak is True


# --- Web search ---

def test_web_search_dry_run(ctx):
    result = execute(ctx, "web_search", {"query": "distance chandigarh to delhi"})
    assert result.ok is True
    assert "Would search" in result.message
    assert result.needs_llm is False


def test_web_search_returns_data_for_llm(ctx, monkeypatch):
    monkeypatch.setattr(tools, "_fetch_search_results", lambda q, limit=5: [
        {"title": "Chandigarh to Delhi", "snippet": "About 250 km by road."},
        {"title": "Distance calculator", "snippet": "243 km as the crow flies."},
    ])
    ctx.dry_run = False
    result = execute(ctx, "web_search", {"query": "distance chandigarh to delhi"})
    assert result.ok is True
    assert result.needs_llm is True
    assert "Chandigarh to Delhi" in result.message
    assert "250 km" in result.message


def test_web_search_failure_is_spoken(ctx, monkeypatch):
    def fail(q, limit=5):
        raise RuntimeError("blocked")

    monkeypatch.setattr(tools, "_fetch_search_results", fail)
    ctx.dry_run = False
    result = execute(ctx, "web_search", {"query": "anything"})
    assert result.ok is False
    assert result.speak is True


def test_web_search_empty_results(ctx, monkeypatch):
    monkeypatch.setattr(tools, "_fetch_search_results", lambda q, limit=5: [])
    ctx.dry_run = False
    result = execute(ctx, "web_search", {"query": "asdfghjkl"})
    assert result.ok is False
