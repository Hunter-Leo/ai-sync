"""Unit tests for ai_sync.github_client."""

from unittest.mock import MagicMock, patch

import pytest
from github import GithubException

from ai_sync.github_client import GitHubClient
from ai_sync.models import GitHubAPIError


@pytest.fixture
def mock_gh() -> MagicMock:
    return MagicMock()


@pytest.fixture
def client(mock_gh: MagicMock) -> GitHubClient:
    with patch("ai_sync.github_client.Github", return_value=mock_gh):
        return GitHubClient(token="ghp_test")


class TestCreatePrivateRepo:
    def test_returns_clone_url(self, client: GitHubClient, mock_gh: MagicMock) -> None:
        mock_repo = MagicMock()
        mock_repo.clone_url = "https://github.com/user/ai-sync-config.git"
        mock_gh.get_user.return_value.create_repo.return_value = mock_repo

        url = client.create_private_repo("ai-sync-config")
        assert url == "https://github.com/user/ai-sync-config.git"

    def test_creates_private_repo(self, client: GitHubClient, mock_gh: MagicMock) -> None:
        mock_repo = MagicMock()
        mock_repo.clone_url = "https://github.com/user/repo.git"
        mock_gh.get_user.return_value.create_repo.return_value = mock_repo

        client.create_private_repo("repo")
        mock_gh.get_user.return_value.create_repo.assert_called_once_with(
            "repo", private=True, auto_init=True
        )

    def test_raises_on_already_exists(self, client: GitHubClient, mock_gh: MagicMock) -> None:
        exc = GithubException(422, {"message": "already exists"}, None)
        mock_gh.get_user.return_value.create_repo.side_effect = exc

        with pytest.raises(GitHubAPIError, match="already exists") as exc_info:
            client.create_private_repo("repo")
        assert exc_info.value.status_code == 422

    def test_raises_on_api_error(self, client: GitHubClient, mock_gh: MagicMock) -> None:
        exc = GithubException(500, {"message": "server error"}, None)
        mock_gh.get_user.return_value.create_repo.side_effect = exc

        with pytest.raises(GitHubAPIError) as exc_info:
            client.create_private_repo("repo")
        assert exc_info.value.status_code == 500


class TestRepoExists:
    def test_returns_true_when_accessible(self, client: GitHubClient, mock_gh: MagicMock) -> None:
        mock_gh.get_repo.return_value = MagicMock()
        assert client.repo_exists("https://github.com/user/repo.git") is True

    def test_returns_false_on_404(self, client: GitHubClient, mock_gh: MagicMock) -> None:
        mock_gh.get_repo.side_effect = GithubException(404, {"message": "Not Found"}, None)
        assert client.repo_exists("https://github.com/user/repo.git") is False

    def test_raises_on_unexpected_error(self, client: GitHubClient, mock_gh: MagicMock) -> None:
        mock_gh.get_repo.side_effect = GithubException(403, {"message": "Forbidden"}, None)
        with pytest.raises(GitHubAPIError) as exc_info:
            client.repo_exists("https://github.com/user/repo.git")
        assert exc_info.value.status_code == 403

    def test_parses_url_correctly(self, client: GitHubClient, mock_gh: MagicMock) -> None:
        mock_gh.get_repo.return_value = MagicMock()
        client.repo_exists("https://github.com/myorg/my-repo.git")
        mock_gh.get_repo.assert_called_once_with("myorg/my-repo")

    def test_raises_on_invalid_url(self, client: GitHubClient) -> None:
        with pytest.raises(GitHubAPIError, match="Cannot parse"):
            client.repo_exists("not-a-url")
