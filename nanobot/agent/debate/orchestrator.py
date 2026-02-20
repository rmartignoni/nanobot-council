"""Debate orchestrator: manages rounds, convergence, and synthesis."""

import asyncio
from pathlib import Path
from typing import Any, Awaitable, Callable

import yaml
from loguru import logger

from nanobot.agent.debate.config import RoundtableConfig, PersonaConfig
from nanobot.agent.debate.persona import Persona
from nanobot.agent.tools.registry import ToolRegistry
from nanobot.providers.base import LLMProvider


# Tools that personas must never have access to (agent-level tools only)
_BLOCKED_PERSONA_TOOLS = frozenset({"message", "spawn", "debate", "cron"})


class DebateOrchestrator:
    """
    Orchestrates a multi-persona debate.

    Loads roundtable configs from YAML, creates Persona instances with
    isolated tool registries, runs debate rounds in parallel, checks
    convergence, and synthesizes the final result.
    """

    def __init__(
        self,
        workspace: Path,
        provider: LLMProvider,
        config: "Config",
        parent_tools: ToolRegistry,
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        brave_api_key: str | None = None,
        exec_config: Any = None,
        restrict_to_workspace: bool = False,
    ):
        from nanobot.config.schema import Config, ExecToolConfig

        self.workspace = workspace
        self.provider = provider
        self.config = config
        self.parent_tools = parent_tools
        self.model = model or provider.get_default_model()
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.brave_api_key = brave_api_key
        self.exec_config = exec_config or ExecToolConfig()
        self.restrict_to_workspace = restrict_to_workspace

    def list_roundtables(self) -> list[RoundtableConfig]:
        """List all available roundtable configs from workspace/roundtables/."""
        roundtables_dir = self.workspace / "roundtables"
        if not roundtables_dir.is_dir():
            return []

        configs = []
        for path in sorted(roundtables_dir.glob("*.yaml")):
            try:
                configs.append(self._load_roundtable(path))
            except Exception as e:
                logger.warning("Failed to load roundtable {}: {}", path.name, e)
        return configs

    def get_roundtable(self, name: str) -> RoundtableConfig | None:
        """Get a roundtable config by name (filename without .yaml)."""
        roundtables_dir = self.workspace / "roundtables"
        path = roundtables_dir / f"{name}.yaml"
        if not path.is_file():
            # Try matching by config name field
            for rt in self.list_roundtables():
                if rt.name.lower() == name.lower():
                    return rt
            return None
        return self._load_roundtable(path)

    async def run_debate(
        self,
        question: str,
        roundtable: RoundtableConfig,
        on_progress: Callable[[str], Awaitable[None]] | None = None,
    ) -> str:
        """
        Run a full debate and return the synthesized result.

        Args:
            question: The debate question.
            roundtable: The roundtable configuration.
            on_progress: Optional callback for streaming debate progress.

        Returns:
            The synthesized debate result.
        """
        logger.info("Starting debate '{}' with {} personas, max {} rounds",
                     roundtable.name, len(roundtable.personas), roundtable.rounds.max)

        if on_progress:
            names = ", ".join(p.name for p in roundtable.personas)
            await on_progress(f"debate({roundtable.name}): {names}")

        personas = self._create_personas(roundtable)
        transcript_entries: list[dict[str, str]] = []  # [{round, persona, response}]

        for round_num in range(1, roundtable.rounds.max + 1):
            logger.info("Debate '{}' round {}/{}", roundtable.name, round_num, roundtable.rounds.max)

            if on_progress:
                await on_progress(f"debate round {round_num}/{roundtable.rounds.max}")

            transcript_text = self._format_transcript(transcript_entries) if transcript_entries else None

            # Run all personas in parallel for this round
            tasks = [
                persona.respond(question, transcript_text, round_num)
                for persona in personas
            ]
            responses = await asyncio.gather(*tasks, return_exceptions=True)

            # Collect responses
            round_entries = []
            for persona, response in zip(personas, responses):
                if isinstance(response, Exception):
                    text = f"[Error: {response}]"
                    logger.error("Persona [{}] round {} failed: {}", persona.name, round_num, response)
                else:
                    text = response
                round_entries.append({
                    "round": str(round_num),
                    "persona": persona.name,
                    "response": text,
                })
            transcript_entries.extend(round_entries)

            # Check convergence after min_rounds
            if (roundtable.rounds.convergence
                    and round_num >= roundtable.rounds.min
                    and round_num < roundtable.rounds.max):
                if await self._check_convergence(question, transcript_entries, roundtable):
                    logger.info("Debate '{}' converged at round {}", roundtable.name, round_num)
                    if on_progress:
                        await on_progress(f"debate converged at round {round_num}")
                    break

        # Synthesize final result
        if on_progress:
            await on_progress("debate synthesis")

        result = await self._synthesize(question, transcript_entries, roundtable)
        logger.info("Debate '{}' completed", roundtable.name)
        return result

    def _create_personas(self, roundtable: RoundtableConfig) -> list[Persona]:
        """Create Persona instances with isolated providers and tool registries."""
        personas = []
        for pc in roundtable.personas:
            provider, model = self._resolve_persona_provider(pc)
            tools = self._build_persona_tools(pc)
            personas.append(Persona(
                config=pc,
                provider=provider,
                model=model,
                tools=tools,
                temperature=self.temperature,
                max_tokens=self.max_tokens,
            ))
        return personas

    def _resolve_persona_provider(self, pc: PersonaConfig) -> tuple[LLMProvider, str]:
        """Resolve the LLM provider and model for a persona."""
        persona_model = pc.model or self.model

        # If same model as parent, reuse parent provider
        if persona_model == self.model:
            return self.provider, self.model

        # Otherwise create a new provider for this persona's model
        from nanobot.providers.litellm_provider import LiteLLMProvider

        provider_name = self.config.get_provider_name(persona_model)
        p = self.config.get_provider(persona_model)

        if not p or not p.api_key:
            logger.warning("No API key for persona model {}, falling back to parent provider", persona_model)
            return self.provider, persona_model

        persona_provider = LiteLLMProvider(
            api_key=p.get_api_key_value(),
            api_base=self.config.get_api_base(persona_model),
            default_model=persona_model,
            extra_headers=p.extra_headers,
            provider_name=provider_name,
        )
        return persona_provider, persona_model

    def _build_persona_tools(self, pc: PersonaConfig) -> ToolRegistry:
        """Build a filtered ToolRegistry for a persona."""
        registry = ToolRegistry()

        if not pc.tools:
            return registry

        for tool_name in pc.tools:
            if tool_name in _BLOCKED_PERSONA_TOOLS:
                logger.warning("Persona '{}' cannot use blocked tool '{}'", pc.name, tool_name)
                continue
            tool = self.parent_tools.get(tool_name)
            if tool:
                registry.register(tool)
            else:
                logger.warning("Tool '{}' not found in parent registry for persona '{}'", tool_name, pc.name)

        return registry

    async def _check_convergence(
        self,
        question: str,
        transcript_entries: list[dict[str, str]],
        roundtable: RoundtableConfig,
    ) -> bool:
        """Check if the debate has converged using the orchestrator's LLM."""
        transcript_text = self._format_transcript(transcript_entries)

        # Use the orchestrator's model (or parent model)
        orch_model = roundtable.orchestrator.model or self.model
        orch_provider, _ = self._resolve_orchestrator_provider(roundtable)

        prompt = (
            "Analyze this debate transcript and determine if the participants have converged "
            "on a shared position or if further debate rounds would be productive.\n\n"
            f"**Question:** {question}\n\n"
            f"**Transcript:**\n{transcript_text}\n\n"
            "Respond with ONLY 'CONVERGED' if participants largely agree and further rounds "
            "would not add value, or 'CONTINUE' if there are still meaningful disagreements "
            "worth exploring."
        )

        response = await orch_provider.chat(
            messages=[
                {"role": "system", "content": "You are a debate moderator. Assess convergence concisely."},
                {"role": "user", "content": prompt},
            ],
            model=orch_model,
            temperature=0.3,
            max_tokens=50,
        )

        result = (response.content or "").strip().upper()
        return "CONVERGED" in result

    async def _synthesize(
        self,
        question: str,
        transcript_entries: list[dict[str, str]],
        roundtable: RoundtableConfig,
    ) -> str:
        """Synthesize the debate into a final response."""
        transcript_text = self._format_transcript(transcript_entries)
        orch_model = roundtable.orchestrator.model or self.model
        orch_provider, _ = self._resolve_orchestrator_provider(roundtable)

        synthesis_prompt = roundtable.orchestrator.synthesis_prompt.strip()

        prompt = (
            f"{synthesis_prompt}\n\n"
            f"**Question:** {question}\n\n"
            f"**Debate transcript:**\n{transcript_text}"
        )

        response = await orch_provider.chat(
            messages=[
                {"role": "system", "content": "You are an expert debate synthesizer."},
                {"role": "user", "content": prompt},
            ],
            model=orch_model,
            temperature=0.5,
            max_tokens=self.max_tokens,
        )

        return response.content or "[Synthesis produced no output]"

    def _resolve_orchestrator_provider(self, roundtable: RoundtableConfig) -> tuple[LLMProvider, str]:
        """Resolve provider for the orchestrator."""
        orch_model = roundtable.orchestrator.model or self.model
        if orch_model == self.model:
            return self.provider, self.model

        from nanobot.providers.litellm_provider import LiteLLMProvider

        provider_name = self.config.get_provider_name(orch_model)
        p = self.config.get_provider(orch_model)

        if not p or not p.api_key:
            return self.provider, orch_model

        return LiteLLMProvider(
            api_key=p.get_api_key_value(),
            api_base=self.config.get_api_base(orch_model),
            default_model=orch_model,
            extra_headers=p.extra_headers,
            provider_name=provider_name,
        ), orch_model

    @staticmethod
    def _format_transcript(entries: list[dict[str, str]]) -> str:
        """Format transcript entries into readable text."""
        lines = []
        current_round = ""
        for entry in entries:
            if entry["round"] != current_round:
                current_round = entry["round"]
                lines.append(f"\n--- Round {current_round} ---\n")
            lines.append(f"**{entry['persona']}:**\n{entry['response']}\n")
        return "\n".join(lines)

    @staticmethod
    def _load_roundtable(path: Path) -> RoundtableConfig:
        """Load and validate a roundtable config from a YAML file."""
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        return RoundtableConfig(**data)
