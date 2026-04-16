"""Claude Code tool adapter.

Declares the files and directories under ~/.claude/ that should be synced.
Sensitive and machine-local paths (sessions, history, cache, etc.) are
excluded by the FileCollector based on the exclude_patterns list.
"""



from pathlib import Path

from ai_sync.adapters.base import ToolAdapter
from ai_sync.models import SyncItem

# Paths inside ~/.claude/ that must never be synced.
EXCLUDE_PATTERNS: list[str] = [
    "sessions",
    "history.jsonl",
    "tasks",
    "plans",
    "plugins/cache",
    "cache",
    "debug",
]


class ClaudeCodeAdapter(ToolAdapter):
    """Sync adapter for Claude Code (~/.claude/).

    Args:
        home: Home directory of the current user. Defaults to Path.home().
    """

    def __init__(self, home: Path | None = None) -> None:
        """Initialize ClaudeCodeAdapter.

        Args:
            home: Home directory. Defaults to Path.home().
        """
        self._home = home or Path.home()

    @property
    def tool_id(self) -> str:
        """Return the tool identifier used as the repo sub-directory.

        Returns:
            The string ``"claude-code"``.
        """
        return "claude-code"

    def get_base_dir(self) -> Path:
        """Return the Claude Code config directory (~/.claude).

        Returns:
            Absolute path to ~/.claude.
        """
        return self._home / ".claude"

    def get_sync_items(self) -> list[SyncItem]:
        """Return the sync items for Claude Code.

        Returns:
            List of SyncItem instances for all Claude Code config assets.
        """
        base = self.get_base_dir()
        return [
            SyncItem(local_path=base / "settings.json", repo_path="settings.json"),
            SyncItem(local_path=base / "CLAUDE.md", repo_path="CLAUDE.md"),
            SyncItem(local_path=base / "hooks", repo_path="hooks/", is_dir=True),
            SyncItem(local_path=base / "skills", repo_path="skills/", is_dir=True),
            SyncItem(
                local_path=base / "agents",
                repo_path="agents/",
                is_dir=True,
                optional=True,
            ),
            SyncItem(
                local_path=base / "plugins" / "installed_plugins.json",
                repo_path="plugins/installed_plugins.json",
                optional=True,
            ),
            SyncItem(
                local_path=base / "keybindings.json",
                repo_path="keybindings.json",
                optional=True,
            ),
        ]
