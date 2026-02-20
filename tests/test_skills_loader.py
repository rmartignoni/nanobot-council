"""Tests for SkillsLoader (agent/skills.py)."""

from pathlib import Path

from nanobot.agent.skills import SkillsLoader, BUILTIN_SKILLS_DIR


def _make_workspace_with_skills(tmp_path: Path) -> Path:
    """Create workspace with two custom skills."""
    ws = tmp_path / "workspace"
    ws.mkdir()

    # Skill with always=true
    s1 = ws / "skills" / "always_skill"
    s1.mkdir(parents=True)
    (s1 / "SKILL.md").write_text(
        "---\nname: always_skill\ndescription: Always loaded\nalways: true\n"
        'metadata: {"nanobot": {"always": true}}\n'
        "---\n\nAlways skill body content.\n",
        encoding="utf-8",
    )

    # Skill without always (defaults to not-always)
    s2 = ws / "skills" / "optional_skill"
    s2.mkdir(parents=True)
    (s2 / "SKILL.md").write_text(
        "---\nname: optional_skill\ndescription: On-demand skill\n"
        'metadata: {"nanobot": {}}\n'
        "---\n\nOptional skill body.\n",
        encoding="utf-8",
    )
    return ws


# --- Tests ---


def test_list_skills_finds_builtins() -> None:
    """Built-in skills directory contains discoverable skills."""
    loader = SkillsLoader(Path("/nonexistent"))
    skills = loader.list_skills(filter_unavailable=False)
    names = [s["name"] for s in skills]
    assert "memory" in names


def test_load_skill_returns_content() -> None:
    """Loading a known builtin skill returns its SKILL.md content."""
    loader = SkillsLoader(Path("/nonexistent"))
    content = loader.load_skill("memory")
    assert content is not None
    assert "MEMORY.md" in content


def test_load_skill_not_found() -> None:
    """Loading a non-existent skill returns None."""
    loader = SkillsLoader(Path("/nonexistent"), builtin_skills_dir=Path("/also_nonexistent"))
    result = loader.load_skill("does_not_exist_xyz")
    assert result is None


def test_strip_frontmatter() -> None:
    """YAML frontmatter is removed from content."""
    loader = SkillsLoader(Path("/nonexistent"))
    raw = "---\nname: test\ndescription: A test\n---\n\nBody content here."
    stripped = loader._strip_frontmatter(raw)
    assert stripped == "Body content here."
    assert "---" not in stripped


def test_strip_frontmatter_no_frontmatter() -> None:
    """Content without frontmatter is returned unchanged."""
    loader = SkillsLoader(Path("/nonexistent"))
    raw = "Just plain content."
    assert loader._strip_frontmatter(raw) == raw


def test_get_always_skills(tmp_path: Path) -> None:
    """Skills with always=true are returned."""
    ws = _make_workspace_with_skills(tmp_path)
    loader = SkillsLoader(ws, builtin_skills_dir=Path("/nonexistent"))
    always = loader.get_always_skills()
    assert "always_skill" in always
    assert "optional_skill" not in always


def test_build_skills_summary(tmp_path: Path) -> None:
    """Summary includes skill names and descriptions in XML format."""
    ws = _make_workspace_with_skills(tmp_path)
    loader = SkillsLoader(ws, builtin_skills_dir=Path("/nonexistent"))
    summary = loader.build_skills_summary()
    assert "<skills>" in summary
    assert "always_skill" in summary
    assert "optional_skill" in summary
    assert "Always loaded" in summary
    assert "On-demand skill" in summary
