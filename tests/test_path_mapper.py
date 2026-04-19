"""Unit tests for ai_sync.path_mapper."""

from pathlib import Path

import pytest

from ai_sync.models import Platform
from ai_sync.path_mapper import PathMapper


@pytest.fixture
def mac_mapper(tmp_path: Path) -> PathMapper:
    return PathMapper(platform=Platform.DARWIN, home=tmp_path)


@pytest.fixture
def linux_mapper(tmp_path: Path) -> PathMapper:
    return PathMapper(platform=Platform.LINUX, home=tmp_path)


@pytest.fixture
def win_mapper(tmp_path: Path) -> PathMapper:
    # Simulate a Windows home like C:\Users\alice
    home = Path("C:/Users/alice")
    return PathMapper(platform=Platform.WINDOWS, home=home)


class TestGetPlaceholders:
    def test_contains_all_keys(self, mac_mapper: PathMapper) -> None:
        keys = set(mac_mapper.get_placeholders().keys())
        assert "{{HOME}}" in keys
        assert "{{CLAUDE_HOME}}" in keys
        assert "{{GEMINI_HOME}}" in keys
        assert "{{OPENCODE_HOME}}" in keys
        assert "{{SKILLS_HOME}}" in keys
        assert "{{AGENTS_HOME}}" in keys

    def test_longest_first_ordering(self, mac_mapper: PathMapper) -> None:
        """Longer real paths must appear before shorter ones."""
        items = list(mac_mapper.get_placeholders().items())
        lengths = [len(v) for _, v in items]
        assert lengths == sorted(lengths, reverse=True)


class TestAbstractPaths:
    def test_replaces_claude_home(self, mac_mapper: PathMapper, tmp_path: Path) -> None:
        content = f'{{"hooks": "{tmp_path}/.claude/hooks/pre.mjs"}}'
        result = mac_mapper.abstract_paths(content)
        assert "{{CLAUDE_HOME}}" in result
        assert str(tmp_path) not in result

    def test_replaces_home(self, mac_mapper: PathMapper, tmp_path: Path) -> None:
        content = f"path: {tmp_path}/some/file"
        result = mac_mapper.abstract_paths(content)
        assert "{{HOME}}" in result
        assert str(tmp_path) not in result

    def test_no_partial_replacement(self, mac_mapper: PathMapper, tmp_path: Path) -> None:
        """~/.claude must become {{CLAUDE_HOME}}, not {{HOME}}/.claude."""
        content = f"{tmp_path}/.claude/settings.json"
        result = mac_mapper.abstract_paths(content)
        assert result == "{{CLAUDE_HOME}}/settings.json"
        assert "{{HOME}}/.claude" not in result

    def test_unknown_path_unchanged(self, mac_mapper: PathMapper) -> None:
        content = "/some/unknown/path"
        assert mac_mapper.abstract_paths(content) == content

    def test_windows_forward_slash(self, win_mapper: PathMapper) -> None:
        """Windows paths written with / should also be abstracted."""
        content = "C:/Users/alice/.gemini/settings.json"
        result = win_mapper.abstract_paths(content)
        assert "{{GEMINI_HOME}}" in result

    def test_multiple_placeholders(self, mac_mapper: PathMapper, tmp_path: Path) -> None:
        content = f"{tmp_path}/.claude/hooks and {tmp_path}/.skills/foo"
        result = mac_mapper.abstract_paths(content)
        assert "{{CLAUDE_HOME}}" in result
        assert "{{SKILLS_HOME}}" in result
        assert str(tmp_path) not in result


class TestRestorePaths:
    def test_restores_claude_home(self, mac_mapper: PathMapper, tmp_path: Path) -> None:
        content = '{"hooks": "{{CLAUDE_HOME}}/hooks/pre.mjs"}'
        result = mac_mapper.restore_paths(content)
        assert str(tmp_path) in result
        assert "{{CLAUDE_HOME}}" not in result

    def test_unknown_placeholder_unchanged(self, mac_mapper: PathMapper) -> None:
        content = "{{UNKNOWN_PLACEHOLDER}}/file"
        assert mac_mapper.restore_paths(content) == content


class TestRoundtrip:
    def test_abstract_then_restore(self, mac_mapper: PathMapper, tmp_path: Path) -> None:
        original = f'{{"mcp": "{tmp_path}/.claude/settings.json", "skills": "{tmp_path}/.skills/foo.md"}}'
        abstracted = mac_mapper.abstract_paths(original)
        restored = mac_mapper.restore_paths(abstracted)
        assert restored == original

    def test_linux_roundtrip(self, linux_mapper: PathMapper, tmp_path: Path) -> None:
        original = f"export PATH={tmp_path}/.agents/bin:$PATH"
        assert linux_mapper.restore_paths(linux_mapper.abstract_paths(original)) == original


class TestIsTextFile:
    def test_text_file(self, tmp_path: Path) -> None:
        f = tmp_path / "settings.json"
        f.write_text('{"model": "opus"}', encoding="utf-8")
        mapper = PathMapper(Platform.DARWIN, tmp_path)
        assert mapper.is_text_file(f) is True

    def test_binary_file(self, tmp_path: Path) -> None:
        f = tmp_path / "icon.png"
        f.write_bytes(b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR")
        mapper = PathMapper(Platform.DARWIN, tmp_path)
        assert mapper.is_text_file(f) is False

    def test_empty_file_is_text(self, tmp_path: Path) -> None:
        f = tmp_path / "empty.md"
        f.write_bytes(b"")
        mapper = PathMapper(Platform.DARWIN, tmp_path)
        assert mapper.is_text_file(f) is True

    def test_file_with_null_byte_is_binary(self, tmp_path: Path) -> None:
        """A file containing a null byte must be treated as binary even if otherwise valid UTF-8."""
        f = tmp_path / "tricky.bin"
        f.write_bytes(b"looks like text\x00but has null byte")
        mapper = PathMapper(Platform.DARWIN, tmp_path)
        assert mapper.is_text_file(f) is False

    def test_utf8_without_null_is_text(self, tmp_path: Path) -> None:
        f = tmp_path / "unicode.md"
        f.write_text("# 你好世界\nsome content", encoding="utf-8")
        mapper = PathMapper(Platform.DARWIN, tmp_path)
        assert mapper.is_text_file(f) is True
