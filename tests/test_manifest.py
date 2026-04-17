"""Unit tests for ai_sync.manifest."""

from datetime import datetime, timezone
from pathlib import Path

import pytest

from ai_sync.manifest import ManifestManager
from ai_sync.models import AiSyncError, Manifest, Platform


def _make_manifest() -> Manifest:
    return Manifest(
        last_push=datetime(2026, 4, 17, 10, 0, 0, tzinfo=timezone.utc),
        source_os=Platform.DARWIN,
        source_home="{{HOME}}",
        tools=["claude-code", "gemini"],
    )


class TestRead:
    def test_returns_none_when_missing(self, tmp_path: Path) -> None:
        mgr = ManifestManager(repo_dir=tmp_path)
        assert mgr.read() is None

    def test_roundtrip(self, tmp_path: Path) -> None:
        mgr = ManifestManager(repo_dir=tmp_path)
        original = _make_manifest()
        mgr.write(original)
        loaded = mgr.read()
        assert loaded is not None
        assert loaded.source_os == Platform.DARWIN
        assert loaded.tools == ["claude-code", "gemini"]
        assert loaded.source_home == "{{HOME}}"

    def test_raises_on_invalid_json(self, tmp_path: Path) -> None:
        (tmp_path / "_manifest.json").write_text("not json", encoding="utf-8")
        mgr = ManifestManager(repo_dir=tmp_path)
        with pytest.raises(AiSyncError, match="invalid JSON"):
            mgr.read()


class TestWrite:
    def test_creates_file(self, tmp_path: Path) -> None:
        mgr = ManifestManager(repo_dir=tmp_path)
        mgr.write(_make_manifest())
        assert (tmp_path / "_manifest.json").is_file()

    def test_creates_parent_dirs(self, tmp_path: Path) -> None:
        deep = tmp_path / "a" / "b"
        mgr = ManifestManager(repo_dir=deep)
        mgr.write(_make_manifest())
        assert (deep / "_manifest.json").is_file()

    def test_written_content_is_valid_json(self, tmp_path: Path) -> None:
        import json
        mgr = ManifestManager(repo_dir=tmp_path)
        mgr.write(_make_manifest())
        data = json.loads((tmp_path / "_manifest.json").read_text())
        assert data["source_os"] == "darwin"
        assert data["version"] == "1.0"
