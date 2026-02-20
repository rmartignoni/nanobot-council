"""Shared tool factory for building common tool registries."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from nanobot.agent.tools.filesystem import EditFileTool, ListDirTool, ReadFileTool, WriteFileTool
from nanobot.agent.tools.registry import ToolRegistry
from nanobot.agent.tools.shell import ExecTool
from nanobot.agent.tools.web import WebFetchTool, WebSearchTool

if TYPE_CHECKING:
    from nanobot.config.schema import ExecToolConfig


def build_safe_tools(
    workspace: Path,
    exec_config: "ExecToolConfig",
    brave_api_key: str | None = None,
    restrict_to_workspace: bool = False,
) -> ToolRegistry:
    """Build a ToolRegistry with the safe base tools (filesystem, shell, web).

    These tools are shared between the main AgentLoop and SubagentManager.
    Agent-level tools (message, spawn, debate, cron) are NOT included.

    Args:
        workspace: Path to the workspace directory.
        exec_config: Shell execution configuration.
        brave_api_key: Optional Brave API key for web search.
        restrict_to_workspace: Whether to restrict file access to workspace.

    Returns:
        A ToolRegistry with filesystem, shell, and web tools registered.
    """
    registry = ToolRegistry()
    allowed_dir = workspace if restrict_to_workspace else None

    # Filesystem tools
    registry.register(ReadFileTool(workspace=workspace, allowed_dir=allowed_dir))
    registry.register(WriteFileTool(workspace=workspace, allowed_dir=allowed_dir))
    registry.register(EditFileTool(workspace=workspace, allowed_dir=allowed_dir))
    registry.register(ListDirTool(workspace=workspace, allowed_dir=allowed_dir))

    # Shell tool
    registry.register(ExecTool(
        working_dir=str(workspace),
        timeout=exec_config.timeout,
        restrict_to_workspace=restrict_to_workspace,
    ))

    # Web tools
    registry.register(WebSearchTool(api_key=brave_api_key))
    registry.register(WebFetchTool())

    return registry
