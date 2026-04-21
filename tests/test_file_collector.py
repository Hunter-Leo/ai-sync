"""Unit tests for ai_sync.file_collector."""

import os
from pathlib import Path
from unittest.mock import patch

import pytest

from ai_sync.adapters.claude_code import ClaudeCodeAdapter
from ai_sync.adapters.shared_skills import SharedSkillsAdapter
from ai_sync.file_collector import FileCollector
from ai_sync.models import Platform, SyncItem
from ai_sync.path_mapper import PathMapper


@pytest.fixture
def mapper(tmp_path: Path) -> PathMapper:
    return PathMapper(platform=Platform.DARWIN, home=tmp_path)


@pytest.fixture
def collector(mapper: PathMapper) -> FileCollector:
    return FileCollector(mapper=mapper)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_claude_dir(base: Path) -> Path:
    """Create a minimal ~/.claude structure under base."""
    claude = base / ".claude"
    claude.mkdir()
    (claude / "settings.json").write_text('{"model": "opus"}', encoding="utf-8")
    (claude / "CLAUDE.md").write_text("# Global", encoding="utf-8")
    hooks = claude / "hooks"
    hooks.mkdir()
    (hooks / "pre.mjs").write_text("// hook", encoding="utf-8")
    skills = claude / "skills"
    skills.mkdir()
    (skills / "foo.md").write_text("# Skill", encoding="utf-8")
    return claude


# ---------------------------------------------------------------------------
# Basic collection
# ---------------------------------------------------------------------------

class TestCollectFiles:
    def test_collects_text_files(self, tmp_path: Path, collector: FileCollector) -> None:
        make_claude_dir(tmp_path)
        adapter = ClaudeCodeAdapter(home=tmp_path)
        files = collector.collect(adapter)
        repo_paths = {f.repo_path for f in files}
        assert "claude-code/settings.json" in repo_paths
        assert "claude-code/CLAUDE.md" in repo_paths

    def test_collects_directory_recursively(self, tmp_path: Path, collector: FileCollector) -> None:
        make_claude_dir(tmp_path)
        adapter = ClaudeCodeAdapter(home=tmp_path)
        files = collector.collect(adapter)
        repo_paths = {f.repo_path for f in files}
        assert "claude-code/hooks/pre.mjs" in repo_paths
        assert "claude-code/skills/foo.md" in repo_paths

    def test_path_abstraction_applied(self, tmp_path: Path, mapper: PathMapper) -> None:
        claude = make_claude_dir(tmp_path)
        # Write a settings.json that contains the real home path.
        (claude / "settings.json").write_text(
            f'{{"hooks": "{tmp_path}/.claude/hooks"}}', encoding="utf-8"
        )
        collector = FileCollector(mapper=mapper)
        adapter = ClaudeCodeAdapter(home=tmp_path)
        files = collector.collect(adapter)
        settings = next(f for f in files if f.repo_path == "claude-code/settings.json")
        content = settings.content.decode("utf-8")
        assert "{{CLAUDE_HOME}}" in content
        assert str(tmp_path) not in content

    def test_binary_file_not_abstracted(self, tmp_path: Path, collector: FileCollector) -> None:
        claude = tmp_path / ".claude"
        claude.mkdir()
        (claude / "settings.json").write_text("{}", encoding="utf-8")
        (claude / "CLAUDE.md").write_text("# x", encoding="utf-8")
        hooks = claude / "hooks"
        hooks.mkdir()
        skills = claude / "skills"
        skills.mkdir()
        binary = skills / "icon.png"
        binary.write_bytes(b"\x89PNG\r\n\x1a\n")
        adapter = ClaudeCodeAdapter(home=tmp_path)
        files = collector.collect(adapter)
        png = next(f for f in files if f.repo_path.endswith("icon.png"))
        assert png.is_binary is True
        assert png.content == b"\x89PNG\r\n\x1a\n"


