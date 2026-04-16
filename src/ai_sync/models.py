"""Data models and exception hierarchy for ai-sync.

This module defines all Pydantic v2 models used across the application,
as well as the custom exception hierarchy. All inter-module data exchange
uses these models — no bare dicts or tuples.
"""

from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

if sys.version_info >= (3, 11):
    from enum import StrEnum
else:
    from enum import Enum

    class StrEnum(str, Enum):  # type: ignore[no-redef]
        """Backport of StrEnum for Python < 3.11."""


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


class AppConfig(BaseModel):
    """Local ai-sync configuration stored in ~/.config/ai-sync/config.json.

    Attributes:
        github_token: Personal access token with repo scope.
        repo_url: HTTPS clone URL of the private sync repository.
    """

    github_token: str = Field(description="GitHub personal access token with repo scope")
    repo_url: str = Field(description="HTTPS clone URL of the private sync repository")


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


class GitHubAPIError(AiSyncError):
    """Raised when a GitHub API call fails.

    Args:
        message: Human-readable description of what failed.
        status_code: HTTP status code returned by the API, if available.
    """

    def __init__(self, message: str, status_code: int | None = None) -> None:
        """Initialize GitHubAPIError.

        Args:
            message: Human-readable description of what failed.
            status_code: HTTP status code returned by the API, if available.
        """
        super().__init__(message)
        self.status_code = status_code
