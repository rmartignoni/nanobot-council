"""Debate tool for initiating multi-persona roundtable discussions."""

from typing import Any, Awaitable, Callable, TYPE_CHECKING

from nanobot.agent.tools.base import Tool

if TYPE_CHECKING:
    from nanobot.agent.debate.orchestrator import DebateOrchestrator


class DebateTool(Tool):
    """
    Tool to initiate a multi-persona debate (roundtable).

    The agent uses this tool to start a structured debate where multiple
    personas discuss a question across multiple rounds, and the orchestrator
    synthesizes their discussion into a final recommendation.
    """

    def __init__(self, orchestrator: "DebateOrchestrator"):
        self._orchestrator = orchestrator
        self._on_progress: Callable[[str], Awaitable[None]] | None = None

    def set_context(self, on_progress: Callable[[str], Awaitable[None]] | None = None) -> None:
        """Set the progress callback for streaming debate status."""
        self._on_progress = on_progress

    @property
    def name(self) -> str:
        return "debate"

    @property
    def description(self) -> str:
        roundtables = self._orchestrator.list_roundtables()
        if roundtables:
            listing = "; ".join(
                f'"{rt.name}" - {rt.description}' if rt.description else f'"{rt.name}"'
                for rt in roundtables
            )
            return (
                "Start a multi-persona debate (roundtable) to get diverse expert perspectives "
                "on a question. Multiple personas with different expertise debate across rounds "
                "and produce a synthesized recommendation. "
                f"Available roundtables: {listing}. "
                "Use this for strategic decisions, complex analysis, or when multiple viewpoints are valuable."
            )
        return (
            "Start a multi-persona debate (roundtable) to get diverse expert perspectives "
            "on a question. No roundtables are currently configured. "
            "Create YAML files in workspace/roundtables/ to define roundtables."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "question": {
                    "type": "string",
                    "description": "The question or topic for the personas to debate",
                },
                "roundtable": {
                    "type": "string",
                    "description": (
                        "Name of the roundtable to use (filename without .yaml, "
                        "or the roundtable's display name). If omitted, uses the first available roundtable."
                    ),
                },
            },
            "required": ["question"],
        }

    async def execute(self, question: str, roundtable: str | None = None, **kwargs: Any) -> str:
        """Execute a debate and return the synthesized result."""
        # Find the roundtable config
        if roundtable:
            rt_config = self._orchestrator.get_roundtable(roundtable)
            if not rt_config:
                available = self._orchestrator.list_roundtables()
                names = ", ".join(rt.name for rt in available) if available else "none"
                return f"Error: Roundtable '{roundtable}' not found. Available: {names}"
        else:
            available = self._orchestrator.list_roundtables()
            if not available:
                return (
                    "Error: No roundtables configured. "
                    "Create YAML files in workspace/roundtables/ to define roundtables."
                )
            rt_config = available[0]

        try:
            result = await self._orchestrator.run_debate(
                question=question,
                roundtable=rt_config,
                on_progress=self._on_progress,
            )
            return result
        except Exception as e:
            return f"Error during debate: {str(e)}"
