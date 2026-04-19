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
    def test_status_in_sync(self) -> None:
        mock_engine = MagicMock()
        mock_engine.status.return_value = []
        with patch("ai_sync.cli._build_engine", return_value=mock_engine):
            result = runner.invoke(app, ["status"])
        assert result.exit_code == 0
        assert "in sync" in result.output.lower()

    def test_status_shows_changes(self) -> None:
        mock_engine = MagicMock()
        mock_engine.status.return_value = [
            StatusEntry(path="claude-code/settings.json", state="modified"),
            StatusEntry(path="gemini/GEMINI.md", state="added"),
        ]
        with patch("ai_sync.cli._build_engine", return_value=mock_engine):
            result = runner.invoke(app, ["status"])
        assert result.exit_code == 0
        assert "claude-code/settings.json" in result.output
        assert "modified" in result.output
        assert "added" in result.output

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
        # Create a fake git repo
        local_repo = tmp_path / "myrepo"
        local_repo.mkdir()
        (local_repo / ".git").mkdir()

        with (
            patch("ai_sync.cli._DEFAULT_CONFIG_DIR", tmp_path / "config"),
            patch("ai_sync.cli.ConfigStore") as mock_store_cls,
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
