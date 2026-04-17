"""GitHubClient — GitHub API wrapper for repository management.

Handles creating private repositories and checking their existence via
PyGithub. All API errors are translated into GitHubAPIError so callers
never need to import PyGithub directly.
"""

from pathlib import PurePosixPath
from urllib.parse import urlparse

from github import Github, GithubException

from ai_sync.models import GitHubAPIError


class GitHubClient:
    """Wraps PyGithub for the operations needed by ai-sync.

    Args:
        token: GitHub personal access token with repo scope.
    """

    def __init__(self, token: str) -> None:
        """Initialize GitHubClient.

        Args:
            token: GitHub personal access token with repo scope.
        """
        self._gh = Github(token)

    def create_private_repo(self, name: str) -> str:
        """Create a new private repository for the authenticated user.

        Args:
            name: Repository name (without owner prefix).

        Returns:
            HTTPS clone URL of the newly created repository.

        Raises:
            GitHubAPIError: If the repository already exists or the API call
                fails for any other reason.
        """
        try:
            user = self._gh.get_user()
            repo = user.create_repo(name, private=True, auto_init=True)
            return repo.clone_url
        except GithubException as exc:
            status = exc.status
            if status == 422:
                raise GitHubAPIError(
                    f"Repository '{name}' already exists on GitHub. "
                    "Use `ai-sync init` with an existing repo URL instead.",
                    status_code=status,
                ) from exc
            raise GitHubAPIError(
                f"Failed to create repository '{name}': {exc.data}",
                status_code=status,
            ) from exc

    def repo_exists(self, repo_url: str) -> bool:
        """Check whether a repository exists and is accessible with the current token.

        Args:
            repo_url: HTTPS clone URL of the repository
                (e.g. "https://github.com/owner/repo.git").

        Returns:
            True if the repository exists and is accessible, False otherwise.

        Raises:
            GitHubAPIError: If the URL cannot be parsed or an unexpected API
                error occurs (not a 404).
        """
        owner, repo_name = self._parse_repo_url(repo_url)
        try:
            self._gh.get_repo(f"{owner}/{repo_name}")
            return True
        except GithubException as exc:
            if exc.status == 404:
                return False
            raise GitHubAPIError(
                f"Failed to check repository '{owner}/{repo_name}': {exc.data}",
                status_code=exc.status,
            ) from exc

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_repo_url(repo_url: str) -> tuple[str, str]:
        """Parse a GitHub HTTPS clone URL into (owner, repo_name).

        Args:
            repo_url: HTTPS clone URL, e.g. "https://github.com/owner/repo.git".

        Returns:
            Tuple of (owner, repo_name).

        Raises:
            GitHubAPIError: If the URL cannot be parsed into owner/repo.
        """
        try:
            path = urlparse(repo_url).path.lstrip("/")
            parts = PurePosixPath(path).parts
            if len(parts) < 2:
                raise ValueError("not enough path segments")
            owner = parts[0]
            repo_name = parts[1].removesuffix(".git")
            return owner, repo_name
        except (ValueError, IndexError) as exc:
            raise GitHubAPIError(
                f"Cannot parse GitHub repository URL: {repo_url!r}"
            ) from exc
