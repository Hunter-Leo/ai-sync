"""FileCollector — reads local config files for a ToolAdapter.

Responsibilities:
- Iterate the SyncItems declared by a ToolAdapter
- Resolve symlinks to their real content (never store the link itself)
- Recursively walk directories, applying per-adapter exclude patterns
- Detect text vs. binary files and apply PathMapper substitution to text files
- Emit rich warnings for dangling symlinks; skip them silently

Symlink resolution diagram:

    local_path
        │
        ├─ is_symlink? ──yes──► resolve() ──► exists? ──no──► warn + skip
        │                                         │
        │                                        yes
        │                                         ▼
        └─ not symlink ──────────────────► read content
                                               │
                                    is_text? ──┤
                                               ├─ yes ──► abstract_paths()
                                               └─ no  ──► raw bytes
"""

from pathlib import Path

from rich.console import Console

from ai_sync.adapters.base import ToolAdapter
from ai_sync.models import CollectedFile, SyncItem
from ai_sync.path_mapper import PathMapper

_console = Console(stderr=True)


class FileCollector:
    """Collects files from the local filesystem for a given ToolAdapter.

    Args:
        mapper: PathMapper used to abstract real paths in text file content.
    """

    def __init__(self, mapper: PathMapper) -> None:
        """Initialize FileCollector.

        Args:
            mapper: PathMapper used to abstract real paths in text file content.
        """
        self._mapper = mapper

    def collect(self, adapter: ToolAdapter) -> list[CollectedFile]:
        """Collect all files declared by *adapter*.

        Iterates the adapter's SyncItems, resolves symlinks, walks directories,
        and returns one CollectedFile per file found.

        Args:
            adapter: The ToolAdapter whose sync items should be collected.

        Returns:
            List of CollectedFile instances ready to be written to the repo.
            The repo_path of each file is prefixed with the adapter's tool_id
            (e.g. "claude-code/settings.json").
        """
        results: list[CollectedFile] = []
        tool_prefix = adapter.tool_id

        for item in adapter.get_sync_items():
            resolved = self._resolve_path(item.local_path)
            if resolved is None:
                if not item.optional:
                    _console.print(
                        f"[yellow]Warning:[/yellow] required path not found: {item.local_path}"
                    )
                continue

            if item.is_dir:
                exclude = self._get_exclude_patterns(adapter)
                results.extend(
                    self._collect_dir(resolved, item.repo_path, tool_prefix, exclude)
                )
            else:
                cf = self._collect_file(resolved, f"{tool_prefix}/{item.repo_path}")
                if cf is not None:
                    results.append(cf)

        return results

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _resolve_path(self, path: Path) -> Path | None:
        """Resolve *path*, following symlinks if necessary.

        Args:
            path: The path to resolve (may or may not be a symlink).

        Returns:
            The resolved real path, or None if the path does not exist or is
            a dangling symlink.
        """
        if path.is_symlink():
            resolved = path.resolve()
            if not resolved.exists():
                _console.print(
                    f"[yellow]Warning:[/yellow] dangling symlink skipped: {path} → {resolved}"
                )
                return None
            return resolved
        if not path.exists():
            return None
        return path

    def _collect_dir(
        self,
        dir_path: Path,
        repo_dir: str,
        tool_prefix: str,
        exclude_patterns: list[str],
    ) -> list[CollectedFile]:
        """Recursively collect all files under *dir_path*.

        Args:
            dir_path: Real (resolved) directory path on the local filesystem.
            repo_dir: Relative directory path within the tool's repo sub-dir.
            tool_prefix: Tool ID used as the top-level repo directory prefix.
            exclude_patterns: Relative path segments to skip (e.g. "cache").

        Returns:
            List of CollectedFile instances for all files found.
        """
        results: list[CollectedFile] = []
        for entry in sorted(dir_path.rglob("*")):
            if not entry.is_file() and not entry.is_symlink():
                continue
            # Build the path relative to dir_path for exclusion checks.
            try:
                rel = entry.relative_to(dir_path)
            except ValueError:
                continue

            if self._is_excluded(rel, exclude_patterns):
                continue

            resolved_entry = self._resolve_path(entry)
            if resolved_entry is None:
                continue

            repo_path = f"{tool_prefix}/{repo_dir}{rel.as_posix()}"
            cf = self._collect_file(resolved_entry, repo_path)
            if cf is not None:
                results.append(cf)

        return results

    def _collect_file(self, path: Path, repo_path: str) -> CollectedFile | None:
        """Read a single file and return a CollectedFile.

        Args:
            path: Real (resolved) file path on the local filesystem.
            repo_path: Destination path relative to the repo root.

        Returns:
            CollectedFile instance, or None if the file cannot be read.
        """
        try:
            raw = path.read_bytes()
        except OSError as exc:
            _console.print(f"[yellow]Warning:[/yellow] could not read {path}: {exc}")
            return None

        if self._mapper.is_text_file(path):
            text = raw.decode("utf-8", errors="replace")
            abstracted = self._mapper.abstract_paths(text)
            return CollectedFile(
                repo_path=repo_path,
                content=abstracted.encode("utf-8"),
                is_binary=False,
            )

        return CollectedFile(repo_path=repo_path, content=raw, is_binary=True)

    @staticmethod
    def _is_excluded(rel: Path, exclude_patterns: list[str]) -> bool:
        """Return True if *rel* matches any of the exclude patterns.

        A pattern matches if any component of *rel* equals the pattern, or if
        the pattern appears as a prefix path segment (e.g. "plugins/cache"
        matches "plugins/cache/foo.json").

        Args:
            rel: Path relative to the directory being walked.
            exclude_patterns: List of path segments or sub-paths to exclude.

        Returns:
            True if the path should be excluded.
        """
        rel_posix = rel.as_posix()
        parts = rel.parts
        for pattern in exclude_patterns:
            # Exact component match (e.g. "cache" matches any "cache" segment).
            if pattern in parts:
                return True
            # Prefix match for multi-segment patterns (e.g. "plugins/cache").
            if rel_posix == pattern or rel_posix.startswith(pattern + "/"):
                return True
        return False

    @staticmethod
    def _get_exclude_patterns(adapter: ToolAdapter) -> list[str]:
        """Return the exclude patterns for *adapter* if it defines them.

        Adapters may expose a module-level ``EXCLUDE_PATTERNS`` list. This
        helper retrieves it without requiring the base class to declare it,
        keeping the ToolAdapter interface minimal (ISP).

        Args:
            adapter: The adapter to inspect.

        Returns:
            List of exclude pattern strings, or an empty list if none defined.
        """
        module = type(adapter).__module__
        import importlib
        mod = importlib.import_module(module)
        return getattr(mod, "EXCLUDE_PATTERNS", [])
