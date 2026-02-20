"""Tests for the core LLM <-> tool execution loop."""

import pytest
from unittest.mock import AsyncMock, MagicMock

from nanobot.agent.core_loop import run_tool_loop, _strip_think
from nanobot.providers.base import LLMResponse, ToolCallRequest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _text_response(content: str) -> LLMResponse:
    """Create an LLMResponse with only text content."""
    return LLMResponse(content=content)


def _tool_response(tool_name: str, tool_id: str, arguments: dict, content: str | None = None) -> LLMResponse:
    """Create an LLMResponse with a tool call."""
    return LLMResponse(
        content=content,
        tool_calls=[ToolCallRequest(id=tool_id, name=tool_name, arguments=arguments)],
        finish_reason="tool_calls",
    )


def _make_provider(*responses: LLMResponse) -> AsyncMock:
    """Create a mock provider that returns the given responses in order."""
    provider = AsyncMock()
    provider.chat = AsyncMock(side_effect=list(responses))
    return provider


def _make_tools(results: dict[str, str] | None = None) -> MagicMock:
    """Create a mock ToolRegistry."""
    tools = MagicMock()
    tools.get_definitions.return_value = [{"type": "function", "function": {"name": "test"}}]

    async def mock_execute(name, args):
        if results and name in results:
            return results[name]
        return f"Result from {name}"

    tools.execute = AsyncMock(side_effect=mock_execute)
    return tools


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestRunToolLoop:
    @pytest.mark.asyncio
    async def test_run_tool_loop_text_response(self):
        """Loop returns text when LLM responds without tool calls."""
        provider = _make_provider(_text_response("Hello user"))
        tools = _make_tools()
        messages = [{"role": "user", "content": "hi"}]

        content, tools_used = await run_tool_loop(
            provider=provider,
            messages=messages,
            tools=tools,
            model="test-model",
            text_only_retry=False,
        )

        assert content == "Hello user"
        assert tools_used == []

    @pytest.mark.asyncio
    async def test_run_tool_loop_with_tool_call(self):
        """Loop executes a tool call and returns the final text response."""
        provider = _make_provider(
            _tool_response("web_search", "call_1", {"query": "test"}),
            _text_response("Here are the results"),
        )
        tools = _make_tools({"web_search": "search results"})
        messages = [{"role": "user", "content": "search for test"}]

        content, tools_used = await run_tool_loop(
            provider=provider,
            messages=messages,
            tools=tools,
            model="test-model",
            text_only_retry=False,
        )

        assert content == "Here are the results"
        assert tools_used == ["web_search"]
        tools.execute.assert_awaited_once_with("web_search", {"query": "test"})

    @pytest.mark.asyncio
    async def test_run_tool_loop_max_iterations(self):
        """Loop stops after max_iterations even if tools keep being called."""
        # Create a provider that always returns tool calls
        infinite_tool = _tool_response("exec", "call_n", {"command": "echo hi"})
        provider = AsyncMock()
        provider.chat = AsyncMock(return_value=infinite_tool)
        tools = _make_tools({"exec": "ok"})
        messages = [{"role": "user", "content": "loop forever"}]

        content, tools_used = await run_tool_loop(
            provider=provider,
            messages=messages,
            tools=tools,
            model="test-model",
            max_iterations=3,
        )

        # After 3 iterations of tool calls, loop exits with no final text
        assert content is None
        assert len(tools_used) == 3

    @pytest.mark.asyncio
    async def test_run_tool_loop_strip_think(self):
        """Thinking tags are removed from the final response."""
        provider = _make_provider(
            _text_response("<think>Let me reason about this...</think>The answer is 42")
        )
        tools = _make_tools()
        messages = [{"role": "user", "content": "what is the answer?"}]

        content, tools_used = await run_tool_loop(
            provider=provider,
            messages=messages,
            tools=tools,
            model="test-model",
            text_only_retry=False,
        )

        assert content == "The answer is 42"
        assert "<think>" not in content

    @pytest.mark.asyncio
    async def test_run_tool_loop_text_only_retry(self):
        """When text_only_retry is True and no tools used yet, loop retries once."""
        provider = _make_provider(
            _text_response("Thinking..."),   # First: interim text, should be retried
            _tool_response("exec", "call_1", {"command": "ls"}),  # Second: tool call
            _text_response("Done!"),         # Third: final answer
        )
        tools = _make_tools({"exec": "file.txt"})
        messages = [{"role": "user", "content": "list files"}]

        content, tools_used = await run_tool_loop(
            provider=provider,
            messages=messages,
            tools=tools,
            model="test-model",
            text_only_retry=True,
        )

        assert content == "Done!"
        assert tools_used == ["exec"]
        # Provider should have been called 3 times (retry + tool + final)
        assert provider.chat.await_count == 3


class TestStripThink:
    def test_removes_think_tags(self):
        assert _strip_think("<think>reasoning</think>answer") == "answer"

    def test_returns_none_for_empty(self):
        assert _strip_think(None) is None
        assert _strip_think("") is None

    def test_returns_none_when_only_think(self):
        assert _strip_think("<think>only thinking</think>") is None

    def test_preserves_plain_text(self):
        assert _strip_think("just text") == "just text"
