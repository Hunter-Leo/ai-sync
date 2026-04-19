"""SyncEngine — orchestrates push, pull, and status operations.

The engine coordinates all lower-level components (FileCollector, PathMapper,
GitRepo, ManifestManager) to implement the three user-facing operations:

    push  — collect local configs → write to repo → commit & push
    pull  — git pull → read repo files → restore paths → write locally
    status — compare local (abstracted) files with repo files

Data flow — push:

    ToolAdapter.get_sync_items()
        → FileCollector.collect()       # resolve symlinks, read content
        → PathMapper.abstract_paths()   # already applied inside FileCollector
        → write to repo_dir/<tool>/<path>
        → ManifestManager.write()
        → GitRepo.push()

Data flow — pull:

    GitRepo.pull()
        → walk repo_dir files
        → PathMapper.restore_paths()    # replace placeholders with real paths
        → write to local config dirs
"""

import hashlib
import platform as _platform_module
import shutil
from datetime import datetime, timezone
from pathlib import Path

from ai_sync.adapters.base import ToolAdapter
from ai_sync.file_collector import FileCollector
from ai_sync.git_repo import GitRepo
from ai_sync.manifest import ManifestManager
from ai_sync.models import (
    Manifest,
    Platform,
    PullResult,
    PushResult,
    StatusEntry,
)
from ai_sync.path_mapper import PathMapper

from rich.console import Console

_console = Console(stderr=True)


