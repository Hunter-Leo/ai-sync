"""Unit tests for ai_sync.sync_engine."""

from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from ai_sync.adapters.claude_code import ClaudeCodeAdapter
from ai_sync.file_collector import FileCollector
from ai_sync.manifest import ManifestManager
from ai_sync.models import CollectedFile, Manifest, Platform, PullResult, PushResult
from ai_sync.path_mapper import PathMapper
from ai_sync.sync_engine import SyncEngine


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def home(tmp_path: Path) -> Path:
    return tmp_path / "home"


@pytest.fixture
def repo_dir(tmp_path: Path) -> Path:
    d = tmp_path / "repo"
    d.mkdir()
    return d


@pytest.fixture
def mapper(home: Path) -> PathMapper:
    return PathMapper(platform=Platform.DARWIN, home=home)


@pytest.fixture
def mock_repo() -> MagicMock:
    r = MagicMock()
    r.push.return_value = True
    return r


@pytest.fixture
def mock_collector() -> MagicMock:
    return MagicMock()


@pytest.fixture
def mock_manifest_mgr() -> MagicMock:
    return MagicMock()


@pytest.fixture
def adapter(home: Path) -> ClaudeCodeAdapter:
    return ClaudeCodeAdapter(home=home)


def make_engine(
    adapters,
    repo,
    mapper,
    collector,
    manifest_mgr,
    repo_dir,
) -> SyncEngine:
    return SyncEngine(
        adapters=adapters,
        repo=repo,
        mapper=mapper,
        collector=collector,
        manifest_mgr=manifest_mgr,
        repo_dir=repo_dir,
    )


# ---------------------------------------------------------------------------
# push()
# ---------------------------------------------------------------------------

class TestPush:
    def test_writes_files_to_repo_dir(
        self,
        adapter: ClaudeCodeAdapter,
        mock_repo: MagicMock,
        mapper: PathMapper,
        mock_manifest_mgr: MagicMock,
        repo_dir: Path,
    ) -> None:
        collector = MagicMock()
        collector.collect.return_value = [
            CollectedFile(
                repo_path="claude-code/settings.json",
                content=b'{"model":"opus"}',
            )
        ]
        engine = make_engine([adapter], mock_repo, mapper, collector, mock_manifest_mgr, repo_dir)
        result = engine.push()

        assert (repo_dir / "claude-code" / "settings.json").is_file()
        assert result.file_count == 1
        assert "claude-code" in result.tools

    def test_writes_manifest(
        self,
        adapter: ClaudeCodeAdapter,
        mock_repo: MagicMock,
        mapper: PathMapper,
        mock_manifest_mgr: MagicMock,
        repo_dir: Path,
    ) -> None:
        collector = MagicMock()
        collector.collect.return_value = [
            CollectedFile(repo_path="claude-code/settings.json", content=b"{}")
        ]
        engine = make_engine([adapter], mock_repo, mapper, collector, mock_manifest_mgr, repo_dir)
        engine.push()

        mock_manifest_mgr.write.assert_called_once()
        manifest: Manifest = mock_manifest_mgr.write.call_args[0][0]
        assert "claude-code" in manifest.tools

    def test_committed_true_when_changes(
        self,
        adapter: ClaudeCodeAdapter,
        mapper: PathMapper,
        mock_manifest_mgr: MagicMock,
        repo_dir: Path,
    ) -> None:
        mock_repo = MagicMock()
        mock_repo.push.return_value = True
        collector = MagicMock()
        collector.collect.return_value = [
            CollectedFile(repo_path="claude-code/settings.json", content=b"{}")
        ]
        engine = make_engine([adapter], mock_repo, mapper, collector, mock_manifest_mgr, repo_dir)
        result = engine.push()
        assert result.committed is True

    def test_committed_false_when_no_changes(
        self,
        adapter: ClaudeCodeAdapter,
        mapper: PathMapper,
        mock_manifest_mgr: MagicMock,
        repo_dir: Path,
    ) -> None:
        mock_repo = MagicMock()
        mock_repo.push.return_value = False
        collector = MagicMock()
        collector.collect.return_value = []
        engine = make_engine([adapter], mock_repo, mapper, collector, mock_manifest_mgr, repo_dir)
        result = engine.push()
        assert result.committed is False

    def test_multiple_adapters_no_overlap(
        self,
        home: Path,
        mock_repo: MagicMock,
        mapper: PathMapper,
        mock_manifest_mgr: MagicMock,
        repo_dir: Path,
    ) -> None:
        from ai_sync.adapters.gemini import GeminiAdapter
        adapters = [ClaudeCodeAdapter(home=home), GeminiAdapter(home=home)]
        collector = MagicMock()
        collector.collect.side_effect = [
            [CollectedFile(repo_path="claude-code/settings.json", content=b"{}")],
            [CollectedFile(repo_path="gemini/settings.json", content=b"{}")],
        ]
        engine = make_engine(adapters, mock_repo, mapper, collector, mock_manifest_mgr, repo_dir)
        result = engine.push()
        assert result.file_count == 2
        assert (repo_dir / "claude-code" / "settings.json").is_file()
        assert (repo_dir / "gemini" / "settings.json").is_file()


