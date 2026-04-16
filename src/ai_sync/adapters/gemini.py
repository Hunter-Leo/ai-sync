"""Gemini CLI tool adapter.

Declares the files and directories under ~/.gemini/ that should be synced.
OAuth tokens, account credentials, and machine-local history are excluded.
"""



from pathlib import Path

from ai_sync.adapters.base import ToolAdapter
from ai_sync.models import SyncItem

# Paths inside ~/.gemini/ that must never be synced.
EXCLUDE_PATTERNS: list[str] = [
    "oauth_creds.json",
    "google_accounts.json",
    "history",
    "antigravity-browser-profile",
    "mcp-oauth-tokens.json",
    "a2a-oauth-tokens.json",
    "installation_id",
]


class GeminiAdapter(ToolAdapter):
    """Sync adapter for Gemini CLI (~/.gemini/).

    Args:
        home: Home directory of the current user. Defaults to Path.home().
    """

    def __init__(self, home: Path | None = None) -> None:
        """Initialize GeminiAdapter.

        Args:
            home: Home directory. Defaults to Path.home().
        """
        self._home = home or Path.home()

    @property
    def tool_id(self) -> str:
        """Return the tool identifier used as the repo sub-directory.

        Returns:
            The string ``"gemini"``.
        """
        return "gemini"

    def get_base_dir(self) -> Path:
        """Return the Gemini CLI config directory (~/.gemini).

        Returns:
            Absolute path to ~/.gemini.
        """
        return self._home / ".gemini"

    def get_sync_items(self) -> list[SyncItem]:
        """Return the sync items for Gemini CLI.

        Returns:
            List of SyncItem instances for all Gemini CLI config assets.
        """
        base = self.get_base_dir()
        return [
            SyncItem(local_path=base / "settings.json", repo_path="settings.json"),
            SyncItem(local_path=base / "GEMINI.md", repo_path="GEMINI.md"),
            SyncItem(
                local_path=base / "commands",
                repo_path="commands/",
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
                local_path=base / "memory.md",
                repo_path="memory.md",
                optional=True,
            ),
            SyncItem(
                local_path=base / "policies",
                repo_path="policies/",
                is_dir=True,
                optional=True,
            ),
        ]
