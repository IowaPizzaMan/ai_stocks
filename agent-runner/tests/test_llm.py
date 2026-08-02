"""Unit tests for llm.py — Ollama client is faked; no network."""
import pytest

from llm import LLMError, generate_json

SCHEMA = {"type": "object", "properties": {"signal": {"type": "string"}}, "required": ["signal"]}


class FakeClient:
    def __init__(self, contents):
        self.contents = list(contents)
        self.calls = []

    def chat(self, **kwargs):
        self.calls.append(kwargs)
        return {"message": {"content": self.contents.pop(0)}}


def test_returns_parsed_json():
    client = FakeClient(['{"signal": "bullish"}'])
    out = generate_json("prompt", SCHEMA, client=client)
    assert out == {"signal": "bullish"}
    assert client.calls[0]["format"] == SCHEMA


def test_system_message_included():
    client = FakeClient(['{"signal": "ok"}'])
    generate_json("prompt", SCHEMA, system="you are a bot", client=client)
    messages = client.calls[0]["messages"]
    assert messages[0] == {"role": "system", "content": "you are a bot"}
    assert messages[1]["role"] == "user"


def test_retries_then_succeeds():
    client = FakeClient(["not json", '{"signal": "bearish"}'])
    out = generate_json("prompt", SCHEMA, client=client)
    assert out["signal"] == "bearish"
    assert len(client.calls) == 2


def test_raises_after_exhausted_retries():
    client = FakeClient(["nope", "still nope"])
    with pytest.raises(LLMError):
        generate_json("prompt", SCHEMA, retries=1, client=client)