# ---------------------------------------------------------------------------
# pull()
# ---------------------------------------------------------------------------

class TestPull:
    def test_calls_git_pull(
        self,
        adapter: ClaudeCodeAdapter,
        mock_repo: MagicMock,
        mapper: PathMapper,
        mock_manifest_mgr: MagicMock,
        repo_dir: Path,
    ) -> None:
        engine = make_engine([adapter], mock_repo, mapper, MagicMock(), mock_manifest_mgr, repo_dir)
        engine.pull()
        mock_repo.pull.assert_called_once()

    def test_writes_files_to_local_dir(
        self,
        adapter: ClaudeCodeAdapter,
        mock_repo: MagicMock,
        mapper: PathMapper,
        mock_manifest_mgr: MagicMock,
        repo_dir: Path,
        home: Path,
    ) -> None:
        # Seed the repo_dir with a file.
        (repo_dir / "claude-code").mkdir()
        (repo_dir / "claude-code" / "settings.json").write_text(
            '{"model":"opus"}', encoding="utf-8"
        )
        engine = make_engine([adapter], mock_repo, mapper, MagicMock(), mock_manifest_mgr, repo_dir)
        engine.pull()

        local = home / ".claude" / "settings.json"
        assert local.is_file()
        assert "opus" in local.read_text()

    def test_skips_manifest_file(
        self,
        adapter: ClaudeCodeAdapter,
        mock_repo: MagicMock,
        mapper: PathMapper,
        mock_manifest_mgr: MagicMock,
        repo_dir: Path,
        home: Path,
    ) -> None:
        (repo_dir / "_manifest.json").write_text('{"version":"1.0"}', encoding="utf-8")
        engine = make_engine([adapter], mock_repo, mapper, MagicMock(), mock_manifest_mgr, repo_dir)
        engine.pull()
        # _manifest.json must not be written to the local config dir.
        assert not (home / ".claude" / "_manifest.json").exists()

    def test_restores_paths_in_text_files(
        self,
        adapter: ClaudeCodeAdapter,
        mock_repo: MagicMock,
        mapper: PathMapper,
        mock_manifest_mgr: MagicMock,
        repo_dir: Path,
        home: Path,
    ) -> None:
        (repo_dir / "claude-code").mkdir()
        (repo_dir / "claude-code" / "settings.json").write_text(
            '{"hooks":"{{CLAUDE_HOME}}/hooks"}', encoding="utf-8"
        )
        engine = make_engine([adapter], mock_repo, mapper, MagicMock(), mock_manifest_mgr, repo_dir)
        engine.pull()

        content = (home / ".claude" / "settings.json").read_text()
        assert "{{CLAUDE_HOME}}" not in content
        assert str(home / ".claude") in content

    def test_returns_pull_result(
        self,
        adapter: ClaudeCodeAdapter,
        mock_repo: MagicMock,
        mapper: PathMapper,
        mock_manifest_mgr: MagicMock,
        repo_dir: Path,
    ) -> None:
        (repo_dir / "claude-code").mkdir()
        (repo_dir / "claude-code" / "settings.json").write_text("{}", encoding="utf-8")
        engine = make_engine([adapter], mock_repo, mapper, MagicMock(), mock_manifest_mgr, repo_dir)
        result = engine.pull()
        assert isinstance(result, PullResult)
        assert result.file_count == 1
        assert "claude-code" in result.tools


