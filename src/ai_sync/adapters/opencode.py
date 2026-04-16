"""OpenCode tool adapter.

OpenCode stores its config at one of two locations (checked in priority order):

    1. $HOME/.opencode.json          (single-file config at home root)
    2. $XDG_CONFIG_HOME/opencode/    (usually ~/.config/opencode/)

The adapter detects which location is active at runtime and adjusts
``get_base_dir()`` and ``get_sync_items()`` accordingly.
"""



from pathlib import Path

from ai_sync.adapters.base import ToolAdapter
from ai_sync.models import SyncItem


class OpenCodeAdapter(ToolAdapter):
    """Sync adapter for OpenCode.

    Detects whether OpenCode uses the home-root config file
    (~/.opencode.json) or the XDG config directory
    (~/.config/opencode/).

    Args:
        home: Home directory of the current user. Defaults to Path.home().
    """

    def __init__(self, home: Path | None = None) -> None:
        """Initialize OpenCodeAdapter.

        Args:
            home: Home directory. Defaults to Path.home().
        """
        self._home = home or Path.home()

    @property
    def tool_id(self) -> str:
        """Return the tool identifier used as the repo sub-directory.

        Returns:
            The string ``"opencode"``.
        """
        return "opencode"

    def get_base_dir(self) -> Path:
        """Return the OpenCode config directory.

        Checks $HOME/.opencode.json first. If it exists, the base directory
        is $HOME (the config file lives directly there). Otherwise falls back
        to ~/.config/opencode/.

        Returns:
            Absolute path to the OpenCode config root.
        """
        home_config = self._home / ".opencode.json"
        if home_config.exists():
            return self._home
        return self._home / ".config" / "opencode"

    def get_sync_items(self) -> list[SyncItem]:
        """Return the sync items for OpenCode.

        All items are optional because OpenCode installations vary widely
        in which directories they create.

        Returns:
            List of SyncItem instances for all OpenCode config assets.
        """
        base = self.get_base_dir()
        return [
            SyncItem(
                local_path=base / ".opencode.json",
                repo_path=".opencode.json",
                optional=True,
            ),
            SyncItem(
                local_path=base / "agents",
                repo_path="agents/",
                is_dir=True,
                optional=True,
            ),
            SyncItem(
                local_path=base / "commands",
                repo_path="commands/",
                is_dir=True,
                optional=True,
            ),
            SyncItem(
                local_path=base / "modes",
                repo_path="modes/",
                is_dir=True,
                optional=True,
            ),
            SyncItem(
                local_path=base / "skills",
                repo_path="skills/",
                is_dir=True,
                optional=True,
            ),
            SyncItem(
                local_path=base / "tools",
                repo_path="tools/",
                is_dir=True,
                optional=True,
            ),
            SyncItem(
                local_path=base / "themes",
                repo_path="themes/",
                is_dir=True,
                optional=True,
            ),
        ]
