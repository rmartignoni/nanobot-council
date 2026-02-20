"""Pydantic models for roundtable debate configuration."""

from pydantic import BaseModel, Field


class PersonaConfig(BaseModel):
    """Configuration for a single debate persona."""

    name: str
    system_prompt: str
    model: str | None = None
    temperature: float | None = None
    max_tokens: int | None = None
    tools: list[str] = Field(default_factory=list)


class OrchestratorConfig(BaseModel):
    """Configuration for the debate orchestrator."""

    model: str | None = None
    synthesis_prompt: str = (
        "Synthesize the debate into a clear recommendation with rationale, "
        "noting points of agreement and disagreement."
    )


class RoundsConfig(BaseModel):
    """Configuration for debate rounds."""

    max: int = 3
    min: int = 1
    convergence: bool = True


class RoundtableConfig(BaseModel):
    """Configuration for a roundtable debate loaded from YAML."""

    name: str
    description: str = ""
    trigger: str = "auto"  # auto | explicit
    orchestrator: OrchestratorConfig = Field(default_factory=OrchestratorConfig)
    rounds: RoundsConfig = Field(default_factory=RoundsConfig)
    personas: list[PersonaConfig] = Field(default_factory=list)