# ---------------------------------------------------------------------------
# status()
# ---------------------------------------------------------------------------

class TestStatus:
    def test_empty_when_both_empty(
        self,
        adapter: ClaudeCodeAdapter,
        mock_repo: MagicMock,
        mapper: PathMapper,
        mock_manifest_mgr: MagicMock,
        repo_dir: Path,
    ) -> None:
        collector = MagicMock()
        collector.collect.return_value = []
        engine = make_engine([adapter], mock_repo, mapper, collector, mock_manifest_mgr, repo_dir)
        assert engine.status() == []

    def test_added_when_only_local(
        self,
        adapter: ClaudeCodeAdapter,
        mock_repo: MagicMock,
        mapper: PathMapper,
        mock_manifest_mgr: MagicMock,
        repo_dir: Path,
    ) -> None:
        collector = MagicMock()
        collector.collect.return_value = [
            CollectedFile(repo_path="claude-code/settings.json", content=b"{}")
        ]
        engine = make_engine([adapter], mock_repo, mapper, collector, mock_manifest_mgr, repo_dir)
        entries = engine.status()
        assert len(entries) == 1
        assert entries[0].state == "added"
        assert entries[0].path == "claude-code/settings.json"

    def test_deleted_when_only_in_repo(
        self,
        adapter: ClaudeCodeAdapter,
        mock_repo: MagicMock,
        mapper: PathMapper,
        mock_manifest_mgr: MagicMock,
        repo_dir: Path,
    ) -> None:
        (repo_dir / "claude-code").mkdir()
        (repo_dir / "claude-code" / "old.json").write_bytes(b"{}")
        collector = MagicMock()
        collector.collect.return_value = []
        engine = make_engine([adapter], mock_repo, mapper, collector, mock_manifest_mgr, repo_dir)
        entries = engine.status()
        assert any(e.state == "deleted" for e in entries)

    def test_modified_when_content_differs(
        self,
        adapter: ClaudeCodeAdapter,
        mock_repo: MagicMock,
        mapper: PathMapper,
        mock_manifest_mgr: MagicMock,
        repo_dir: Path,
    ) -> None:
        (repo_dir / "claude-code").mkdir()
        (repo_dir / "claude-code" / "settings.json").write_bytes(b'{"old":true}')
        collector = MagicMock()
        collector.collect.return_value = [
            CollectedFile(repo_path="claude-code/settings.json", content=b'{"new":true}')
        ]
        engine = make_engine([adapter], mock_repo, mapper, collector, mock_manifest_mgr, repo_dir)
        entries = engine.status()
        assert entries[0].state == "modified"

    def test_unchanged_when_content_same(
        self,
        adapter: ClaudeCodeAdapter,
        mock_repo: MagicMock,
        mapper: PathMapper,
        mock_manifest_mgr: MagicMock,
        repo_dir: Path,
    ) -> None:
        (repo_dir / "claude-code").mkdir()
        (repo_dir / "claude-code" / "settings.json").write_bytes(b'{"model":"opus"}')
        collector = MagicMock()
        collector.collect.return_value = [
            CollectedFile(repo_path="claude-code/settings.json", content=b'{"model":"opus"}')
        ]
        engine = make_engine([adapter], mock_repo, mapper, collector, mock_manifest_mgr, repo_dir)
        entries = engine.status()
        assert entries[0].state == "unchanged"
