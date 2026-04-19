"""ConfigStore — reads and writes the local ai-sync configuration file.

The configuration file lives at ~/.config/ai-sync/config.json and stores
the GitHub token and remote repository URL. This module is the single
point of access for that file.
"""



import json
import os
from pathlib import Path

from ai_sync.models import AppConfig, ConfigNotFoundError

_DEFAULT_CONFIG_PATH = Path.home() / ".config" / "ai-sync" / "config.json"


class ConfigStore:
    """Manages reading and writing ~/.config/ai-sync/config.json.

    Args:
        config_path: Path to the config file. Defaults to
            ~/.config/ai-sync/config.json.
    """

    def __init__(self, config_path: Path = _DEFAULT_CONFIG_PATH) -> None:
        """Initialize ConfigStore.

        Args:
            config_path: Path to the config file.
        """
        self._path = config_path

    def exists(self) -> bool:
        """Return True if the config file exists.

        Returns:
            True if the config file exists on disk.
        """
        return self._path.is_file()

    def load(self) -> AppConfig:
        """Load and return the application configuration.

        Returns:
            Parsed AppConfig instance.

        Raises:
            ConfigNotFoundError: If the config file does not exist.
            AiSyncError: If the file contains invalid JSON or missing fields.
        """
        if not self._path.is_file():
            raise ConfigNotFoundError(
                f"Config file not found: {self._path}\n"
                "Run `ai-sync init` to create it."
            )
        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            from ai_sync.models import AiSyncError
            raise AiSyncError(
                f"Config file contains invalid JSON: {self._path}\n{exc}"
            ) from exc
        return AppConfig.model_validate(data)

    def save(self, config: AppConfig) -> None:
        """Write the configuration to disk.

        Creates parent directories if they do not exist.

        Args:
            config: AppConfig instance to persist.
        """
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(
            json.dumps(config.model_dump(), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        os.chmod(self._path, 0o600)
