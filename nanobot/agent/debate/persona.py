"""Persona: inner loop for a single debate participant."""

import json
from typing import Any

from loguru import logger

from nanobot.agent.debate.config import PersonaConfig
from nanobot.agent.tools.registry import ToolRegistry
from nanobot.providers.base import LLMProvider


class Persona:
    """
    A debate persona that runs its own mini agent loop.

    Each persona has an independent LLM provider, model, tools, and system prompt.
    Follows the same inner-loop pattern as SubagentManager._run_subagent().
    """

    def __init__(
        self,
        config: PersonaConfig,
        provider: LLMProvider,
        model: str,
        tools: ToolRegistry,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ):
        self.config = config
        self.provider = provider
        self.model = model
        self.tools = tools
        self.temperature = config.temperature if config.temperature is not None else temperature
        self.max_tokens = config.max_tokens if config.max_tokens is not None else max_tokens
        self.name = config.name

    async def respond(
        self,
        question: str,
        transcript: str | None = None,
        round_num: int = 1,
    ) -> str:
        """
        Generate a response for this persona in the debate.

        Args:
            question: The debate question.
            transcript: Full transcript of previous rounds (None for round 1).
            round_num: Current round number (1-indexed).

        Returns:
            The persona's response text.
        """
        system_prompt = self._build_system_prompt(round_num)
        user_content = self._build_user_message(question, transcript, round_num)

        messages: list[dict[str, Any]] = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ]

        tool_defs = self.tools.get_definitions() if len(self.tools) > 0 else None
        max_iterations = 10
        iteration = 0
        final_result: str | None = None

        while iteration < max_iterations:
            iteration += 1

            response = await self.provider.chat(
                messages=messages,
                tools=tool_defs,
                model=self.model,
                temperature=self.temperature,
                max_tokens=self.max_tokens,
            )

            if response.has_tool_calls:
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
                messages.append(
                    {
                        "role": "assistant",
                        "content": response.content or "",
                        "tool_calls": tool_call_dicts,
                    }
                )

                for tool_call in response.tool_calls:
                    logger.debug("Persona [{}] executing: {}", self.name, tool_call.name)
                    result = await self.tools.execute(tool_call.name, tool_call.arguments)
                    messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": tool_call.id,
                            "name": tool_call.name,
                            "content": result,
                        }
                    )
            else:
                final_result = response.content
                break

        if final_result is None:
            final_result = (
                f"[{self.name} did not produce a response after {max_iterations} iterations]"
            )

        logger.info(
            "Persona [{}] round {} response ({} chars)", self.name, round_num, len(final_result)
        )
        return final_result

    def _build_system_prompt(self, round_num: int) -> str:
        """Build the system prompt for this persona."""
        base = self.config.system_prompt.strip()
        instructions = (
            f"\n\nYou are participating in a structured multi-persona debate as **{self.name}**. "
            f"This is round {round_num}."
        )
        if round_num == 1:
            instructions += (
                " Provide your initial analysis from your perspective. Be specific and substantive."
            )
        else:
            instructions += (
                " Review the other participants' responses from previous rounds. "
                "React, critique, refine your position, and highlight agreements or disagreements. "
                "Be constructive but honest."
            )
        return base + instructions

    def _build_user_message(
        self,
        question: str,
        transcript: str | None,
        round_num: int,
    ) -> str:
        """Build the user message with question and optional transcript."""
        parts = [f"**Question:** {question}"]
        if transcript and round_num > 1:
            parts.append(f"\n**Debate transcript so far:**\n\n{transcript}")
        parts.append(f"\n**Your response as {self.name} (round {round_num}):**")
        return "\n".join(parts)
