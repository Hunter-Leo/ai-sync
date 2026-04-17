"""GitRepo — git operations wrapper using gitpython.

Encapsulates clone, pull, push, and diff operations for the local sync
repository at ~/.config/ai-sync/repo/. All git errors are translated into
GitOperationError so callers never need to import gitpython directly.
"""

from pathlib import Path

import git
from git.exc import GitCommandError, InvalidGitRepositoryError

from ai_sync.models import GitOperationError, RepoNotInitializedError


class GitRepo:
    """Manages the local git clone of the remote sync repository.

    Args:
        repo_dir: Local directory where the repository is (or will be) cloned.
        remote_url: HTTPS URL of the remote repository.
    """

    def __init__(self, repo_dir: Path, remote_url: str) -> None:
        """Initialize GitRepo.

        Args:
            repo_dir: Local directory for the git clone.
            remote_url: HTTPS clone URL of the remote repository.
        """
        self._repo_dir = repo_dir
        self._remote_url = remote_url

    def is_cloned(self) -> bool:
        """Return True if the repository has already been cloned locally.

        Returns:
            True if repo_dir contains a valid git repository.
        """
        try:
            git.Repo(self._repo_dir)
            return True
        except (InvalidGitRepositoryError, git.NoSuchPathError):
            return False

    def clone(self) -> None:
        """Clone the remote repository into repo_dir.

        If the repository is already cloned, this is a no-op.

        Raises:
            GitOperationError: If the clone fails.
        """
        if self.is_cloned():
            return
        try:
            self._repo_dir.mkdir(parents=True, exist_ok=True)
            git.Repo.clone_from(self._remote_url, self._repo_dir)
        except GitCommandError as exc:
            raise GitOperationError(
                f"Failed to clone {self._remote_url}: {exc}", original=exc
            ) from exc

    def pull(self) -> None:
        """Pull the latest changes from the remote repository.

        Raises:
            RepoNotInitializedError: If the repository has not been cloned yet.
            GitOperationError: If the pull fails.
        """
        repo = self._get_repo()
        try:
            origin = repo.remotes.origin
            origin.pull()
        except GitCommandError as exc:
            raise GitOperationError(
                f"Failed to pull from remote: {exc}", original=exc
            ) from exc

    def push(self, commit_message: str) -> bool:
        """Stage all changes, commit, and push to the remote repository.

        If there are no changes to commit, the push is skipped and False is
        returned.

        Args:
            commit_message: The git commit message.

        Returns:
            True if a commit was created and pushed, False if nothing changed.

        Raises:
            RepoNotInitializedError: If the repository has not been cloned yet.
            GitOperationError: If the commit or push fails.
        """
        repo = self._get_repo()
        try:
            repo.git.add(A=True)
            if not repo.is_dirty(index=True, untracked_files=True):
                return False
            repo.index.commit(commit_message)
            repo.remotes.origin.push()
            return True
        except GitCommandError as exc:
            raise GitOperationError(
                f"Failed to push to remote: {exc}", original=exc
            ) from exc

    def diff_files(self) -> list[str]:
        """Return a list of files that differ from the last commit.

        Includes staged changes, unstaged changes, and untracked files.

        Returns:
            List of file paths (relative to repo root) that have changed.

        Raises:
            RepoNotInitializedError: If the repository has not been cloned yet.
        """
        repo = self._get_repo()
        changed: set[str] = set()

        # Staged and unstaged changes vs HEAD.
        if repo.head.is_valid():
            for diff in repo.head.commit.diff(None):
                if diff.a_path:
                    changed.add(diff.a_path)
                if diff.b_path:
                    changed.add(diff.b_path)

        # Untracked files.
        changed.update(repo.untracked_files)

        return sorted(changed)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_repo(self) -> git.Repo:
        """Return the gitpython Repo object, raising if not yet cloned.

        Returns:
            A gitpython Repo instance for repo_dir.

        Raises:
            RepoNotInitializedError: If the repository has not been cloned yet.
        """
        try:
            return git.Repo(self._repo_dir)
        except (InvalidGitRepositoryError, git.NoSuchPathError) as exc:
            raise RepoNotInitializedError(
                f"Repository not found at {self._repo_dir}.\n"
                "Run `ai-sync init` to clone the repository."
            ) from exc
