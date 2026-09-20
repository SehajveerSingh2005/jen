"""LLMClient: response parsing (native tool_calls + inlined JSON fallback), retries."""

import pytest

from client import ChatResult, LLMClient, LLMError, ToolCall, TransientLLMError, parse_response


def make_client():
    return LLMClient(base_url="http://test/v1", model="test-model")


def openai_response(tool_calls=None, content=None):
    message = {}
    if tool_calls is not None:
        message["tool_calls"] = tool_calls
    if content is not None:
        message["content"] = content
    return {"choices": [{"message": message}]}


# --- parse_response ---

def test_parses_native_tool_calls():
    data = openai_response(tool_calls=[{
        "id": "call_1",
        "type": "function",
        "function": {"name": "open_app", "arguments": '{"app": "chrome"}'},
    }])
    result = parse_response(data)
    assert result.tool_calls == [ToolCall(name="open_app", arguments={"app": "chrome"})]
    assert result.text is None


def test_parses_multiple_tool_calls():
    data = openai_response(tool_calls=[
        {"function": {"name": "open_app", "arguments": '{"app": "chrome"}'}},
        {"function": {"name": "volume_control", "arguments": '{"action": "up"}'}},
    ])
    result = parse_response(data)
    assert [c.name for c in result.tool_calls] == ["open_app", "volume_control"]


def test_tool_call_arguments_malformed_json_becomes_empty():
    data = openai_response(tool_calls=[{
        "function": {"name": "screenshot", "arguments": "not json"},
    }])
    result = parse_response(data)
    assert result.tool_calls == [ToolCall(name="screenshot", arguments={})]


def test_parses_plain_text():
    result = parse_response(openai_response(content="The sky is blue."))
    assert result.text == "The sky is blue."
    assert result.tool_calls == []


def test_parses_inlined_json_tool_call():
    result = parse_response(openai_response(content='{"name": "open_app", "arguments": {"app": "chrome"}}'))
    assert result.tool_calls == [ToolCall(name="open_app", arguments={"app": "chrome"})]


def test_inlined_json_with_trailing_junk():
    result = parse_response(openai_response(content='{"name": "mute", "args": {}}\nSure thing!'))
    # "mute" isn't required to be valid — the point is trailing junk doesn't crash
    assert result.text is not None or result.tool_calls


def test_malformed_response_raises():
    with pytest.raises(LLMError):
        parse_response({"choices": []})


# --- chat() with mocked _post ---

def test_chat_sends_tools_and_parses(monkeypatch):
    client = make_client()
    seen = {}

    def fake_post(payload):
        seen.update(payload)
        return openai_response(content="hi")

    monkeypatch.setattr(client, "_post", fake_post)
    result = client.chat([{"role": "user", "content": "hello"}], tools=[{"type": "function"}])
    assert result.text == "hi"
    assert seen["model"] == "test-model"
    assert seen["tools"] == [{"type": "function"}]
    assert seen["tool_choice"] == "auto"
    assert seen["stream"] is False


def test_chat_retries_transient_then_succeeds(monkeypatch):
    client = make_client()
    monkeypatch.setattr("client.time.sleep", lambda *_: None)
    calls = {"n": 0}

    def flaky_post(payload):
        calls["n"] += 1
        if calls["n"] == 1:
            raise TransientLLMError("timeout")
        return openai_response(content="recovered")

    monkeypatch.setattr(client, "_post", flaky_post)
    assert client.chat([]).text == "recovered"
    assert calls["n"] == 2


def test_chat_gives_up_after_retries(monkeypatch):
    client = make_client()
    monkeypatch.setattr("client.time.sleep", lambda *_: None)

    def always_fail(payload):
        raise TransientLLMError("down")

    monkeypatch.setattr(client, "_post", always_fail)
    with pytest.raises(LLMError):
        client.chat([])


def test_chat_fatal_error_not_retried(monkeypatch):
    client = make_client()
    calls = {"n": 0}

    def fatal(payload):
        calls["n"] += 1
        raise LLMError("401 unauthorized")

    monkeypatch.setattr(client, "_post", fatal)
    with pytest.raises(LLMError):
        client.chat([])
    assert calls["n"] == 1


def test_chat_result_defaults():
    r = ChatResult()
    assert r.text is None and r.tool_calls == []