# ---------------------------------------------------------------------------
# Optional items
# ---------------------------------------------------------------------------

class TestOptionalItems:
    def test_optional_missing_skipped(self, tmp_path: Path, collector: FileCollector) -> None:
        """SharedSkillsAdapter items are optional — missing dirs should be skipped."""
        adapter = SharedSkillsAdapter(home=tmp_path)
        files = collector.collect(adapter)
        assert files == []

    def test_optional_present_collected(self, tmp_path: Path, collector: FileCollector) -> None:
        skills = tmp_path / ".skills"
        skills.mkdir()
        (skills / "my_skill.md").write_text("# Skill", encoding="utf-8")
        adapter = SharedSkillsAdapter(home=tmp_path)
        files = collector.collect(adapter)
        repo_paths = {f.repo_path for f in files}
        assert "shared/skills/my_skill.md" in repo_paths


# ---------------------------------------------------------------------------
# Symlink handling
# ---------------------------------------------------------------------------

class TestSymlinks:
    def test_symlink_resolved_to_content(self, tmp_path: Path, collector: FileCollector) -> None:
        real = tmp_path / "real_settings.json"
        real.write_text('{"model": "opus"}', encoding="utf-8")
        claude = tmp_path / ".claude"
        claude.mkdir()
        link = claude / "settings.json"
        link.symlink_to(real)
        (claude / "CLAUDE.md").write_text("# x", encoding="utf-8")
        hooks = claude / "hooks"
        hooks.mkdir()
        skills = claude / "skills"
        skills.mkdir()
        adapter = ClaudeCodeAdapter(home=tmp_path)
        files = collector.collect(adapter)
        settings = next(f for f in files if f.repo_path == "claude-code/settings.json")
        assert b'"model"' in settings.content

    def test_dangling_symlink_skipped_with_warning(
        self, tmp_path: Path, collector: FileCollector, capsys
    ) -> None:
        claude = tmp_path / ".claude"
        claude.mkdir()
        link = claude / "settings.json"
        link.symlink_to(tmp_path / "nonexistent.json")
        (claude / "CLAUDE.md").write_text("# x", encoding="utf-8")
        hooks = claude / "hooks"
        hooks.mkdir()
        skills = claude / "skills"
        skills.mkdir()
        adapter = ClaudeCodeAdapter(home=tmp_path)
        # Should not raise; dangling link is skipped.
        files = collector.collect(adapter)
        repo_paths = {f.repo_path for f in files}
        assert "claude-code/settings.json" not in repo_paths

    def test_directory_symlink_content_collected(self, tmp_path: Path, collector: FileCollector) -> None:
        real_dir = tmp_path / "real_hooks"
        real_dir.mkdir()
        (real_dir / "pre.mjs").write_text("// hook", encoding="utf-8")
        claude = tmp_path / ".claude"
        claude.mkdir()
        (claude / "settings.json").write_text("{}", encoding="utf-8")
        (claude / "CLAUDE.md").write_text("# x", encoding="utf-8")
        link = claude / "hooks"
        link.symlink_to(real_dir)
        skills = claude / "skills"
        skills.mkdir()
        adapter = ClaudeCodeAdapter(home=tmp_path)
        files = collector.collect(adapter)
        repo_paths = {f.repo_path for f in files}
        assert "claude-code/hooks/pre.mjs" in repo_paths

    def test_symlink_to_dir_inside_dir_skipped_silently(
        self, tmp_path: Path, collector: FileCollector
    ) -> None:
        """Symlink inside a collected dir that resolves to a directory must be skipped.

        Reproduces the real-world case where ~/.agents/skills/ contains
        subdirectories that are symlinks pointing to other directories.
        Without the is_file() guard, _collect_file receives a directory path
        and raises EISDIR.
        """
        agents_skills = tmp_path / ".agents" / "skills"
        agents_skills.mkdir(parents=True)

        # A real skill directory (should be collected).
        real_skill = agents_skills / "my-skill"
        real_skill.mkdir()
        (real_skill / "README.md").write_text("# skill", encoding="utf-8")

        # A symlink inside agents/skills pointing to another directory.
        target_dir = tmp_path / "external-plugin"
        target_dir.mkdir()
        (target_dir / "plugin.json").write_text("{}", encoding="utf-8")
        link = agents_skills / "linked-plugin"
        link.symlink_to(target_dir)

        adapter = SharedSkillsAdapter(home=tmp_path)
        # Must not raise; symlink-to-dir entry is silently skipped.
        files = collector.collect(adapter)
        repo_paths = {f.repo_path for f in files}

        # The real file inside the real skill dir is collected.
        assert "shared/agents/skills/my-skill/README.md" in repo_paths
        # The symlink-to-dir itself is not collected (no EISDIR error).
        assert not any("linked-plugin" in p for p in repo_paths)


