"""Unit tests for all ToolAdapter implementations."""

from pathlib import Path

import pytest

from ai_sync.adapters.base import ToolAdapter
from ai_sync.adapters.claude_code import ClaudeCodeAdapter
from ai_sync.adapters.gemini import GeminiAdapter
from ai_sync.adapters.opencode import OpenCodeAdapter
from ai_sync.adapters.shared_skills import SharedSkillsAdapter


class TestToolAdapterABC:
    def test_cannot_instantiate_base(self) -> None:
        with pytest.raises(TypeError):
            ToolAdapter()  # type: ignore[abstract]


class TestClaudeCodeAdapter:
    def test_tool_id(self, tmp_path: Path) -> None:
        assert ClaudeCodeAdapter(home=tmp_path).tool_id == "claude-code"

    def test_get_base_dir(self, tmp_path: Path) -> None:
        assert ClaudeCodeAdapter(home=tmp_path).get_base_dir() == tmp_path / ".claude"

    def test_sync_items_required(self, tmp_path: Path) -> None:
        items = ClaudeCodeAdapter(home=tmp_path).get_sync_items()
        repo_paths = [i.repo_path for i in items]
        assert "settings.json" in repo_paths
        assert "CLAUDE.md" in repo_paths
        assert "hooks/" in repo_paths
        assert "skills/" in repo_paths

    def test_sync_items_optional(self, tmp_path: Path) -> None:
        items = ClaudeCodeAdapter(home=tmp_path).get_sync_items()
        optional = {i.repo_path for i in items if i.optional}
        assert "agents/" in optional
        assert "plugins/installed_plugins.json" in optional
        assert "keybindings.json" in optional

    def test_local_paths_under_base(self, tmp_path: Path) -> None:
        adapter = ClaudeCodeAdapter(home=tmp_path)
        base = adapter.get_base_dir()
        for item in adapter.get_sync_items():
            assert str(item.local_path).startswith(str(base))

    def test_is_subclass(self, tmp_path: Path) -> None:
        assert isinstance(ClaudeCodeAdapter(home=tmp_path), ToolAdapter)


class TestGeminiAdapter:
    def test_tool_id(self, tmp_path: Path) -> None:
        assert GeminiAdapter(home=tmp_path).tool_id == "gemini"

    def test_get_base_dir(self, tmp_path: Path) -> None:
        assert GeminiAdapter(home=tmp_path).get_base_dir() == tmp_path / ".gemini"

    def test_sync_items_required(self, tmp_path: Path) -> None:
        items = GeminiAdapter(home=tmp_path).get_sync_items()
        repo_paths = [i.repo_path for i in items]
        assert "settings.json" in repo_paths
        assert "GEMINI.md" in repo_paths

    def test_sync_items_optional(self, tmp_path: Path) -> None:
        items = GeminiAdapter(home=tmp_path).get_sync_items()
        optional = {i.repo_path for i in items if i.optional}
        assert "commands/" in optional
        assert "skills/" in optional
        assert "memory.md" in optional
        assert "policies/" in optional


class TestOpenCodeAdapter:
    def test_tool_id(self, tmp_path: Path) -> None:
        assert OpenCodeAdapter(home=tmp_path).tool_id == "opencode"

    def test_base_dir_xdg_when_no_home_config(self, tmp_path: Path) -> None:
        adapter = OpenCodeAdapter(home=tmp_path)
        assert adapter.get_base_dir() == tmp_path / ".config" / "opencode"

    def test_base_dir_home_when_home_config_exists(self, tmp_path: Path) -> None:
        (tmp_path / ".opencode.json").write_text("{}", encoding="utf-8")
        adapter = OpenCodeAdapter(home=tmp_path)
        assert adapter.get_base_dir() == tmp_path

    def test_all_items_optional(self, tmp_path: Path) -> None:
        items = OpenCodeAdapter(home=tmp_path).get_sync_items()
        assert all(i.optional for i in items)

    def test_sync_items_repo_paths(self, tmp_path: Path) -> None:
        items = OpenCodeAdapter(home=tmp_path).get_sync_items()
        repo_paths = {i.repo_path for i in items}
        assert ".opencode.json" in repo_paths
        assert "agents/" in repo_paths
        assert "commands/" in repo_paths
        assert "modes/" in repo_paths
        assert "skills/" in repo_paths
        assert "tools/" in repo_paths
        assert "themes/" in repo_paths


class TestSharedSkillsAdapter:
    def test_tool_id(self, tmp_path: Path) -> None:
        assert SharedSkillsAdapter(home=tmp_path).tool_id == "shared"

    def test_get_base_dir(self, tmp_path: Path) -> None:
        assert SharedSkillsAdapter(home=tmp_path).get_base_dir() == tmp_path

    def test_sync_items(self, tmp_path: Path) -> None:
        items = SharedSkillsAdapter(home=tmp_path).get_sync_items()
        repo_paths = {i.repo_path for i in items}
        assert "skills/" in repo_paths
        assert "agents/skills/" in repo_paths

    def test_all_items_optional(self, tmp_path: Path) -> None:
        items = SharedSkillsAdapter(home=tmp_path).get_sync_items()
        assert all(i.optional for i in items)

    def test_local_paths(self, tmp_path: Path) -> None:
        items = SharedSkillsAdapter(home=tmp_path).get_sync_items()
        local_paths = {i.local_path for i in items}
        assert tmp_path / ".skills" in local_paths
        assert tmp_path / ".agents" / "skills" in local_paths
