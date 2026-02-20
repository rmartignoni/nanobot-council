"""Tests for the LiteLLM provider."""

import pytest
from types import SimpleNamespace
from unittest.mock import patch, MagicMock

from nanobot.providers.litellm_provider import LiteLLMProvider
from nanobot.providers.base import LLMResponse, ToolCallRequest
from nanobot.providers.registry import ProviderSpec


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_provider(**kwargs):
    """Create a LiteLLMProvider with safe defaults (no real API calls)."""
    defaults = dict(api_key="test-key", default_model="anthropic/claude-sonnet-4-5")
    defaults.update(kwargs)
    with patch("nanobot.providers.litellm_provider.find_gateway", return_value=None):
        return LiteLLMProvider(**defaults)


_OPENROUTER_GATEWAY = ProviderSpec(
    name="openrouter",
    keywords=("openrouter",),
    env_key="OPENROUTER_API_KEY",
    litellm_prefix="openrouter",
    is_gateway=True,
    strip_model_prefix=False,
    supports_prompt_caching=True,
)

_VLLM_GATEWAY = ProviderSpec(
    name="vllm",
    keywords=("vllm",),
    env_key="HOSTED_VLLM_API_KEY",
    litellm_prefix="hosted_vllm",
    is_local=True,
    strip_model_prefix=True,
)


# ---------------------------------------------------------------------------
# _resolve_model
# ---------------------------------------------------------------------------

class TestResolveModel:
    def test_resolve_model_with_prefix(self):
        """openrouter gateway prepends 'openrouter/' to the model."""
        with patch("nanobot.providers.litellm_provider.find_gateway", return_value=_OPENROUTER_GATEWAY):
            provider = LiteLLMProvider(api_key="sk-or-test", default_model="meta-llama/llama-3")
        result = provider._resolve_model("meta-llama/llama-3")
        assert result == "openrouter/meta-llama/llama-3"

    def test_resolve_model_gateway(self):
        """Gateway with strip_model_prefix strips provider/ and re-prefixes."""
        with patch("nanobot.providers.litellm_provider.find_gateway", return_value=_VLLM_GATEWAY):
            provider = LiteLLMProvider(api_key="test", default_model="org/my-model")
        result = provider._resolve_model("org/my-model")
        assert result == "hosted_vllm/my-model"

    def test_resolve_model_standard(self):
        """Standard model without gateway keeps its name (Anthropic has no prefix)."""
        provider = _make_provider()
        result = provider._resolve_model("claude-sonnet-4-5")
        assert result == "claude-sonnet-4-5"


# ---------------------------------------------------------------------------
# _supports_cache_control
# ---------------------------------------------------------------------------

class TestSupportsCacheControl:
    def test_supports_cache_control_anthropic(self):
        """Anthropic models support cache control."""
        provider = _make_provider()
        assert provider._supports_cache_control("claude-sonnet-4-5") is True

    def test_supports_cache_control_other(self):
        """Non-Anthropic models (e.g. deepseek) do not support cache control."""
        provider = _make_provider()
        assert provider._supports_cache_control("deepseek-chat") is False


# ---------------------------------------------------------------------------
# _sanitize_messages
# ---------------------------------------------------------------------------

class TestSanitizeMessages:
    def test_sanitize_messages_removes_extra_keys(self):
        """Extra keys like 'reasoning_content' are stripped."""
        messages = [
            {"role": "assistant", "content": "hello", "reasoning_content": "thinking..."},
        ]
        result = LiteLLMProvider._sanitize_messages(messages)
        assert len(result) == 1
        assert "reasoning_content" not in result[0]
        assert result[0]["content"] == "hello"

    def test_sanitize_messages_preserves_required(self):
        """Standard keys (role, content, tool_calls, tool_call_id, name) are kept."""
        messages = [
            {"role": "assistant", "content": "hi", "tool_calls": [{"id": "1"}]},
            {"role": "tool", "tool_call_id": "1", "name": "exec", "content": "ok"},
        ]
        result = LiteLLMProvider._sanitize_messages(messages)
        assert result[0]["tool_calls"] == [{"id": "1"}]
        assert result[1]["tool_call_id"] == "1"
        assert result[1]["name"] == "exec"

    def test_sanitize_messages_adds_content_none_for_assistant(self):
        """Assistant messages without 'content' key get content=None."""
        messages = [{"role": "assistant", "tool_calls": [{"id": "1"}]}]
        result = LiteLLMProvider._sanitize_messages(messages)
        assert result[0]["content"] is None


# ---------------------------------------------------------------------------
# _parse_response
# ---------------------------------------------------------------------------

class TestParseResponse:
    def _make_litellm_response(
        self,
        content="hello",
        tool_calls=None,
        finish_reason="stop",
        reasoning_content=None,
        usage=None,
    ):
        """Build a mock LiteLLM response object."""
        message = SimpleNamespace(
            content=content,
            tool_calls=tool_calls,
            reasoning_content=reasoning_content,
        )
        choice = SimpleNamespace(message=message, finish_reason=finish_reason)
        usage_ns = SimpleNamespace(
            prompt_tokens=10,
            completion_tokens=20,
            total_tokens=30,
        ) if usage is None else SimpleNamespace(**usage)
        return SimpleNamespace(choices=[choice], usage=usage_ns)

    def test_parse_response_text_only(self):
        """Parse a response with only text, no tool calls."""
        provider = _make_provider()
        raw = self._make_litellm_response(content="Hello world")
        result = provider._parse_response(raw)

        assert isinstance(result, LLMResponse)
        assert result.content == "Hello world"
        assert result.tool_calls == []
        assert result.finish_reason == "stop"
        assert result.usage["total_tokens"] == 30

    def test_parse_response_with_tool_calls(self):
        """Parse a response containing tool calls."""
        tc = SimpleNamespace(
            id="call_1",
            function=SimpleNamespace(
                name="web_search",
                arguments='{"query": "test"}',
            ),
        )
        provider = _make_provider()
        raw = self._make_litellm_response(content=None, tool_calls=[tc], finish_reason="tool_calls")
        result = provider._parse_response(raw)

        assert result.has_tool_calls
        assert len(result.tool_calls) == 1
        assert result.tool_calls[0].name == "web_search"
        assert result.tool_calls[0].arguments == {"query": "test"}
        assert result.tool_calls[0].id == "call_1"

    def test_parse_response_with_reasoning(self):
        """Parse a response that includes reasoning_content (e.g. DeepSeek-R1)."""
        provider = _make_provider()
        raw = self._make_litellm_response(
            content="Final answer",
            reasoning_content="Let me think step by step...",
        )
        result = provider._parse_response(raw)

        assert result.content == "Final answer"
        assert result.reasoning_content == "Let me think step by step..."
