"""Abstract base class for tool-specific sync adapters.

Each supported AI tool (Claude Code, Gemini CLI, OpenCode, …) has its own
adapter that declares which files and directories to sync. The adapter
contains no I/O logic — it only describes *what* to sync. The FileCollector
performs the actual reading.

Adding support for a new tool requires only a new subclass of ToolAdapter;
no existing code needs to change (Open/Closed Principle).
"""



from abc import ABC, abstractmethod
from pathlib import Path

from ai_sync.models import SyncItem


class ToolAdapter(ABC):
    """Declares the sync contract for a single AI tool.

    Subclasses must implement three methods:
    - ``tool_id`` — a stable string identifier used as the directory name
      in the remote repository (e.g. ``"claude-code"``).
    - ``get_base_dir`` — the root config directory on the local filesystem.
    - ``get_sync_items`` — the list of files/directories to sync.
    """

    @property
    @abstractmethod
    def tool_id(self) -> str:
        """Stable identifier for this tool (used as the repo sub-directory).

        Returns:
            A lowercase, hyphen-separated string, e.g. ``"claude-code"``.
        """

    @abstractmethod
    def get_base_dir(self) -> Path:
        """Return the root config directory for this tool on the local machine.

        Returns:
            Absolute path to the tool's config directory.
        """

    @abstractmethod
    def get_sync_items(self) -> list[SyncItem]:
        """Return the list of files and directories to sync for this tool.

        Each item's ``local_path`` is an absolute path on the local machine.
        Its ``repo_path`` is the relative path within this tool's sub-directory
        in the remote repository.

        Items with ``optional=True`` are silently skipped when they do not
        exist on the local machine.

        Returns:
            Ordered list of SyncItem instances describing what to sync.
        """
