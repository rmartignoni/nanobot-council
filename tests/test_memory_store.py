"""Tests for MemoryStore (agent/memory.py)."""

from pathlib import Path

from nanobot.agent.memory import MemoryStore


def _make_store(tmp_path: Path) -> MemoryStore:
    """Create a MemoryStore backed by a temp workspace."""
    ws = tmp_path / "workspace"
    ws.mkdir()
    return MemoryStore(ws)


# --- Tests ---


def test_read_write_long_term(tmp_path: Path) -> None:
    store = _make_store(tmp_path)
    store.write_long_term("User prefers dark mode.")
    assert store.read_long_term() == "User prefers dark mode."


def test_read_long_term_empty(tmp_path: Path) -> None:
    store = _make_store(tmp_path)
    assert store.read_long_term() == ""


def test_append_history(tmp_path: Path) -> None:
    store = _make_store(tmp_path)
    store.append_history("2024-01-01 Event A")
    store.append_history("2024-01-02 Event B")
    content = store.history_file.read_text(encoding="utf-8")
    assert "Event A" in content
    assert "Event B" in content
    # Each entry separated by double newline
    assert content.count("\n\n") >= 2


def test_get_memory_context_empty(tmp_path: Path) -> None:
    store = _make_store(tmp_path)
    ctx = store.get_memory_context()
    assert ctx == ""


def test_get_memory_context_with_data(tmp_path: Path) -> None:
    store = _make_store(tmp_path)
    store.write_long_term("Important fact.")
    ctx = store.get_memory_context()
    assert "Long-term Memory" in ctx
    assert "Important fact." in ctx