class SyncEngine:
    """Orchestrates push, pull, and status for all registered tool adapters.

    All dependencies are injected via the constructor so they can be replaced
    with test doubles in unit tests (Dependency Inversion Principle).

    Args:
        adapters: List of ToolAdapter instances to sync.
        repo: GitRepo managing the local clone of the sync repository.
        mapper: PathMapper for the current platform.
        collector: FileCollector used during push and status.
        manifest_mgr: ManifestManager for reading/writing _manifest.json.
        repo_dir: Root directory of the local git clone.
    """

    def __init__(
        self,
        adapters: list[ToolAdapter],
        repo: GitRepo,
        mapper: PathMapper,
        collector: FileCollector,
        manifest_mgr: ManifestManager,
        repo_dir: Path,
    ) -> None:
        """Initialize SyncEngine.

        Args:
            adapters: List of ToolAdapter instances to sync.
            repo: GitRepo managing the local clone.
            mapper: PathMapper for the current platform.
            collector: FileCollector for reading local files.
            manifest_mgr: ManifestManager for _manifest.json.
            repo_dir: Root directory of the local git clone.
        """
        self._adapters = adapters
        self._repo = repo
        self._mapper = mapper
        self._collector = collector
        self._manifest_mgr = manifest_mgr
        self._repo_dir = repo_dir
        self._adapter_map: dict[str, ToolAdapter] = {a.tool_id: a for a in adapters}

    def push(self) -> PushResult:
        """Collect local configs, write to repo, commit, and push.

        Returns:
            PushResult with statistics about the operation.

        Raises:
            RepoNotInitializedError: If the local clone does not exist.
            GitOperationError: If the git push fails.
        """
        file_count = 0
        tool_ids: list[str] = []

        for adapter in self._adapters:
            tool_dir = self._repo_dir / adapter.tool_id
            if tool_dir.exists():
                shutil.rmtree(tool_dir)
            tool_dir.mkdir(parents=True, exist_ok=True)

            files = self._collector.collect(adapter)
            for cf in files:
                dest = (self._repo_dir / cf.repo_path).resolve()
                if not dest.is_relative_to(self._repo_dir.resolve()):
                    _console.print(
                        f"[red]Security:[/red] push path traversal blocked: {cf.repo_path}"
                    )
                    continue
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_bytes(cf.content)
                file_count += 1
            if files:
                tool_ids.append(adapter.tool_id)

        manifest = Manifest(
            last_push=datetime.now(tz=timezone.utc),
            source_os=self._current_platform(),
            source_home="{{HOME}}",
            tools=tool_ids,
        )
        self._manifest_mgr.write(manifest)

        commit_msg = f"ai-sync push: {', '.join(tool_ids) or 'no tools'}"
        committed = self._repo.push(commit_msg)

        return PushResult(tools=tool_ids, file_count=file_count, committed=committed)

    def pull(self) -> PullResult:
        """Pull from remote, restore paths, and write files to local config dirs.

        Returns:
            PullResult with statistics about the operation.

        Raises:
            RepoNotInitializedError: If the local clone does not exist.
            GitOperationError: If the git pull fails.
        """
        self._repo.pull()

        file_count = 0
        tool_ids: set[str] = set()

        for file_path in self._repo_dir.rglob("*"):
            if not file_path.is_file():
                continue
            rel = file_path.relative_to(self._repo_dir)
            parts = rel.parts
            if not parts or parts[0].startswith("_"):
                # Skip _manifest.json and other meta files.
                continue

            tool_id = parts[0]
            adapter = self._adapter_map.get(tool_id)
            if adapter is None:
                continue

            rest = Path(*parts[1:]) if len(parts) > 1 else Path()
            local_path = (adapter.get_base_dir() / rest).resolve()
            base_dir = adapter.get_base_dir().resolve()
            if not local_path.is_relative_to(base_dir):
                _console.print(
                    f"[red]Security:[/red] pull path traversal blocked: {rel.as_posix()}"
                )
                continue
            local_path.parent.mkdir(parents=True, exist_ok=True)

            raw = file_path.read_bytes()
            try:
                text = raw.decode("utf-8")
                restored = self._mapper.restore_paths(text)
                local_path.write_text(restored, encoding="utf-8")
            except UnicodeDecodeError:
                local_path.write_bytes(raw)

            file_count += 1
            tool_ids.add(tool_id)

        return PullResult(tools=sorted(tool_ids), file_count=file_count)

    def status(self) -> list[StatusEntry]:
        """Compare local configs (after path abstraction) with the repo.

        Returns:
            List of StatusEntry instances describing each file's change state.
            Files are sorted by path for deterministic output.
        """
        # Build a map of repo_path → sha256 for files currently in the repo.
        repo_hashes: dict[str, str] = {}
        for file_path in self._repo_dir.rglob("*"):
            if not file_path.is_file():
                continue
            rel = file_path.relative_to(self._repo_dir)
            if rel.parts and rel.parts[0].startswith("_"):
                continue
            repo_hashes[rel.as_posix()] = _sha256(file_path.read_bytes())

        # Build a map of repo_path → sha256 for local files (abstracted).
        local_hashes: dict[str, str] = {}
        for adapter in self._adapters:
            for cf in self._collector.collect(adapter):
                local_hashes[cf.repo_path] = _sha256(cf.content)

        all_paths = set(repo_hashes) | set(local_hashes)
        entries: list[StatusEntry] = []

        for path in sorted(all_paths):
            in_repo = path in repo_hashes
            in_local = path in local_hashes

            if in_local and not in_repo:
                state = "added"
            elif in_repo and not in_local:
                state = "deleted"
            elif repo_hashes[path] != local_hashes[path]:
                state = "modified"
            else:
                state = "unchanged"

            entries.append(StatusEntry(path=path, state=state))

        return entries

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _current_platform() -> Platform:
        """Detect the current operating system as a Platform enum value.

        Returns:
            Platform.DARWIN, Platform.LINUX, or Platform.WINDOWS.
        """
        system = _platform_module.system().lower()
        if system == "darwin":
            return Platform.DARWIN
        if system == "windows":
            return Platform.WINDOWS
        return Platform.LINUX


def _sha256(data: bytes) -> str:
    """Return the hex SHA-256 digest of *data*.

    Args:
        data: Raw bytes to hash.

    Returns:
        Lowercase hex string of the SHA-256 digest.
    """
    return hashlib.sha256(data).hexdigest()
