"""Unit tests for ai_sync.config_store."""

import json
import platform
import stat
from pathlib import Path

import pytest

from ai_sync.config_store import ConfigStore
from ai_sync.models import AiSyncError, ConfigNotFoundError, LocalConfig, RemoteConfig


@pytest.fixture
def store(tmp_path: Path) -> ConfigStore:
    return ConfigStore(config_path=tmp_path / "config.json")


class TestExists:
    def test_false_when_missing(self, store: ConfigStore) -> None:
        assert store.exists() is False

    def test_true_after_save(self, store: ConfigStore) -> None:
        store.save(RemoteConfig(repo_url="https://github.com/u/r.git"))
        assert store.exists() is True


class TestSave:
    def test_creates_parent_dirs(self, tmp_path: Path) -> None:
        deep = tmp_path / "a" / "b" / "config.json"
        s = ConfigStore(config_path=deep)
        s.save(RemoteConfig(repo_url="https://github.com/u/r.git"))
        assert deep.is_file()

    def test_remote_config_written_correctly(self, store: ConfigStore, tmp_path: Path) -> None:
        cfg = RemoteConfig(repo_url="https://github.com/u/r.git", token="ghp_abc")
        store.save(cfg)
        data = json.loads((tmp_path / "config.json").read_text())
        assert data["mode"] == "remote"
        assert data["repo_url"] == "https://github.com/u/r.git"
        assert data["token"] == "ghp_abc"

    def test_local_config_written_correctly(self, store: ConfigStore, tmp_path: Path) -> None:
        cfg = LocalConfig(local_repo_path=tmp_path / "myrepo")
        store.save(cfg)
        data = json.loads((tmp_path / "config.json").read_text())
        assert data["mode"] == "local"
        assert "local_repo_path" in data


class TestLoad:
    def test_roundtrip_remote(self, store: ConfigStore) -> None:
        cfg = RemoteConfig(repo_url="https://github.com/u/r.git", token="ghp_xyz")
        store.save(cfg)
        loaded = store.load()
        assert isinstance(loaded, RemoteConfig)
        assert loaded.repo_url == "https://github.com/u/r.git"
        assert loaded.token == "ghp_xyz"

    def test_roundtrip_local(self, store: ConfigStore, tmp_path: Path) -> None:
        repo = tmp_path / "myrepo"
        cfg = LocalConfig(local_repo_path=repo)
        store.save(cfg)
        loaded = store.load()
        assert isinstance(loaded, LocalConfig)
        assert loaded.local_repo_path == repo

    def test_raises_when_missing(self, store: ConfigStore) -> None:
        with pytest.raises(ConfigNotFoundError, match="ai-sync init"):
            store.load()

    def test_raises_on_invalid_json(self, tmp_path: Path) -> None:
        p = tmp_path / "config.json"
        p.write_text("not json", encoding="utf-8")
        s = ConfigStore(config_path=p)
        with pytest.raises(AiSyncError, match="invalid JSON"):
            s.load()

    def test_raises_on_invalid_structure(self, tmp_path: Path) -> None:
        p = tmp_path / "config.json"
        p.write_text(json.dumps({"mode": "remote"}), encoding="utf-8")
        s = ConfigStore(config_path=p)
        with pytest.raises(AiSyncError, match="invalid structure"):
            s.load()


class TestBackwardCompatMigration:
    def test_legacy_with_github_token_migrates(self, tmp_path: Path) -> None:
        """Old config.json (no mode, github_token field) migrates to RemoteConfig."""
        p = tmp_path / "config.json"
        p.write_text(
            json.dumps({"github_token": "ghp_old", "repo_url": "https://github.com/u/r.git"}),
            encoding="utf-8",
        )
        loaded = ConfigStore(config_path=p).load()
        assert isinstance(loaded, RemoteConfig)
        assert loaded.token == "ghp_old"
        assert loaded.repo_url == "https://github.com/u/r.git"

    def test_legacy_without_token_migrates(self, tmp_path: Path) -> None:
        """Old config.json without github_token migrates to RemoteConfig with token=None."""
        p = tmp_path / "config.json"
        p.write_text(
            json.dumps({"repo_url": "https://github.com/u/r.git"}),
            encoding="utf-8",
        )
        loaded = ConfigStore(config_path=p).load()
        assert isinstance(loaded, RemoteConfig)
        assert loaded.token is None

    def test_legacy_without_managed_tools_defaults_to_empty(self, tmp_path: Path) -> None:
        """Old config.json without managed_tools deserializes to managed_tools=[]."""
        p = tmp_path / "config.json"
        p.write_text(
            json.dumps({"mode": "remote", "repo_url": "https://github.com/u/r.git"}),
            encoding="utf-8",
        )
        loaded = ConfigStore(config_path=p).load()
        assert isinstance(loaded, RemoteConfig)
        assert loaded.managed_tools == []

    def test_managed_tools_roundtrip(self, tmp_path: Path) -> None:
        """managed_tools is persisted and restored correctly."""
        p = tmp_path / "config.json"
        cfg = RemoteConfig(repo_url="https://github.com/u/r.git", managed_tools=["claude-code", "gemini"])
        store = ConfigStore(config_path=p)
        store.save(cfg)
        loaded = store.load()
        assert isinstance(loaded, RemoteConfig)
        assert loaded.managed_tools == ["claude-code", "gemini"]


class TestFilePermissions:
    def test_config_file_is_owner_readable_only(self, store: ConfigStore, tmp_path: Path) -> None:
        if platform.system() == "Windows":
            pytest.skip("chmod 0o600 not enforced on Windows")
        store.save(RemoteConfig(repo_url="https://github.com/u/r.git"))
        mode = stat.S_IMODE((tmp_path / "config.json").stat().st_mode)
        assert mode == 0o600, f"Expected 0o600, got {oct(mode)}"
