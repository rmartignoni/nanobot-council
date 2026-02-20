"""Tests for filesystem tools: read, write, edit, list_dir and _resolve_path."""

import pytest
from pathlib import Path

from nanobot.agent.tools.filesystem import (
    ReadFileTool,
    WriteFileTool,
    EditFileTool,
    ListDirTool,
    _resolve_path,
)


# --- _resolve_path ---


class TestResolvePath:
    def test_within_allowed_dir(self, tmp_path: Path) -> None:
        result = _resolve_path("sub/file.txt", workspace=tmp_path, allowed_dir=tmp_path)
        assert result == (tmp_path / "sub" / "file.txt").resolve()

    def test_outside_allowed_dir_blocked(self, tmp_path: Path) -> None:
        with pytest.raises(PermissionError):
            _resolve_path("../../../etc/passwd", workspace=tmp_path, allowed_dir=tmp_path)

    def test_prefix_attack_blocked(self, tmp_path: Path) -> None:
        """Ensure /home/user cannot access /home/usermalicious."""
        allowed = tmp_path / "user"
        allowed.mkdir()
        malicious = tmp_path / "usermalicious"
        malicious.mkdir()
        target = malicious / "secret.txt"
        target.write_text("secret")

        with pytest.raises(PermissionError):
            _resolve_path(str(target), allowed_dir=allowed)


# --- ReadFileTool ---


class TestReadFile:
    @pytest.mark.asyncio
    async def test_read_success(self, tmp_path: Path) -> None:
        f = tmp_path / "hello.txt"
        f.write_text("hello world")
        tool = ReadFileTool(workspace=tmp_path, allowed_dir=tmp_path)
        result = await tool.execute(path=str(f))
        assert result == "hello world"

    @pytest.mark.asyncio
    async def test_read_not_found(self, tmp_path: Path) -> None:
        tool = ReadFileTool(workspace=tmp_path, allowed_dir=tmp_path)
        result = await tool.execute(path=str(tmp_path / "nope.txt"))
        assert "Error" in result


# --- WriteFileTool ---


class TestWriteFile:
    @pytest.mark.asyncio
    async def test_creates_parent_dirs(self, tmp_path: Path) -> None:
        tool = WriteFileTool(workspace=tmp_path, allowed_dir=tmp_path)
        target = tmp_path / "a" / "b" / "c" / "file.txt"
        result = await tool.execute(path=str(target), content="nested")
        assert "Successfully" in result
        assert target.parent.exists()

    @pytest.mark.asyncio
    async def test_content_written(self, tmp_path: Path) -> None:
        tool = WriteFileTool(workspace=tmp_path, allowed_dir=tmp_path)
        target = tmp_path / "out.txt"
        await tool.execute(path=str(target), content="expected content")
        assert target.read_text() == "expected content"


# --- EditFileTool ---


class TestEditFile:
    @pytest.mark.asyncio
    async def test_replaces_text(self, tmp_path: Path) -> None:
        f = tmp_path / "code.py"
        f.write_text("def foo():\n    return 1\n")
        tool = EditFileTool(workspace=tmp_path, allowed_dir=tmp_path)
        result = await tool.execute(path=str(f), old_text="return 1", new_text="return 42")
        assert "Successfully" in result
        assert "return 42" in f.read_text()

    @pytest.mark.asyncio
    async def test_no_match_returns_error(self, tmp_path: Path) -> None:
        f = tmp_path / "code.py"
        f.write_text("def foo():\n    return 1\n")
        tool = EditFileTool(workspace=tmp_path, allowed_dir=tmp_path)
        result = await tool.execute(path=str(f), old_text="nonexistent", new_text="x")
        assert "Error" in result


# --- ListDirTool ---


class TestListDir:
    @pytest.mark.asyncio
    async def test_lists_files_and_dirs(self, tmp_path: Path) -> None:
        (tmp_path / "file.txt").write_text("x")
        (tmp_path / "subdir").mkdir()
        tool = ListDirTool(workspace=tmp_path, allowed_dir=tmp_path)
        result = await tool.execute(path=str(tmp_path))
        assert "file.txt" in result
        assert "subdir" in result
