"""CLI commands for nanobot — main entry point and shared utilities."""

from pathlib import Path

import typer
from rich.console import Console

from nanobot import __version__, __logo__
from nanobot.config.schema import Config

# ---------------------------------------------------------------------------
# Typer app (entry point registered in pyproject.toml)
# ---------------------------------------------------------------------------

app = typer.Typer(
    name="nanobot",
    help=f"{__logo__} nanobot - Personal AI Assistant",
    no_args_is_help=True,
)

console = Console()


# ---------------------------------------------------------------------------
# Version callback
# ---------------------------------------------------------------------------

def version_callback(value: bool):
    if value:
        console.print(f"{__logo__} nanobot v{__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: bool = typer.Option(
        None, "--version", "-v", callback=version_callback, is_eager=True
    ),
):
    """nanobot - Personal AI Assistant."""
    pass


# ---------------------------------------------------------------------------
# Logging setup
# ---------------------------------------------------------------------------

_logging_configured = False


def _setup_logging() -> None:
    """Configure persistent file logging with loguru (idempotent)."""
    global _logging_configured
    if _logging_configured:
        return
    _logging_configured = True

    from loguru import logger

    log_dir = Path.home() / ".nanobot" / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    logger.add(
        log_dir / "nanobot.log",
        rotation="10 MB",
        retention="7 days",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level:<8} | {name}:{function}:{line} | {message}",
        level="DEBUG",
    )


# ---------------------------------------------------------------------------
# Provider factory (shared by agent_cmd, gateway_cmd, cron_cmd)
# ---------------------------------------------------------------------------

def _make_provider(config: Config):
    """Create the appropriate LLM provider from config."""
    from nanobot.providers.litellm_provider import LiteLLMProvider
    from nanobot.providers.openai_codex_provider import OpenAICodexProvider
    from nanobot.providers.custom_provider import CustomProvider

    model = config.agents.defaults.model
    provider_name = config.get_provider_name(model)
    p = config.get_provider(model)

    # OpenAI Codex (OAuth)
    if provider_name == "openai_codex" or model.startswith("openai-codex/"):
        return OpenAICodexProvider(default_model=model)

    # Custom: direct OpenAI-compatible endpoint, bypasses LiteLLM
    if provider_name == "custom":
        return CustomProvider(
            api_key=p.get_api_key_value() if p else "no-key",
            api_base=config.get_api_base(model) or "http://localhost:8000/v1",
            default_model=model,
        )

    from nanobot.providers.registry import find_by_name
    spec = find_by_name(provider_name)
    if not model.startswith("bedrock/") and not (p and p.api_key) and not (spec and spec.is_oauth):
        console.print("[red]Error: No API key configured.[/red]")
        console.print("Set one in ~/.nanobot/config.json under providers section")
        raise typer.Exit(1)

    return LiteLLMProvider(
        api_key=p.get_api_key_value() if p else None,
        api_base=config.get_api_base(model),
        default_model=model,
        extra_headers=p.extra_headers if p else None,
        provider_name=provider_name,
    )


# ---------------------------------------------------------------------------
# AgentLoop factory (replaces 3 duplicate instantiation sites)
# ---------------------------------------------------------------------------

def _create_agent_loop(
    config: Config,
    bus,
    cron_service=None,
    session_manager=None,
):
    """Create an AgentLoop with standard configuration from config."""
    from nanobot.agent.loop import AgentLoop

    provider = _make_provider(config)

    return AgentLoop(
        bus=bus,
        provider=provider,
        workspace=config.workspace_path,
        model=config.agents.defaults.model,
        temperature=config.agents.defaults.temperature,
        max_tokens=config.agents.defaults.max_tokens,
        max_iterations=config.agents.defaults.max_tool_iterations,
        memory_window=config.agents.defaults.memory_window,
        brave_api_key=config.tools.web.search.api_key.get_secret_value() if config.tools.web.search.api_key else None,
        exec_config=config.tools.exec,
        cron_service=cron_service,
        restrict_to_workspace=config.tools.restrict_to_workspace,
        session_manager=session_manager,
        mcp_servers=config.tools.mcp_servers,
        config=config,
    )


# ---------------------------------------------------------------------------
# Register commands from sub-modules
# ---------------------------------------------------------------------------

# Onboard
from nanobot.cli.onboard_cmd import onboard as _onboard_fn  # noqa: E402
app.command()(_onboard_fn)

# Agent
from nanobot.cli.agent_cmd import agent as _agent_fn  # noqa: E402
app.command()(_agent_fn)

# Gateway
from nanobot.cli.gateway_cmd import gateway as _gateway_fn  # noqa: E402
app.command()(_gateway_fn)

# Status (small, kept inline)
@app.command()
def status():
    """Show nanobot status."""
    from nanobot.config.loader import load_config, get_config_path

    config_path = get_config_path()
    config = load_config()
    workspace = config.workspace_path

    console.print(f"{__logo__} nanobot Status\n")

    console.print(f"Config: {config_path} {'[green]✓[/green]' if config_path.exists() else '[red]✗[/red]'}")
    console.print(f"Workspace: {workspace} {'[green]✓[/green]' if workspace.exists() else '[red]✗[/red]'}")

    if config_path.exists():
        from nanobot.providers.registry import PROVIDERS

        console.print(f"Model: {config.agents.defaults.model}")

        # Check API keys from registry
        for spec in PROVIDERS:
            p = getattr(config.providers, spec.name, None)
            if p is None:
                continue
            if spec.is_oauth:
                console.print(f"{spec.label}: [green]✓ (OAuth)[/green]")
            elif spec.is_local:
                # Local deployments show api_base instead of api_key
                if p.api_base:
                    console.print(f"{spec.label}: [green]✓ {p.api_base}[/green]")
                else:
                    console.print(f"{spec.label}: [dim]not set[/dim]")
            else:
                has_key = bool(p.api_key)
                console.print(f"{spec.label}: {'[green]✓[/green]' if has_key else '[dim]not set[/dim]'}")


# Sub-apps: cron, provider, channels
from nanobot.cli.cron_cmd import cron_app  # noqa: E402
app.add_typer(cron_app, name="cron")

from nanobot.cli.provider_cmd import provider_app  # noqa: E402
app.add_typer(provider_app, name="provider")

from nanobot.cli.channels_cmd import channels_app  # noqa: E402
app.add_typer(channels_app, name="channels")


if __name__ == "__main__":
    app()
