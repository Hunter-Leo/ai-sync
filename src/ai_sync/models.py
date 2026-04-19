"""Data models and exception hierarchy for ai-sync.

This module defines all Pydantic v2 models used across the application,
as well as the custom exception hierarchy. All inter-module data exchange
uses these models — no bare dicts or tuples.
"""



from datetime import datetime
from enum import StrEnum
from pathlib import Path
from typing import Annotated, Literal

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class Platform(StrEnum):
    """Operating system platform identifier.

    Used to select the correct path mapping for each platform.
    """

    DARWIN = "darwin"
    LINUX = "linux"
    WINDOWS = "windows"


# ---------------------------------------------------------------------------
# Configuration models
# ---------------------------------------------------------------------------


class RemoteConfig(BaseModel):
    """Configuration for remote-hosted repository mode.

    The repository is cloned to ~/.config/ai-sync/repo/ and managed by ai-sync.
    An optional token is used for HTTPS authentication with private repositories.

    Attributes:
        mode: Discriminator field, always "remote".
        repo_url: HTTPS clone URL of the sync repository.
        token: Optional HTTPS authentication token for private repositories.
        managed_tools: Tool IDs to sync. Empty list means all known tools (backward compat).
    """

    mode: Literal["remote"] = "remote"
    repo_url: str = Field(description="HTTPS clone URL of the sync repository")
    token: str | None = Field(default=None, description="Optional HTTPS authentication token")
    managed_tools: list[str] = Field(default_factory=list, description="Tool IDs to sync; empty = all tools")


class LocalConfig(BaseModel):
    """Configuration for local repository mode.

    The user manages their own git clone and credentials. ai-sync reads and
    writes files directly in the provided directory without performing clone.

    Attributes:
        mode: Discriminator field, always "local".
        local_repo_path: Absolute path to the user-managed local git clone.
        managed_tools: Tool IDs to sync. Empty list means all known tools (backward compat).
    """

    mode: Literal["local"] = "local"
    local_repo_path: Path = Field(description="Absolute path to the local git clone")
    managed_tools: list[str] = Field(default_factory=list, description="Tool IDs to sync; empty = all tools")


AppConfig = Annotated[RemoteConfig | LocalConfig, Field(discriminator="mode")]


class Manifest(BaseModel):
    """Remote repository metadata stored in _manifest.json.

    Attributes:
        version: Schema version string (e.g. "1.0").
        last_push: UTC timestamp of the last successful push.
        source_os: Platform that performed the last push.
        source_home: Home directory placeholder used during the last push.
        tools: List of tool IDs included in the last push.
    """

    version: str = Field(default="1.0", description="Schema version")
    last_push: datetime = Field(description="UTC timestamp of the last successful push")
    source_os: Platform = Field(description="Platform that performed the last push")
    source_home: str = Field(description="Home directory placeholder (e.g. {{HOME}})")
    tools: list[str] = Field(default_factory=list, description="Tool IDs included in the last push")


# ---------------------------------------------------------------------------
# Sync item models
# ---------------------------------------------------------------------------


class SyncItem(BaseModel):
    """Describes a single file or directory to be synced for a tool.

    Attributes:
        local_path: Absolute path on the local filesystem.
        repo_path: Relative path within the tool's directory in the remote repo
            (e.g. "settings.json" or "hooks/").
        is_dir: True if this item is a directory to be recursively synced.
        optional: If True, the item is silently skipped when it does not exist.
    """

    local_path: Path = Field(description="Absolute path on the local filesystem")
    repo_path: str = Field(description="Relative path within the tool's repo directory")
    is_dir: bool = Field(default=False, description="Whether this item is a directory")
    optional: bool = Field(default=False, description="Skip silently if the path does not exist")


class CollectedFile(BaseModel):
    """A single file collected from the local filesystem, ready to write to the repo.

    Attributes:
        repo_path: Destination path relative to the repo root
            (e.g. "claude-code/settings.json").
        content: Raw file bytes. For text files, paths have already been
            abstracted by PathMapper before storage here.
        is_binary: True if the file is binary (path substitution was skipped).
    """

    repo_path: str = Field(description="Destination path relative to the repo root")
    content: bytes = Field(description="Raw file bytes (paths abstracted for text files)")
    is_binary: bool = Field(default=False, description="True if binary — path substitution was skipped")


class StatusEntry(BaseModel):
    """A single entry in the output of `ai-sync status`.

    Attributes:
        path: Repo-relative file path.
        state: Change state compared to the remote repo.
    """

    path: str = Field(description="Repo-relative file path")
    state: Literal["added", "modified", "deleted", "unchanged"] = Field(
        description="Change state compared to the remote repo"
    )


# ---------------------------------------------------------------------------
# Result models
# ---------------------------------------------------------------------------


class PushResult(BaseModel):
    """Summary returned by SyncEngine.push().

    Attributes:
        tools: Tool IDs that were pushed.
        file_count: Total number of files written to the repo.
        committed: True if a git commit was created (False if nothing changed).
    """

    tools: list[str] = Field(default_factory=list)
    file_count: int = Field(default=0)
    committed: bool = Field(default=False)


class PullResult(BaseModel):
    """Summary returned by SyncEngine.pull().

    Attributes:
        tools: Tool IDs that were restored.
        file_count: Total number of files written to the local filesystem.
    """

    tools: list[str] = Field(default_factory=list)
    file_count: int = Field(default=0)


# ---------------------------------------------------------------------------
# Exception hierarchy
# ---------------------------------------------------------------------------


class AiSyncError(Exception):
    """Base exception for all ai-sync domain errors.

    Catch this in the CLI layer to display a friendly message and exit
    with a non-zero status code.
    """


class ConfigNotFoundError(AiSyncError):
    """Raised when ~/.config/ai-sync/config.json does not exist.

    The user should run `ai-sync init` to create it.
    """


class RepoNotInitializedError(AiSyncError):
    """Raised when the local git clone does not exist.

    The user should run `ai-sync init` to clone the repository.
    """


class GitOperationError(AiSyncError):
    """Raised when a git operation (clone, pull, push) fails.

    Args:
        message: Human-readable description of what failed.
        original: The underlying exception from gitpython, if any.
    """

    def __init__(self, message: str, original: Exception | None = None) -> None:
        """Initialize GitOperationError.

        Args:
            message: Human-readable description of what failed.
            original: The underlying exception from gitpython, if any.
        """
        super().__init__(message)
        self.original = original
