"""Reusable LLM <-> tool execution loop.

Used by both AgentLoop (main agent) and SubagentManager (background tasks).
"""

from __future__ import annotations

import json
import re
from typing import Any, Awaitable, Callable

from loguru import logger

from nanobot.agent.tools.registry import ToolRegistry
from nanobot.providers.base import LLMProvider


def _strip_think(text: str | None) -> str | None:
    """Remove <think>...</think> blocks that some models embed in content."""
    if not text:
        return None
    return re.sub(r"<think>[\s\S]*?</think>", "", text).strip() or None


def _tool_hint(tool_calls: list) -> str:
    """Format tool calls as concise hint, e.g. 'web_search("query")'."""

    def _fmt(tc):
        val = next(iter(tc.arguments.values()), None) if tc.arguments else None
        if not isinstance(val, str):
            return tc.name
        return f'{tc.name}("{val[:40]}...")' if len(val) > 40 else f'{tc.name}("{val}")'

    return ", ".join(_fmt(tc) for tc in tool_calls)


async def run_tool_loop(
    provider: LLMProvider,
    messages: list[dict[str, Any]],
    tools: ToolRegistry,
    model: str,
    temperature: float = 0.7,
    max_tokens: int = 4096,
    max_iterations: int = 20,
    text_only_retry: bool = True,
    on_progress: Callable[[str], Awaitable[None]] | None = None,
    on_tool_call: Callable[[str, str], None] | None = None,
) -> tuple[str | None, list[str]]:
    """Core LLM <-> tool execution loop.

    Repeatedly calls the LLM, executes any requested tool calls, appends
    results to the conversation, and loops until the model returns a
    plain-text response (no tool calls).

    Args:
        provider: The LLM provider to call.
        messages: Starting messages list (modified in-place).
        tools: ToolRegistry with available tools.
        model: Model identifier to use.
        temperature: Sampling temperature.
        max_tokens: Max tokens per LLM call.
        max_iterations: Safety cap on loop iterations.
        text_only_retry: If True, retry once when the LLM returns text
            before any tools have been used (handles models that send
            interim text before tool calls).
        on_progress: Optional async callback for intermediate content
            (stripped think blocks + tool hints).
        on_tool_call: Optional sync callback(tool_name, args_str) for
            logging tool executions.

    Returns:
        Tuple of (final_text_content_or_None, list_of_tool_names_used).
    """
    iteration = 0
    final_content: str | None = None
    tools_used: list[str] = []
    text_only_retried = False

    while iteration < max_iterations:
        iteration += 1

        response = await provider.chat(
            messages=messages,
            tools=tools.get_definitions(),
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
        )

        if response.has_tool_calls:
            # Push progress if callback provided
            if on_progress:
                clean = _strip_think(response.content)
                if clean:
                    await on_progress(clean)
                await on_progress(_tool_hint(response.tool_calls))

            # Build assistant message with tool calls
            tool_call_dicts = [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {
                        "name": tc.name,
                        "arguments": json.dumps(tc.arguments, ensure_ascii=False),
                    },
                }
                for tc in response.tool_calls
            ]

            assistant_msg: dict[str, Any] = {
                "role": "assistant",
                "content": response.content,
                "tool_calls": tool_call_dicts,
            }
            if response.reasoning_content:
                assistant_msg["reasoning_content"] = response.reasoning_content
            messages.append(assistant_msg)

            # Execute each tool call
            for tool_call in response.tool_calls:
                tools_used.append(tool_call.name)
                args_str = json.dumps(tool_call.arguments, ensure_ascii=False)

                if on_tool_call:
                    on_tool_call(tool_call.name, args_str)
                else:
                    logger.info("Tool call: {}({})", tool_call.name, args_str[:200])

                result = await tools.execute(tool_call.name, tool_call.arguments)
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "name": tool_call.name,
                        "content": result,
                    }
                )
        else:
            final_content = _strip_think(response.content)
            # Some models send an interim text response before tool calls.
            # Give them one retry; don't forward the text to avoid duplicates.
            if text_only_retry and not tools_used and not text_only_retried and final_content:
                text_only_retried = True
                logger.debug(
                    "Interim text response (no tools used yet), retrying: {}", final_content[:80]
                )
                final_content = None
                continue
            break

    return final_content, tools_used
