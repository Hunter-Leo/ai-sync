"""Integration tests for ai_sync.cli."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from ai_sync.cli import app
from ai_sync.models import (
    AiSyncError,
    ConfigNotFoundError,
    PullResult,
    PushResult,
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
    def test_init_creates_config_with_new_repo(self, tmp_path: Path) -> None:
        mock_gh = MagicMock()
        mock_gh.create_private_repo.return_value = "https://github.com/u/r.git"
        mock_git_repo = MagicMock()

        with (
            patch("ai_sync.cli._DEFAULT_CONFIG_DIR", tmp_path),
            patch("ai_sync.cli._DEFAULT_REPO_DIR", tmp_path / "repo"),
            patch("ai_sync.cli.ConfigStore") as mock_store_cls,
            patch("ai_sync.cli.GitHubClient", return_value=mock_gh),
            patch("ai_sync.cli.GitRepo", return_value=mock_git_repo),
        ):
            mock_store = MagicMock()
            mock_store.exists.return_value = False
            mock_store_cls.return_value = mock_store

            result = runner.invoke(
                app,
                ["init"],
                input="ghp_token\ny\nai-sync-config\n",
            )

        assert result.exit_code == 0
        mock_store.save.assert_called_once()
        mock_git_repo.clone.assert_called_once()

    def test_init_with_existing_repo_url(self, tmp_path: Path) -> None:
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
                app,
                ["init"],
                # token, don't create new repo, provide URL
                input="ghp_token\nn\nhttps://github.com/u/existing.git\n",
            )

        assert result.exit_code == 0
        mock_git_repo.clone.assert_called_once()
