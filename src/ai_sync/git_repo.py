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
    """Manages the local git clone of the sync repository.

    Supports two modes:
    - Remote mode: ``remote_url`` is provided; ``clone()`` fetches from the URL.
    - Local mode: ``remote_url`` is None; ``clone()`` is a no-op and the caller
      is responsible for providing a valid git repository at ``repo_dir``.

    Args:
        repo_dir: Local directory where the repository is (or will be) cloned.
        remote_url: HTTPS URL of the remote repository, or None for local mode.
    """

    def __init__(self, repo_dir: Path, remote_url: str | None = None) -> None:
        """Initialize GitRepo.

        Args:
            repo_dir: Local directory for the git clone.
            remote_url: HTTPS clone URL of the remote repository, or None to
                skip cloning (local mode).
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

        If ``remote_url`` is None (local mode), this method is a no-op.
        If the repository is already cloned, this is also a no-op.

        Raises:
            GitOperationError: If the clone fails.
        """
        if self._remote_url is None:
            return
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

    def fetch(self) -> None:
        """Fetch from the remote origin without modifying the working tree.

        In local mode (remote_url is None) or if the fetch fails (e.g. no
        network), this method is a silent no-op — callers should not rely on
        the result being up-to-date.
        """
        if self._remote_url is None:
            return
        try:
            repo = self._get_repo()
            repo.remotes.origin.fetch()
        except Exception:  # noqa: BLE001 — intentionally silent
            pass

    def commits_behind(self) -> int:
        """Return how many commits origin/main is ahead of the local HEAD.

        Fetches are not performed here — call fetch() first if needed.
        Returns 0 if the remote tracking branch does not exist or the repo
        is not initialized.

        Returns:
            Number of commits the local clone is behind origin/main.
        """
        try:
            repo = self._get_repo()
            local = repo.head.commit
            remote_ref = repo.remotes.origin.refs["main"]
            count = sum(1 for _ in repo.iter_commits(f"{local}..{remote_ref}"))
            return count
        except Exception:  # noqa: BLE001 — remote ref may not exist
            return 0

    def checkout_or_create_branch(self, name: str) -> None:
        """Switch to a branch, creating it if it does not exist.

        Args:
            name: Branch name (e.g. "backup/host-darwin").

        Raises:
            RepoNotInitializedError: If the repository has not been cloned.
            GitOperationError: If the git operation fails.
        """
        repo = self._get_repo()
        try:
            if name in [h.name for h in repo.heads]:
                repo.heads[name].checkout()
            else:
                repo.create_head(name).checkout()
        except GitCommandError as exc:
            raise GitOperationError(
                f"Failed to checkout/create branch {name}: {exc}", original=exc
            ) from exc

    def commit_all(self, message: str) -> bool:
        """Stage all changes and create a commit.

        Args:
            message: Commit message.

        Returns:
            True if a commit was created, False if there was nothing to commit.

        Raises:
            RepoNotInitializedError: If the repository has not been cloned.
            GitOperationError: If the commit fails.
        """
        repo = self._get_repo()
        try:
            repo.git.add(A=True)
            if not repo.is_dirty(index=True, untracked_files=True):
                return False
            repo.index.commit(message)
            return True
        except GitCommandError as exc:
            raise GitOperationError(
                f"Failed to commit: {exc}", original=exc
            ) from exc

    def sync_remote_url(self) -> None:
        """Update the local clone's remote URL to match the current remote_url.

        Call this after loading config to ensure the embedded token stays in
        sync with config.json. In local mode (remote_url is None) or when the
        repo is not yet cloned, this is a no-op.
        """
        if self._remote_url is None or not self.is_cloned():
            return
        try:
            repo = self._get_repo()
            repo.remotes.origin.set_url(self._remote_url)
        except GitCommandError as exc:
            raise GitOperationError(
                f"Failed to update remote URL: {exc}", original=exc
            ) from exc

    def push_branch(self, name: str) -> None:
        """Push a branch to the remote origin.

        In local mode (remote_url is None), this method is a no-op.

        Args:
            name: Branch name to push.

        Raises:
            RepoNotInitializedError: If the repository has not been cloned.
            GitOperationError: If the push fails.
        """
        if self._remote_url is None:
            return
        repo = self._get_repo()
        try:
            repo.remotes.origin.push(refspec=f"{name}:{name}")
        except GitCommandError as exc:
            raise GitOperationError(
                f"Failed to push branch {name}: {exc}", original=exc
            ) from exc

    def checkout_branch(self, name: str) -> None:
        """Switch to an existing branch.

        Args:
            name: Branch name to switch to.

        Raises:
            RepoNotInitializedError: If the repository has not been cloned.
            GitOperationError: If the branch does not exist or checkout fails.
        """
        repo = self._get_repo()
        try:
            repo.heads[name].checkout()
        except (GitCommandError, IndexError) as exc:
            raise GitOperationError(
                f"Failed to checkout branch {name}: {exc}", original=exc
            ) from exc

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
