"""Tests for ContextBuilder (agent/context.py)."""

from pathlib import Path

from nanobot.agent.context import ContextBuilder


def _make_workspace(tmp_path: Path) -> Path:
    """Create a minimal workspace with memory dir."""
    ws = tmp_path / "workspace"
    ws.mkdir()
    (ws / "memory").mkdir()
    return ws


def _make_workspace_with_skill(tmp_path: Path, *, always: bool = False) -> Path:
    """Create workspace with a custom skill."""
    ws = _make_workspace(tmp_path)
    skill_dir = ws / "skills" / "greet"
    skill_dir.mkdir(parents=True)
    always_line = "always: true" if always else "always: false"
    (skill_dir / "SKILL.md").write_text(
        f"---\nname: greet\ndescription: Say hello\n{always_line}\n"
        f'metadata: {{"nanobot": {{"always": {"true" if always else "false"}}}}}\n'
        "---\n\nGreet the user warmly.\n",
        encoding="utf-8",
    )
    return ws


# --- Tests ---


def test_build_system_prompt_includes_identity(tmp_path: Path) -> None:
    ws = _make_workspace(tmp_path)
    cb = ContextBuilder(ws)
    prompt = cb.build_system_prompt()
    assert "nanobot" in prompt
    assert "workspace" in prompt.lower()


def test_build_system_prompt_includes_skills(tmp_path: Path) -> None:
    ws = _make_workspace_with_skill(tmp_path, always=True)
    cb = ContextBuilder(ws)
    prompt = cb.build_system_prompt()
    assert "Greet the user warmly" in prompt


def test_build_messages_with_history(tmp_path: Path) -> None:
    ws = _make_workspace(tmp_path)
    cb = ContextBuilder(ws)
    history = [
        {"role": "user", "content": "hi"},
        {"role": "assistant", "content": "hello"},
    ]
    msgs = cb.build_messages(history, "how are you?")
    # system + 2 history + current user
    assert len(msgs) == 4
    assert msgs[0]["role"] == "system"
    assert msgs[1] == {"role": "user", "content": "hi"}
    assert msgs[2] == {"role": "assistant", "content": "hello"}
    assert msgs[3]["role"] == "user"
    assert msgs[3]["content"] == "how are you?"


def test_build_messages_limits_window(tmp_path: Path) -> None:
    """History is passed as-is; the caller is responsible for trimming.

    ContextBuilder.build_messages does not truncate history itself — it
    relies on the caller passing a pre-trimmed list. So passing a short
    history should yield exactly those entries plus system + current.
    """
    ws = _make_workspace(tmp_path)
    cb = ContextBuilder(ws)
    history = [{"role": "user", "content": f"msg{i}"} for i in range(5)]
    msgs = cb.build_messages(history[:2], "latest")
    # system + 2 history + current
    assert len(msgs) == 4


def test_add_tool_result(tmp_path: Path) -> None:
    ws = _make_workspace(tmp_path)
    cb = ContextBuilder(ws)
    messages: list[dict] = []
    result = cb.add_tool_result(messages, "call_123", "read_file", "file content here")
    assert len(result) == 1
    entry = result[0]
    assert entry["role"] == "tool"
    assert entry["tool_call_id"] == "call_123"
    assert entry["name"] == "read_file"
    assert entry["content"] == "file content here"


def test_add_assistant_message(tmp_path: Path) -> None:
    ws = _make_workspace(tmp_path)
    cb = ContextBuilder(ws)
    messages: list[dict] = []
    tool_calls = [{"id": "tc1", "function": {"name": "read_file", "arguments": "{}"}}]
    result = cb.add_assistant_message(messages, "thinking...", tool_calls=tool_calls)
    assert len(result) == 1
    msg = result[0]
    assert msg["role"] == "assistant"
    assert msg["content"] == "thinking..."
    assert msg["tool_calls"] == tool_calls
