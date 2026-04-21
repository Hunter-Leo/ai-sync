"""Integration tests for ai_sync.cli."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from ai_sync.cli import app, _embed_token
from ai_sync.models import (
    AiSyncError,
    ConfigNotFoundError,
    LocalConfig,
    PullResult,
    PushResult,
    RemoteConfig,
    StatusEntry,
)

runner = CliRunner()


# ---------------------------------------------------------------------------
# --help
# ---------------------------------------------------------------------------

class TestHelp:
    def test_help_lists_all_commands(self) -> None:
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        assert "init" in result.output
        assert "push" in result.output
        assert "pull" in result.output
        assert "status" in result.output


# ---------------------------------------------------------------------------
# push
# ---------------------------------------------------------------------------

class TestPush:
    def test_push_success_with_changes(self) -> None:
        mock_engine = MagicMock()
        mock_engine.push.return_value = PushResult(
            tools=["claude-code"], file_count=3, committed=True
        )
        with patch("ai_sync.cli._build_engine", return_value=mock_engine):
            result = runner.invoke(app, ["push"])
        assert result.exit_code == 0
        assert "3" in result.output
        assert "claude-code" in result.output

    def test_push_no_changes(self) -> None:
        mock_engine = MagicMock()
        mock_engine.push.return_value = PushResult(tools=[], file_count=0, committed=False)
        with patch("ai_sync.cli._build_engine", return_value=mock_engine):
            result = runner.invoke(app, ["push"])
        assert result.exit_code == 0
        assert "Nothing to push" in result.output

    def test_push_config_not_found(self) -> None:
        with patch("ai_sync.cli._build_engine", side_effect=ConfigNotFoundError("no config")):
            result = runner.invoke(app, ["push"])
        assert result.exit_code == 1

    def test_push_generic_error(self) -> None:
        with patch("ai_sync.cli._build_engine", side_effect=AiSyncError("something failed")):
            result = runner.invoke(app, ["push"])
        assert result.exit_code == 1


# ---------------------------------------------------------------------------
# pull
# ---------------------------------------------------------------------------

class TestPull:
    def test_pull_success(self) -> None:
        mock_engine = MagicMock()
        mock_engine.pull.return_value = PullResult(tools=["gemini"], file_count=2)
        with patch("ai_sync.cli._build_engine", return_value=mock_engine):
            result = runner.invoke(app, ["pull"])
        assert result.exit_code == 0
        assert "2" in result.output
        assert "gemini" in result.output

    def test_pull_error(self) -> None:
        with patch("ai_sync.cli._build_engine", side_effect=AiSyncError("pull failed")):
            result = runner.invoke(app, ["pull"])
        assert result.exit_code == 1


# ---------------------------------------------------------------------------
# status
# ---------------------------------------------------------------------------

class TestStatus:
    def _make_engine(self, entries: list) -> MagicMock:
        mock_engine = MagicMock()
        mock_engine.status.return_value = entries
        mock_engine._repo.commits_behind.return_value = 0
        mock_engine._manifest_mgr.read.return_value = None
        return mock_engine

    def test_status_in_sync(self) -> None:
        mock_engine = self._make_engine([])
        with patch("ai_sync.cli._build_engine", return_value=mock_engine):
            result = runner.invoke(app, ["status"])
        assert result.exit_code == 0
        assert "in sync" in result.output.lower() or "match" in result.output.lower()

    def test_status_shows_changes(self) -> None:
        mock_engine = self._make_engine([
            StatusEntry(path="claude-code/settings.json", state="modified"),
            StatusEntry(path="gemini/GEMINI.md", state="added"),
        ])
        with patch("ai_sync.cli._build_engine", return_value=mock_engine):
            result = runner.invoke(app, ["status"])
        assert result.exit_code == 0
        assert "claude-code/settings.json" in result.output
        assert "modified" in result.output
        assert "added" in result.output

    def test_status_shows_behind_warning(self) -> None:
        mock_engine = self._make_engine([])
        mock_engine._repo.commits_behind.return_value = 3
        with patch("ai_sync.cli._build_engine", return_value=mock_engine):
            result = runner.invoke(app, ["status"])
        assert result.exit_code == 0
        assert "3" in result.output
        assert "behind" in result.output.lower()

    def test_status_shows_manifest_info(self) -> None:
        from datetime import datetime, timezone
        from ai_sync.models import Manifest, Platform
        mock_engine = self._make_engine([])
        mock_engine._manifest_mgr.read.return_value = Manifest(
            last_push=datetime(2026, 4, 20, 9, 30, tzinfo=timezone.utc),
            source_os=Platform.DARWIN,
            source_home="{{HOME}}",
            tools=["claude-code"],
        )
        with patch("ai_sync.cli._build_engine", return_value=mock_engine):
            result = runner.invoke(app, ["status"])
        assert result.exit_code == 0
        assert "2026-04-20" in result.output
        assert "darwin" in result.output.lower()

    def test_status_error(self) -> None:
        with patch("ai_sync.cli._build_engine", side_effect=AiSyncError("status failed")):
            result = runner.invoke(app, ["status"])
        assert result.exit_code == 1


# ---------------------------------------------------------------------------
# init
# ---------------------------------------------------------------------------

class TestInit:
    def test_remote_mode_without_token(self, tmp_path: Path) -> None:
        mock_git_repo = MagicMock()
        with (
            patch("ai_sync.cli._DEFAULT_CONFIG_DIR", tmp_path),
            patch("ai_sync.cli._DEFAULT_REPO_DIR", tmp_path / "repo"),
            patch("ai_sync.cli.ConfigStore") as mock_store_cls,
            patch("ai_sync.cli.GitRepo", return_value=mock_git_repo),
            patch("ai_sync.cli._discover_tools", return_value=[]),
            patch("ai_sync.cli._build_engine"),
            patch("ai_sync.cli._handle_conflict"),
        ):
            mock_store = MagicMock()
            mock_store.exists.return_value = False
            mock_store_cls.return_value = mock_store
            # mode=1(remote), no new repo, URL, no token
            result = runner.invoke(
                app, ["init"],
                input="1\nn\nhttps://github.com/u/r.git\nn\n",
            )
        assert result.exit_code == 0
        saved_config = mock_store.save.call_args[0][0]
        assert isinstance(saved_config, RemoteConfig)
        assert saved_config.repo_url == "https://github.com/u/r.git"
        assert saved_config.token is None
        mock_git_repo.clone.assert_called_once()

    def test_remote_mode_with_token(self, tmp_path: Path) -> None:
        mock_git_repo = MagicMock()
        with (
            patch("ai_sync.cli._DEFAULT_CONFIG_DIR", tmp_path),
            patch("ai_sync.cli._DEFAULT_REPO_DIR", tmp_path / "repo"),
            patch("ai_sync.cli.ConfigStore") as mock_store_cls,
            patch("ai_sync.cli.GitRepo", return_value=mock_git_repo),
            patch("ai_sync.cli._discover_tools", return_value=[]),
            patch("ai_sync.cli._build_engine"),
            patch("ai_sync.cli._handle_conflict"),
        ):
            mock_store = MagicMock()
            mock_store.exists.return_value = False
            mock_store_cls.return_value = mock_store
            result = runner.invoke(
                app, ["init"],
                input="1\nn\nhttps://github.com/u/r.git\ny\nghp_abc\n",
            )
        assert result.exit_code == 0
        saved_config = mock_store.save.call_args[0][0]
        assert isinstance(saved_config, RemoteConfig)
        assert saved_config.token == "ghp_abc"
        mock_git_repo.clone.assert_called_once()

    def test_local_mode_valid_path(self, tmp_path: Path) -> None:
        local_repo = tmp_path / "myrepo"
        local_repo.mkdir()
        (local_repo / ".git").mkdir()

        with (
            patch("ai_sync.cli._DEFAULT_CONFIG_DIR", tmp_path / "config"),
            patch("ai_sync.cli.ConfigStore") as mock_store_cls,
            patch("ai_sync.cli._discover_tools", return_value=[]),
            patch("ai_sync.cli._build_engine"),
            patch("ai_sync.cli._handle_conflict"),
        ):
            mock_store = MagicMock()
            mock_store.exists.return_value = False
            mock_store_cls.return_value = mock_store
            result = runner.invoke(
                app, ["init"],
                input=f"2\n{local_repo}\n",
            )
        assert result.exit_code == 0
        saved_config = mock_store.save.call_args[0][0]
        assert isinstance(saved_config, LocalConfig)
        assert saved_config.local_repo_path == local_repo

    def test_local_mode_path_not_exist(self, tmp_path: Path) -> None:
        with (
            patch("ai_sync.cli._DEFAULT_CONFIG_DIR", tmp_path / "config"),
            patch("ai_sync.cli.ConfigStore") as mock_store_cls,
            patch("ai_sync.cli._discover_tools", return_value=[]),
        ):
            mock_store = MagicMock()
            mock_store.exists.return_value = False
            mock_store_cls.return_value = mock_store
            result = runner.invoke(
                app, ["init"],
                input=f"2\n{tmp_path / 'nonexistent'}\n",
            )
        assert result.exit_code == 1
        assert "does not exist" in result.output.lower() or "does not exist" in (result.stderr or "").lower()

    def test_local_mode_not_a_git_repo(self, tmp_path: Path) -> None:
        not_a_repo = tmp_path / "notrepo"
        not_a_repo.mkdir()
        with (
            patch("ai_sync.cli._DEFAULT_CONFIG_DIR", tmp_path / "config"),
            patch("ai_sync.cli.ConfigStore") as mock_store_cls,
            patch("ai_sync.cli._discover_tools", return_value=[]),
        ):
            mock_store = MagicMock()
            mock_store.exists.return_value = False
            mock_store_cls.return_value = mock_store
            result = runner.invoke(
                app, ["init"],
                input=f"2\n{not_a_repo}\n",
            )
        assert result.exit_code == 1

    def test_init_aborts_if_config_exists_and_no_overwrite(self, tmp_path: Path) -> None:
        with (
            patch("ai_sync.cli._DEFAULT_CONFIG_DIR", tmp_path),
            patch("ai_sync.cli.ConfigStore") as mock_store_cls,
        ):
            mock_store = MagicMock()
            mock_store.exists.return_value = True
            mock_store_cls.return_value = mock_store
            result = runner.invoke(app, ["init"], input="n\n")
        assert result.exit_code == 0
        assert "Aborted" in result.output


# ---------------------------------------------------------------------------
# _embed_token
# ---------------------------------------------------------------------------

class TestEmbedToken:
    def test_embeds_token_into_https_url(self) -> None:
        url = "https://github.com/user/repo.git"
        result = _embed_token(url, "mytoken")
        assert result == "https://mytoken@github.com/user/repo.git"

    def test_returns_original_when_token_none(self) -> None:
        url = "https://github.com/user/repo.git"
        assert _embed_token(url, None) == url

    def test_returns_original_when_token_empty(self) -> None:
        url = "https://github.com/user/repo.git"
        assert _embed_token(url, "") == url


# ---------------------------------------------------------------------------
# T-014: init — tool discovery, conflict handling, managed_tools in config
# ---------------------------------------------------------------------------

class TestInitEnhanced:
    def test_managed_tools_saved_in_config(self, tmp_path: Path) -> None:
        mock_git_repo = MagicMock()
        with (
            patch("ai_sync.cli._DEFAULT_CONFIG_DIR", tmp_path),
            patch("ai_sync.cli._DEFAULT_REPO_DIR", tmp_path / "repo"),
            patch("ai_sync.cli.ConfigStore") as mock_store_cls,
            patch("ai_sync.cli.GitRepo", return_value=mock_git_repo),
            patch("ai_sync.cli._discover_tools", return_value=["claude-code", "gemini"]),
            patch("ai_sync.cli._build_engine"),
            patch("ai_sync.cli._handle_conflict"),
        ):
            mock_store = MagicMock()
            mock_store.exists.return_value = False
            mock_store_cls.return_value = mock_store
            result = runner.invoke(app, ["init"], input="1\nn\nhttps://github.com/u/r.git\nn\n")
        assert result.exit_code == 0
        saved_config = mock_store.save.call_args[0][0]
        assert saved_config.managed_tools == ["claude-code", "gemini"]

    def test_no_conflict_when_repo_empty(self, tmp_path: Path) -> None:
        mock_handle = MagicMock()
        with (
            patch("ai_sync.cli._DEFAULT_CONFIG_DIR", tmp_path),
            patch("ai_sync.cli._DEFAULT_REPO_DIR", tmp_path / "repo"),
            patch("ai_sync.cli.ConfigStore") as mock_store_cls,
            patch("ai_sync.cli.GitRepo"),
            patch("ai_sync.cli._discover_tools", return_value=[]),
            patch("ai_sync.cli._build_engine"),
            patch("ai_sync.cli._handle_conflict", mock_handle),
        ):
            mock_store = MagicMock()
            mock_store.exists.return_value = False
            mock_store_cls.return_value = mock_store
            runner.invoke(app, ["init"], input="1\nn\nhttps://github.com/u/r.git\nn\n")
        mock_handle.assert_called_once()

    def test_empty_managed_tools_when_user_rejects_all(self, tmp_path: Path) -> None:
        with (
            patch("ai_sync.cli._DEFAULT_CONFIG_DIR", tmp_path),
            patch("ai_sync.cli._DEFAULT_REPO_DIR", tmp_path / "repo"),
            patch("ai_sync.cli.ConfigStore") as mock_store_cls,
            patch("ai_sync.cli.GitRepo"),
            patch("ai_sync.cli._discover_tools", return_value=[]),
            patch("ai_sync.cli._build_engine"),
            patch("ai_sync.cli._handle_conflict"),
        ):
            mock_store = MagicMock()
            mock_store.exists.return_value = False
            mock_store_cls.return_value = mock_store
            runner.invoke(app, ["init"], input="1\nn\nhttps://github.com/u/r.git\nn\n")
        saved_config = mock_store.save.call_args[0][0]
        assert saved_config.managed_tools == []


# ---------------------------------------------------------------------------
# T-015: pull — backup branch called before engine.pull()
# ---------------------------------------------------------------------------

class TestPullBackup:
    def test_backup_called_before_pull(self) -> None:
        call_order: list[str] = []

        def fake_backup(*args, **kwargs) -> None:  # type: ignore[no-untyped-def]
            call_order.append("backup")

        mock_engine = MagicMock()
        mock_engine._repo = MagicMock()
        mock_engine._repo_dir = MagicMock()

        def fake_pull() -> PullResult:
            call_order.append("pull")
            return PullResult(tools=[], file_count=0)

        mock_engine.pull.side_effect = fake_pull

        with (
            patch("ai_sync.cli._build_engine", return_value=mock_engine),
            patch("ai_sync.cli._backup_to_branch", side_effect=fake_backup),
        ):
            result = runner.invoke(app, ["pull"])
        assert result.exit_code == 0
        assert call_order == ["backup", "pull"]

    def test_pull_continues_when_backup_push_fails(self) -> None:
        mock_engine = MagicMock()
        mock_engine._repo = MagicMock()
        mock_engine._repo_dir = MagicMock()
        mock_engine.pull.return_value = PullResult(tools=["gemini"], file_count=2)

        with (
            patch("ai_sync.cli._build_engine", return_value=mock_engine),
            patch("ai_sync.cli._backup_to_branch"),
        ):
            result = runner.invoke(app, ["pull"])
        assert result.exit_code == 0
        mock_engine.pull.assert_called_once()


# ---------------------------------------------------------------------------
# T-016: manage list / add / remove
# ---------------------------------------------------------------------------

class TestManage:
    def _make_store(self, tmp_path: Path, managed_tools: list[str]) -> MagicMock:
        mock_store = MagicMock()
        mock_store.load.return_value = RemoteConfig(
            repo_url="https://github.com/u/r.git",
            managed_tools=managed_tools,
        )
        return mock_store

    def test_list_empty(self, tmp_path: Path) -> None:
        with patch("ai_sync.cli.ConfigStore") as mock_cls:
            mock_cls.return_value = self._make_store(tmp_path, [])
            result = runner.invoke(app, ["manage", "list"])
        assert result.exit_code == 0
        assert "all tools" in result.output.lower()

    def test_list_nonempty(self, tmp_path: Path) -> None:
        with patch("ai_sync.cli.ConfigStore") as mock_cls:
            mock_cls.return_value = self._make_store(tmp_path, ["claude-code", "gemini"])
            result = runner.invoke(app, ["manage", "list"])
        assert result.exit_code == 0
        assert "claude-code" in result.output
        assert "gemini" in result.output

    def test_add_valid_tool(self, tmp_path: Path) -> None:
        mock_store = self._make_store(tmp_path, [])
        with (
            patch("ai_sync.cli.ConfigStore", return_value=mock_store),
            patch("ai_sync.cli.Path.home", return_value=tmp_path),
        ):
            result = runner.invoke(app, ["manage", "add", "gemini"])
        assert result.exit_code == 0
        saved = mock_store.save.call_args[0][0]
        assert "gemini" in saved.managed_tools

    def test_add_invalid_tool_id(self, tmp_path: Path) -> None:
        with patch("ai_sync.cli.ConfigStore") as mock_cls:
            mock_cls.return_value = self._make_store(tmp_path, [])
            result = runner.invoke(app, ["manage", "add", "cursor"])
        assert result.exit_code == 1

    def test_add_duplicate_tool(self, tmp_path: Path) -> None:
        mock_store = self._make_store(tmp_path, ["gemini"])
        with patch("ai_sync.cli.ConfigStore", return_value=mock_store):
            result = runner.invoke(app, ["manage", "add", "gemini"])
        assert result.exit_code == 0
        assert "already" in result.output.lower()
        mock_store.save.assert_not_called()

    def test_remove_existing_tool(self, tmp_path: Path) -> None:
        mock_store = self._make_store(tmp_path, ["claude-code", "gemini"])
        with patch("ai_sync.cli.ConfigStore", return_value=mock_store):
            result = runner.invoke(app, ["manage", "remove", "gemini"])
        assert result.exit_code == 0
        saved = mock_store.save.call_args[0][0]
        assert "gemini" not in saved.managed_tools

    def test_remove_nonexistent_tool(self, tmp_path: Path) -> None:
        mock_store = self._make_store(tmp_path, ["claude-code"])
        with patch("ai_sync.cli.ConfigStore", return_value=mock_store):
            result = runner.invoke(app, ["manage", "remove", "gemini"])
        assert result.exit_code == 1


# ---------------------------------------------------------------------------
# T-017: _build_engine() adapter filtering
# ---------------------------------------------------------------------------

class TestBuildEngineAdapterFilter:
    def _invoke_with_config(self, managed_tools: list[str]) -> MagicMock:
        """Invoke _build_engine with a mocked config and capture SyncEngine args."""
        from ai_sync.cli import _build_engine

        mock_config = RemoteConfig(
            repo_url="https://github.com/u/r.git",
            managed_tools=managed_tools,
        )
        captured: dict = {}

        def fake_sync_engine(**kwargs):  # type: ignore[no-untyped-def]
            captured["adapters"] = kwargs.get("adapters", [])
            return MagicMock()

        with (
            patch("ai_sync.cli.ConfigStore") as mock_store_cls,
            patch("ai_sync.cli.GitRepo"),
            patch("ai_sync.cli.SyncEngine", side_effect=fake_sync_engine),
            patch("ai_sync.cli.FileCollector"),
            patch("ai_sync.cli.ManifestManager"),
            patch("ai_sync.cli._DEFAULT_CONFIG_DIR", Path("/tmp")),
            patch("ai_sync.cli._DEFAULT_REPO_DIR", Path("/tmp/repo")),
        ):
            mock_store = MagicMock()
            mock_store.load.return_value = mock_config
            mock_store_cls.return_value = mock_store
            _build_engine()

        return captured.get("adapters", [])

    def test_filtered_to_single_tool(self) -> None:
        from ai_sync.adapters.gemini import GeminiAdapter
        adapters = self._invoke_with_config(["gemini"])
        assert len(adapters) == 1
        assert isinstance(adapters[0], GeminiAdapter)

    def test_empty_managed_tools_uses_all_adapters(self) -> None:
        adapters = self._invoke_with_config([])
        assert len(adapters) == 4

    def test_invalid_tool_id_skipped_with_warning(self, capsys) -> None:
        adapters = self._invoke_with_config(["gemini", "nonexistent-tool"])
        from ai_sync.adapters.gemini import GeminiAdapter
        assert len(adapters) == 1
        assert isinstance(adapters[0], GeminiAdapter)