# ---------------------------------------------------------------------------
# Exclude patterns
# ---------------------------------------------------------------------------

class TestExcludePatterns:
    def test_excluded_dir_skipped(self, tmp_path: Path, collector: FileCollector) -> None:
        claude = make_claude_dir(tmp_path)
        cache = claude / "cache"
        cache.mkdir()
        (cache / "cached.json").write_text("{}", encoding="utf-8")
        adapter = ClaudeCodeAdapter(home=tmp_path)
        files = collector.collect(adapter)
        repo_paths = {f.repo_path for f in files}
        assert not any("cache" in p for p in repo_paths)

    def test_excluded_file_skipped(self, tmp_path: Path, collector: FileCollector) -> None:
        claude = make_claude_dir(tmp_path)
        (claude / "history.jsonl").write_text("{}", encoding="utf-8")
        adapter = ClaudeCodeAdapter(home=tmp_path)
        files = collector.collect(adapter)
        repo_paths = {f.repo_path for f in files}
        assert not any("history.jsonl" in p for p in repo_paths)


# ---------------------------------------------------------------------------
# Path concatenation robustness (F-004)
# ---------------------------------------------------------------------------

class TestPathConcatenation:
    def test_repo_path_correct_with_trailing_slash(self, tmp_path: Path, collector: FileCollector) -> None:
        """SyncItem.repo_path with trailing slash must produce correct repo_path."""
        make_claude_dir(tmp_path)
        adapter = ClaudeCodeAdapter(home=tmp_path)
        files = collector.collect(adapter)
        repo_paths = {f.repo_path for f in files}
        # hooks/ has trailing slash — must produce "claude-code/hooks/pre.mjs", not "claude-code/hookspre.mjs"
        assert "claude-code/hooks/pre.mjs" in repo_paths
        assert not any("hookspre" in p for p in repo_paths)

    def test_repo_path_correct_without_trailing_slash(self, tmp_path: Path, mapper: PathMapper) -> None:
        """SyncItem.repo_path without trailing slash must still produce correct repo_path."""
        from ai_sync.adapters.base import ToolAdapter
        from ai_sync.models import SyncItem

        class _TestAdapter(ToolAdapter):
            @property
            def tool_id(self) -> str:
                return "test-tool"

            def get_base_dir(self) -> Path:
                return tmp_path / ".test"

            def get_sync_items(self) -> list[SyncItem]:
                base = self.get_base_dir()
                base.mkdir(exist_ok=True)
                sub = base / "sub"
                sub.mkdir(exist_ok=True)
                (sub / "file.json").write_text("{}", encoding="utf-8")
                # repo_path WITHOUT trailing slash
                return [SyncItem(local_path=sub, repo_path="sub", is_dir=True)]

        collector = FileCollector(mapper=mapper)
        files = collector.collect(_TestAdapter())
        repo_paths = {f.repo_path for f in files}
        # Must be "test-tool/sub/file.json", not "test-tool/subfile.json"
        assert "test-tool/sub/file.json" in repo_paths
        assert not any("subfile" in p for p in repo_paths)
