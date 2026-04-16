"""Shared skills adapter.

Syncs cross-tool shared asset directories that are not owned by any single
AI tool:

    ~/.skills/          → shared/skills/
    ~/.agents/skills/   → shared/agents/skills/

Both paths are optional — they are silently skipped when absent.
"""



from pathlib import Path

from ai_sync.adapters.base import ToolAdapter
from ai_sync.models import SyncItem


class SharedSkillsAdapter(ToolAdapter):
    """Sync adapter for cross-tool shared skills directories.

    Args:
        home: Home directory of the current user. Defaults to Path.home().
    """

    def __init__(self, home: Path | None = None) -> None:
        """Initialize SharedSkillsAdapter.

        Args:
            home: Home directory. Defaults to Path.home().
        """
        self._home = home or Path.home()

    @property
    def tool_id(self) -> str:
        """Return the tool identifier used as the repo sub-directory.

        Returns:
            The string ``"shared"``.
        """
        return "shared"

    def get_base_dir(self) -> Path:
        """Return the home directory (shared assets live directly under home).

        Returns:
            The user's home directory.
        """
        return self._home

    def get_sync_items(self) -> list[SyncItem]:
        """Return the sync items for shared cross-tool assets.

        Returns:
            List of SyncItem instances for ~/.skills/ and ~/.agents/skills/.
        """
        home = self._home
        return [
            SyncItem(
                local_path=home / ".skills",
                repo_path="skills/",
                is_dir=True,
                optional=True,
            ),
            SyncItem(
                local_path=home / ".agents" / "skills",
                repo_path="agents/skills/",
                is_dir=True,
                optional=True,
            ),
        ]
