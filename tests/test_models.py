"""Unit tests for ai_sync.models."""

from datetime import datetime, timezone
from pathlib import Path

import pytest
from pydantic import TypeAdapter, ValidationError

from ai_sync.models import (
    AiSyncError,
    AppConfig,
    CollectedFile,
    ConfigNotFoundError,
    GitOperationError,
    LocalConfig,
    Manifest,
    Platform,
    PullResult,
    PushResult,
    RemoteConfig,
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


class TestRemoteConfig:
    def test_instantiation_without_token(self) -> None:
        cfg = RemoteConfig(repo_url="https://github.com/u/r.git")
        assert cfg.mode == "remote"
        assert cfg.repo_url == "https://github.com/u/r.git"
        assert cfg.token is None

    def test_instantiation_with_token(self) -> None:
        cfg = RemoteConfig(repo_url="https://github.com/u/r.git", token="ghp_abc")
        assert cfg.token == "ghp_abc"

    def test_missing_repo_url(self) -> None:
        with pytest.raises(ValidationError):
            RemoteConfig()  # type: ignore[call-arg]

    def test_serialization(self) -> None:
        cfg = RemoteConfig(repo_url="https://example.com/r.git", token="tok")
        data = cfg.model_dump(mode="json")
        assert data["mode"] == "remote"
        assert data["repo_url"] == "https://example.com/r.git"
        assert data["token"] == "tok"

    def test_managed_tools_default_empty(self) -> None:
        cfg = RemoteConfig(repo_url="https://github.com/u/r.git")
        assert cfg.managed_tools == []

    def test_managed_tools_stored(self) -> None:
        cfg = RemoteConfig(repo_url="https://github.com/u/r.git", managed_tools=["claude-code", "gemini"])
        assert cfg.managed_tools == ["claude-code", "gemini"]

    def test_managed_tools_in_serialization(self) -> None:
        cfg = RemoteConfig(repo_url="https://github.com/u/r.git", managed_tools=["gemini"])
        data = cfg.model_dump(mode="json")
        assert data["managed_tools"] == ["gemini"]


class TestLocalConfig:
    def test_instantiation(self, tmp_path: Path) -> None:
        cfg = LocalConfig(local_repo_path=tmp_path)
        assert cfg.mode == "local"
        assert cfg.local_repo_path == tmp_path

    def test_missing_path(self) -> None:
        with pytest.raises(ValidationError):
            LocalConfig()  # type: ignore[call-arg]

    def test_path_serialized_as_string(self, tmp_path: Path) -> None:
        cfg = LocalConfig(local_repo_path=tmp_path)
        data = cfg.model_dump(mode="json")
        assert isinstance(data["local_repo_path"], str)

    def test_managed_tools_default_empty(self, tmp_path: Path) -> None:
        cfg = LocalConfig(local_repo_path=tmp_path)
        assert cfg.managed_tools == []

    def test_managed_tools_stored(self, tmp_path: Path) -> None:
        cfg = LocalConfig(local_repo_path=tmp_path, managed_tools=["opencode"])
        assert cfg.managed_tools == ["opencode"]


class TestAppConfigUnion:
    _adapter: TypeAdapter = TypeAdapter(AppConfig)  # type: ignore[type-arg]

    def test_routes_to_remote(self) -> None:
        cfg = self._adapter.validate_python(
            {"mode": "remote", "repo_url": "https://example.com/r.git"}
        )
        assert isinstance(cfg, RemoteConfig)

    def test_routes_to_local(self, tmp_path: Path) -> None:
        cfg = self._adapter.validate_python(
            {"mode": "local", "local_repo_path": str(tmp_path)}
        )
        assert isinstance(cfg, LocalConfig)

    def test_missing_mode_raises(self) -> None:
        with pytest.raises(ValidationError):
            self._adapter.validate_python({"repo_url": "https://example.com/r.git"})

    def test_invalid_mode_raises(self) -> None:
        with pytest.raises(ValidationError):
            self._adapter.validate_python({"mode": "ssh", "repo_url": "git@example.com"})


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

    def test_git_operation_error(self) -> None:
        orig = ValueError("git failed")
        err = GitOperationError("push failed", original=orig)
        assert str(err) == "push failed"
        assert err.original is orig

    def test_catch_as_base(self) -> None:
        with pytest.raises(AiSyncError):
            raise ConfigNotFoundError("no config")
