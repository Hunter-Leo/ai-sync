"""Unit tests for ai_sync.config_store."""

from pathlib import Path

import pytest
from pydantic import ValidationError

from ai_sync.config_store import ConfigStore
from ai_sync.models import AppConfig, AiSyncError, ConfigNotFoundError


@pytest.fixture
def store(tmp_path: Path) -> ConfigStore:
    return ConfigStore(config_path=tmp_path / "config.json")


class TestExists:
    def test_false_when_missing(self, store: ConfigStore) -> None:
        assert store.exists() is False

    def test_true_after_save(self, store: ConfigStore) -> None:
        store.save(AppConfig(github_token="tok", repo_url="https://github.com/u/r.git"))
        assert store.exists() is True


class TestSave:
    def test_creates_parent_dirs(self, tmp_path: Path) -> None:
        deep = tmp_path / "a" / "b" / "config.json"
        s = ConfigStore(config_path=deep)
        s.save(AppConfig(github_token="tok", repo_url="https://github.com/u/r.git"))
        assert deep.is_file()

    def test_writes_valid_json(self, store: ConfigStore, tmp_path: Path) -> None:
        import json
        cfg = AppConfig(github_token="ghp_abc", repo_url="https://github.com/u/r.git")
        store.save(cfg)
        data = json.loads((tmp_path / "config.json").read_text())
        assert data["github_token"] == "ghp_abc"
        assert data["repo_url"] == "https://github.com/u/r.git"


class TestLoad:
    def test_roundtrip(self, store: ConfigStore) -> None:
        cfg = AppConfig(github_token="ghp_xyz", repo_url="https://github.com/u/r.git")
        store.save(cfg)
        loaded = store.load()
        assert loaded.github_token == "ghp_xyz"
        assert loaded.repo_url == "https://github.com/u/r.git"

    def test_raises_when_missing(self, store: ConfigStore) -> None:
        with pytest.raises(ConfigNotFoundError, match="ai-sync init"):
            store.load()

    def test_raises_on_invalid_json(self, tmp_path: Path) -> None:
        p = tmp_path / "config.json"
        p.write_text("not json", encoding="utf-8")
        s = ConfigStore(config_path=p)
        with pytest.raises(AiSyncError, match="invalid JSON"):
            s.load()

    def test_raises_on_missing_fields(self, tmp_path: Path) -> None:
        import json
        p = tmp_path / "config.json"
        p.write_text(json.dumps({"github_token": "tok"}), encoding="utf-8")
        s = ConfigStore(config_path=p)
        with pytest.raises(ValidationError):
            s.load()


class TestFilePermissions:
    def test_config_file_is_owner_readable_only(self, store: ConfigStore, tmp_path: Path) -> None:
        import platform
        import stat
        if platform.system() == "Windows":
            pytest.skip("chmod 0o600 not enforced on Windows")
        store.save(AppConfig(github_token="tok", repo_url="https://github.com/u/r.git"))
        mode = stat.S_IMODE((tmp_path / "config.json").stat().st_mode)
        assert mode == 0o600, f"Expected 0o600, got {oct(mode)}"
