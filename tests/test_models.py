"""Unit tests for ai_sync.models."""

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from ai_sync.models import (
    AiSyncError,
    AppConfig,
    CollectedFile,
    ConfigNotFoundError,
    GitHubAPIError,
    GitOperationError,
    Manifest,
    Platform,
    PullResult,
    PushResult,
    RepoNotInitializedError,
    StatusEntry,
    SyncItem,
)


class TestPlatform:
    def test_values(self) -> None:
        assert Platform.DARWIN == "darwin"
        assert Platform.LINUX == "linux"
        assert Platform.WINDOWS == "windows"

    def test_from_string(self) -> None:
        assert Platform("darwin") is Platform.DARWIN

    def test_invalid_value(self) -> None:
        with pytest.raises(ValueError):
            Platform("freebsd")


class TestAppConfig:
    def test_instantiation(self) -> None:
        cfg = AppConfig(github_token="ghp_abc", repo_url="https://github.com/u/r.git")
        assert cfg.github_token == "ghp_abc"
        assert cfg.repo_url == "https://github.com/u/r.git"

    def test_missing_fields(self) -> None:
        with pytest.raises(ValidationError):
            AppConfig(github_token="tok")  # type: ignore[call-arg]

    def test_wrong_type(self) -> None:
        with pytest.raises(ValidationError):
            AppConfig(github_token=123, repo_url="url")  # type: ignore[arg-type]


class TestManifest:
    def _make(self) -> Manifest:
        return Manifest(
            last_push=datetime(2026, 4, 16, 10, 0, 0, tzinfo=timezone.utc),
            source_os=Platform.DARWIN,
            source_home="{{HOME}}",
            tools=["claude-code", "gemini"],
        )

    def test_instantiation(self) -> None:
        m = self._make()
        assert m.version == "1.0"
        assert m.source_os == Platform.DARWIN
        assert m.tools == ["claude-code", "gemini"]

    def test_default_version(self) -> None:
        assert self._make().version == "1.0"

    def test_default_tools(self) -> None:
        m = Manifest(
            last_push=datetime(2026, 1, 1, tzinfo=timezone.utc),
            source_os=Platform.LINUX,
            source_home="{{HOME}}",
        )
        assert m.tools == []

    def test_invalid_platform(self) -> None:
        with pytest.raises(ValidationError):
            Manifest(
                last_push=datetime(2026, 1, 1, tzinfo=timezone.utc),
                source_os="haiku",  # type: ignore[arg-type]
                source_home="{{HOME}}",
            )


class TestSyncItem:
    def test_instantiation(self, tmp_path) -> None:  # type: ignore[no-untyped-def]
        item = SyncItem(local_path=tmp_path / "settings.json", repo_path="settings.json")
        assert item.is_dir is False
        assert item.optional is False

    def test_optional_flag(self, tmp_path) -> None:  # type: ignore[no-untyped-def]
        item = SyncItem(local_path=tmp_path / "agents", repo_path="agents/", is_dir=True, optional=True)
        assert item.optional is True
        assert item.is_dir is True


class TestCollectedFile:
    def test_text_file(self) -> None:
        cf = CollectedFile(repo_path="claude-code/settings.json", content=b'{"model":"opus"}')
        assert cf.is_binary is False

    def test_binary_file(self) -> None:
        cf = CollectedFile(repo_path="claude-code/icon.png", content=b"\x89PNG", is_binary=True)
        assert cf.is_binary is True


class TestStatusEntry:
    def test_valid_states(self) -> None:
        for state in ("added", "modified", "deleted", "unchanged"):
            e = StatusEntry(path="some/file.json", state=state)  # type: ignore[arg-type]
            assert e.state == state

    def test_invalid_state(self) -> None:
        with pytest.raises(ValidationError):
            StatusEntry(path="f", state="renamed")  # type: ignore[arg-type]


class TestResultModels:
    def test_push_result_defaults(self) -> None:
        r = PushResult()
        assert r.tools == []
        assert r.file_count == 0
        assert r.committed is False

    def test_pull_result_defaults(self) -> None:
        r = PullResult()
        assert r.tools == []
        assert r.file_count == 0


class TestExceptions:
    def test_hierarchy(self) -> None:
        assert issubclass(ConfigNotFoundError, AiSyncError)
        assert issubclass(RepoNotInitializedError, AiSyncError)
        assert issubclass(GitOperationError, AiSyncError)
        assert issubclass(GitHubAPIError, AiSyncError)

    def test_git_operation_error(self) -> None:
        orig = ValueError("git failed")
        err = GitOperationError("push failed", original=orig)
        assert str(err) == "push failed"
        assert err.original is orig

    def test_github_api_error(self) -> None:
        err = GitHubAPIError("not found", status_code=404)
        assert err.status_code == 404

    def test_catch_as_base(self) -> None:
        with pytest.raises(AiSyncError):
            raise ConfigNotFoundError("no config")
