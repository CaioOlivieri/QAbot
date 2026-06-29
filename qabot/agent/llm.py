"""Provider-agnostic LLM layer.

A thin abstraction (:class:`LLMProvider`) over chat-completion APIs so QAbot can
run against any model/provider, not just Gemini. :func:`get_provider` selects the
implementation from the environment:

    QABOT_PROVIDER  = gemini | openai-compatible | anthropic   (default: gemini)
    QABOT_MODEL     = model id (a provider-specific default is used if unset)
    QABOT_API_KEY   = API key for the chosen provider
                      (gemini also accepts the legacy GEMINI_API_KEY;
                       openai-compatible also accepts OPENAI_API_KEY;
                       anthropic also accepts ANTHROPIC_API_KEY)
    QABOT_BASE_URL  = base URL override (openai-compatible and anthropic)
    QABOT_JSON_MODE = "0" disables the JSON response_format on openai-compatible
                      endpoints that reject it (default: enabled)

Each provider exposes ``complete(messages) -> str``. ``messages`` is QAbot's
internal history — ``[{"role": "user" | "model", "content": str}, ...]`` (the
"model" role is Gemini's term for the assistant). Providers map that role to their
own vocabulary and apply JSON mode where the API supports it; the agent's tolerant
``_parse_agent_json`` handles any non-strict output. The system prompt is sent the
way each API expects (Gemini: ``system_instruction``; OpenAI: a leading
``{"role": "system"}`` message; Anthropic: the top-level ``system`` field).

API keys are read only from the environment and only ever placed in the outbound
request to the chosen provider's own endpoint — never logged, printed, or embedded
in an exception message.
"""

import os
from typing import Protocol

import httpx

from qabot.agent.prompts import SYSTEM_PROMPT

_HTTP_TIMEOUT = 120
_DEFAULT_MAX_OUTPUT_TOKENS = 8192


class LLMProvider(Protocol):
    def complete(self, messages: list[dict[str, str]]) -> str: ...


def _assistant_role(role: str) -> str:
    """Map QAbot's internal 'model' role to the OpenAI/Anthropic 'assistant'."""
    return "assistant" if role == "model" else role


class GeminiProvider:
    """Native Google Gemini via ``google-genai`` (the original path)."""

    def __init__(self) -> None:
        from google import genai  # lazy import

        api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("QABOT_API_KEY")
        if not api_key:
            raise RuntimeError(
                "GEMINI_API_KEY (or QABOT_API_KEY) is required for the gemini provider"
            )
        self._client = genai.Client(api_key=api_key)
        self._model = os.environ.get("QABOT_MODEL", "gemini-2.5-flash-lite")

    def complete(self, messages: list[dict[str, str]]) -> str:
        from google.genai import types  # lazy import

        contents = [
            types.Content(role=m["role"], parts=[types.Part(text=m["content"])])
            for m in messages
        ]
        response = self._client.models.generate_content(
            model=self._model,
            contents=contents,
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT,
                response_mime_type="application/json",
            ),
        )
        return response.text


class OpenAICompatibleProvider:
    """Any OpenAI-compatible ``/chat/completions`` endpoint.

    Covers OpenAI, OpenRouter, Together, Groq, Fireworks, DeepSeek, Mistral, and
    local servers (Ollama, vLLM, LM Studio), plus Gemini's own OpenAI-compatible
    endpoint. Uses ``httpx`` directly (no extra dependency).
    """

    def __init__(self) -> None:
        self._api_key = os.environ.get("QABOT_API_KEY") or os.environ.get(
            "OPENAI_API_KEY", ""
        )
        self._base_url = os.environ.get(
            "QABOT_BASE_URL", "https://api.openai.com/v1"
        ).rstrip("/")
        self._model = os.environ.get("QABOT_MODEL", "gpt-4o-mini")
        self._json_mode = os.environ.get("QABOT_JSON_MODE", "1") != "0"

    def complete(self, messages: list[dict[str, str]]) -> str:
        payload_messages: list[dict[str, str]] = [
            {"role": "system", "content": SYSTEM_PROMPT}
        ]
        payload_messages.extend(
            {"role": _assistant_role(m["role"]), "content": m["content"]}
            for m in messages
        )
        payload: dict[str, object] = {
            "model": self._model,
            "messages": payload_messages,
        }
        if self._json_mode:
            payload["response_format"] = {"type": "json_object"}
        headers = {"Content-Type": "application/json"}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"
        with httpx.Client(timeout=_HTTP_TIMEOUT) as client:
            resp = client.post(
                f"{self._base_url}/chat/completions", headers=headers, json=payload
            )
            resp.raise_for_status()
            data = resp.json()
        return data["choices"][0]["message"]["content"]


class AnthropicProvider:
    """Native Anthropic Messages API (``POST /v1/messages``) via ``httpx``.

    Anthropic is not OpenAI-compatible: ``system`` is a top-level field (not a
    message), ``max_tokens`` is required, and auth uses the ``x-api-key`` header
    with ``anthropic-version``. There is no strict JSON mode, so QAbot relies on
    the system prompt plus the tolerant ``_parse_agent_json`` fallback.
    """

    def __init__(self) -> None:
        self._api_key = os.environ.get("QABOT_API_KEY") or os.environ.get(
            "ANTHROPIC_API_KEY", ""
        )
        if not self._api_key:
            raise RuntimeError(
                "QABOT_API_KEY (or ANTHROPIC_API_KEY) is required for the "
                "anthropic provider"
            )
        self._base_url = os.environ.get(
            "QABOT_BASE_URL", "https://api.anthropic.com"
        ).rstrip("/")
        self._model = os.environ.get("QABOT_MODEL", "claude-opus-4-8")
        self._max_tokens = _DEFAULT_MAX_OUTPUT_TOKENS

    def complete(self, messages: list[dict[str, str]]) -> str:
        payload = {
            "model": self._model,
            "max_tokens": self._max_tokens,
            "system": SYSTEM_PROMPT,
            "messages": [
                {"role": _assistant_role(m["role"]), "content": m["content"]}
                for m in messages
            ],
        }
        headers = {
            "Content-Type": "application/json",
            "x-api-key": self._api_key,
            "anthropic-version": "2023-06-01",
        }
        with httpx.Client(timeout=_HTTP_TIMEOUT) as client:
            resp = client.post(
                f"{self._base_url}/v1/messages", headers=headers, json=payload
            )
            resp.raise_for_status()
            data = resp.json()
        return "".join(
            block.get("text", "")
            for block in data.get("content", [])
            if block.get("type") == "text"
        )


_PROVIDERS: dict[str, type] = {
    "gemini": GeminiProvider,
    "openai-compatible": OpenAICompatibleProvider,
    "anthropic": AnthropicProvider,
}


def get_provider() -> LLMProvider:
    """Build the provider selected by ``QABOT_PROVIDER`` (default ``gemini``)."""
    name = os.environ.get("QABOT_PROVIDER", "gemini").strip().lower()
    try:
        provider_cls = _PROVIDERS[name]
    except KeyError:
        raise RuntimeError(
            f"Unknown QABOT_PROVIDER {name!r}; expected one of "
            f"{', '.join(sorted(_PROVIDERS))}"
        ) from None
    return provider_cls()
