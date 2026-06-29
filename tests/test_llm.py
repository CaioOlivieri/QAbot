from unittest.mock import MagicMock

import pytest

import qabot.agent.llm as llm


class _FakeResponse:
    def __init__(self, payload: dict) -> None:
        self._payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return self._payload


class _FakeHTTPClient:
    """Records the request and returns a canned response — never hits the network."""

    def __init__(self, payload: dict, calls: list) -> None:
        self._payload = payload
        self._calls = calls

    def __enter__(self) -> "_FakeHTTPClient":
        return self

    def __exit__(self, *exc) -> bool:
        return False

    def post(self, url, headers=None, json=None):
        self._calls.append({"url": url, "headers": headers, "json": json})
        return _FakeResponse(self._payload)


def _patch_httpx(monkeypatch, payload: dict) -> list:
    calls: list = []
    monkeypatch.setattr(
        llm.httpx, "Client", lambda timeout=None: _FakeHTTPClient(payload, calls)
    )
    return calls


# --- factory ----------------------------------------------------------------


def test_get_provider_defaults_to_gemini(monkeypatch) -> None:
    monkeypatch.delenv("QABOT_PROVIDER", raising=False)
    monkeypatch.setenv("GEMINI_API_KEY", "x")
    monkeypatch.setattr("google.genai.Client", lambda **_kw: object())
    assert isinstance(llm.get_provider(), llm.GeminiProvider)


def test_get_provider_openai_compatible(monkeypatch) -> None:
    monkeypatch.setenv("QABOT_PROVIDER", "openai-compatible")
    assert isinstance(llm.get_provider(), llm.OpenAICompatibleProvider)


def test_get_provider_anthropic(monkeypatch) -> None:
    monkeypatch.setenv("QABOT_PROVIDER", "anthropic")
    monkeypatch.setenv("QABOT_API_KEY", "x")
    assert isinstance(llm.get_provider(), llm.AnthropicProvider)


def test_get_provider_unknown_raises(monkeypatch) -> None:
    monkeypatch.setenv("QABOT_PROVIDER", "bogus")
    with pytest.raises(RuntimeError, match="Unknown QABOT_PROVIDER"):
        llm.get_provider()


# --- GeminiProvider (migrated from test_agent.py) ---------------------------


def test_gemini_provider_uses_model_from_env(monkeypatch) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "x")
    monkeypatch.setenv("QABOT_MODEL", "gemini-2.5-flash")
    fake_client = MagicMock()
    fake_client.models.generate_content.return_value = MagicMock(text="{}")
    monkeypatch.setattr("google.genai.Client", lambda **_kw: fake_client)
    provider = llm.GeminiProvider()
    assert provider.complete([{"role": "user", "content": "hi"}]) == "{}"
    kwargs = fake_client.models.generate_content.call_args.kwargs
    assert kwargs["model"] == "gemini-2.5-flash"


def test_gemini_provider_defaults_model_when_env_absent(monkeypatch) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "x")
    monkeypatch.delenv("QABOT_MODEL", raising=False)
    fake_client = MagicMock()
    fake_client.models.generate_content.return_value = MagicMock(text="{}")
    monkeypatch.setattr("google.genai.Client", lambda **_kw: fake_client)
    provider = llm.GeminiProvider()
    provider.complete([{"role": "user", "content": "hi"}])
    kwargs = fake_client.models.generate_content.call_args.kwargs
    assert kwargs["model"] == "gemini-2.5-flash-lite"


def test_gemini_provider_requires_api_key(monkeypatch) -> None:
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("QABOT_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="GEMINI_API_KEY"):
        llm.GeminiProvider()


# --- OpenAICompatibleProvider ----------------------------------------------


def test_openai_compatible_builds_request_and_parses(monkeypatch) -> None:
    monkeypatch.setenv("QABOT_API_KEY", "test-key")
    monkeypatch.setenv("QABOT_MODEL", "gpt-4o-mini")
    monkeypatch.delenv("QABOT_JSON_MODE", raising=False)
    monkeypatch.delenv("QABOT_BASE_URL", raising=False)
    calls = _patch_httpx(monkeypatch, {"choices": [{"message": {"content": "{}"}}]})
    provider = llm.OpenAICompatibleProvider()
    out = provider.complete(
        [{"role": "model", "content": "prev"}, {"role": "user", "content": "hi"}]
    )
    assert out == "{}"
    sent = calls[0]
    assert sent["url"].endswith("/chat/completions")
    messages = sent["json"]["messages"]
    assert messages[0]["role"] == "system"  # system prompt is prepended
    assert messages[1]["role"] == "assistant"  # internal "model" -> "assistant"
    assert sent["json"]["response_format"] == {"type": "json_object"}
    # the key is attached to the header (presence/format only, never the value)
    assert sent["headers"]["Authorization"].startswith("Bearer ")


def test_openai_compatible_json_mode_can_be_disabled(monkeypatch) -> None:
    monkeypatch.setenv("QABOT_JSON_MODE", "0")
    monkeypatch.setenv("QABOT_API_KEY", "test-key")
    calls = _patch_httpx(monkeypatch, {"choices": [{"message": {"content": "{}"}}]})
    provider = llm.OpenAICompatibleProvider()
    provider.complete([{"role": "user", "content": "hi"}])
    assert "response_format" not in calls[0]["json"]


# --- AnthropicProvider ------------------------------------------------------


def test_anthropic_builds_request_and_parses(monkeypatch) -> None:
    monkeypatch.setenv("QABOT_API_KEY", "test-key")
    monkeypatch.setenv("QABOT_MODEL", "claude-sonnet-4-6")
    monkeypatch.delenv("QABOT_BASE_URL", raising=False)
    calls = _patch_httpx(monkeypatch, {"content": [{"type": "text", "text": "{}"}]})
    provider = llm.AnthropicProvider()
    out = provider.complete(
        [{"role": "model", "content": "prev"}, {"role": "user", "content": "hi"}]
    )
    assert out == "{}"
    sent = calls[0]
    assert sent["url"].endswith("/v1/messages")
    assert "x-api-key" in sent["headers"]  # presence only, never the value
    assert sent["headers"]["anthropic-version"] == "2023-06-01"
    body = sent["json"]
    assert body["system"]  # system is a top-level field, not a message
    assert body["max_tokens"] > 0  # Anthropic requires max_tokens
    assert body["model"] == "claude-sonnet-4-6"
    assert body["messages"][0]["role"] == "assistant"  # "model" -> "assistant"


def test_anthropic_requires_api_key(monkeypatch) -> None:
    monkeypatch.delenv("QABOT_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="anthropic provider"):
        llm.AnthropicProvider()
