"""ManifestManager — reads and writes _manifest.json in the sync repository.

The manifest records metadata about the last push so that pull operations
can detect cross-platform differences and display useful status information.
"""

import json
from pathlib import Path

from ai_sync.models import AiSyncError, Manifest

_MANIFEST_FILENAME = "_manifest.json"


class ManifestManager:
    """Manages the _manifest.json file at the root of the sync repository.

    Args:
        repo_dir: Root directory of the local git clone.
    """

    def __init__(self, repo_dir: Path) -> None:
        """Initialize ManifestManager.

        Args:
            repo_dir: Root directory of the local git clone.
        """
        self._path = repo_dir / _MANIFEST_FILENAME

    def read(self) -> Manifest | None:
        """Read and return the manifest, or None if it does not exist yet.

        Returns:
            Parsed Manifest instance, or None if _manifest.json is absent.

        Raises:
            AiSyncError: If the file exists but contains invalid JSON or
                fails Pydantic validation.
        """
        if not self._path.is_file():
            return None
        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise AiSyncError(
                f"Manifest file contains invalid JSON: {self._path}\n{exc}"
            ) from exc
        return Manifest.model_validate(data)

    def write(self, manifest: Manifest) -> None:
        """Write the manifest to _manifest.json.

        Creates parent directories if they do not exist.

        Args:
            manifest: Manifest instance to persist.
        """
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(
            manifest.model_dump_json(indent=2),
            encoding="utf-8",
        )
