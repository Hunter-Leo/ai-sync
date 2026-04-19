"""Unit tests for ai_sync.git_repo."""

from pathlib import Path

import git
import pytest

from ai_sync.git_repo import GitRepo
from ai_sync.models import GitOperationError, RepoNotInitializedError


@pytest.fixture
def bare_remote(tmp_path: Path) -> Path:
    """Create a bare git repository to act as the remote."""
    remote = tmp_path / "remote.git"
    git.Repo.init(remote, bare=True)
    return remote


@pytest.fixture
def seeded_remote(tmp_path: Path) -> Path:
    """Create a bare remote with an initial commit."""
    remote = tmp_path / "remote.git"
    git.Repo.init(remote, bare=True)

    # Create a temporary working copy to seed the remote.
    seed = tmp_path / "seed"
    seed.mkdir()
    repo = git.Repo.init(seed)
    repo.config_writer().set_value("user", "name", "Test").release()
    repo.config_writer().set_value("user", "email", "test@test.com").release()
    (seed / "README.md").write_text("init", encoding="utf-8")
    repo.index.add(["README.md"])
    repo.index.commit("init")
    repo.create_remote("origin", str(remote))
    repo.remotes.origin.push(refspec="HEAD:refs/heads/main")
    return remote


class TestIsCloned:
    def test_false_when_dir_missing(self, tmp_path: Path, seeded_remote: Path) -> None:
        gr = GitRepo(repo_dir=tmp_path / "repo", remote_url=str(seeded_remote))
        assert gr.is_cloned() is False

    def test_true_after_clone(self, tmp_path: Path, seeded_remote: Path) -> None:
        repo_dir = tmp_path / "repo"
        gr = GitRepo(repo_dir=repo_dir, remote_url=str(seeded_remote))
        gr.clone()
        assert gr.is_cloned() is True


class TestClone:
    def test_clones_successfully(self, tmp_path: Path, seeded_remote: Path) -> None:
        repo_dir = tmp_path / "repo"
        gr = GitRepo(repo_dir=repo_dir, remote_url=str(seeded_remote))
        gr.clone()
        assert (repo_dir / "README.md").exists()

    def test_clone_is_noop_if_already_cloned(self, tmp_path: Path, seeded_remote: Path) -> None:
        repo_dir = tmp_path / "repo"
        gr = GitRepo(repo_dir=repo_dir, remote_url=str(seeded_remote))
        gr.clone()
        # Second call should not raise.
        gr.clone()
        assert gr.is_cloned() is True

    def test_clone_invalid_url_raises(self, tmp_path: Path) -> None:
        gr = GitRepo(repo_dir=tmp_path / "repo", remote_url="/nonexistent/path.git")
        with pytest.raises(GitOperationError):
            gr.clone()


class TestPull:
    def test_pull_raises_when_not_cloned(self, tmp_path: Path, seeded_remote: Path) -> None:
        gr = GitRepo(repo_dir=tmp_path / "repo", remote_url=str(seeded_remote))
        with pytest.raises(RepoNotInitializedError):
            gr.pull()

    def test_pull_fetches_new_commits(self, tmp_path: Path, seeded_remote: Path) -> None:
        repo_dir = tmp_path / "repo"
        gr = GitRepo(repo_dir=repo_dir, remote_url=str(seeded_remote))
        gr.clone()

        # Push a new commit to the remote directly.
        seed = tmp_path / "seed2"
        seed.mkdir()
        r = git.Repo.clone_from(str(seeded_remote), seed)
        r.config_writer().set_value("user", "name", "Test").release()
        r.config_writer().set_value("user", "email", "test@test.com").release()
        (seed / "new_file.txt").write_text("hello", encoding="utf-8")
        r.index.add(["new_file.txt"])
        r.index.commit("add new_file")
        r.remotes.origin.push()

        gr.pull()
        assert (repo_dir / "new_file.txt").exists()


class TestPush:
    def test_push_returns_false_when_nothing_changed(
        self, tmp_path: Path, seeded_remote: Path
    ) -> None:
        repo_dir = tmp_path / "repo"
        gr = GitRepo(repo_dir=repo_dir, remote_url=str(seeded_remote))
        gr.clone()
        # Configure git user for commits.
        repo = git.Repo(repo_dir)
        repo.config_writer().set_value("user", "name", "Test").release()
        repo.config_writer().set_value("user", "email", "test@test.com").release()
        result = gr.push("no changes")
        assert result is False

    def test_push_commits_and_returns_true(self, tmp_path: Path, seeded_remote: Path) -> None:
        repo_dir = tmp_path / "repo"
        gr = GitRepo(repo_dir=repo_dir, remote_url=str(seeded_remote))
        gr.clone()
        repo = git.Repo(repo_dir)
        repo.config_writer().set_value("user", "name", "Test").release()
        repo.config_writer().set_value("user", "email", "test@test.com").release()

        (repo_dir / "config.json").write_text('{"key": "val"}', encoding="utf-8")
        result = gr.push("add config")
        assert result is True

    def test_push_raises_when_not_cloned(self, tmp_path: Path, seeded_remote: Path) -> None:
        gr = GitRepo(repo_dir=tmp_path / "repo", remote_url=str(seeded_remote))
        with pytest.raises(RepoNotInitializedError):
            gr.push("msg")


class TestDiffFiles:
    def test_returns_empty_when_clean(self, tmp_path: Path, seeded_remote: Path) -> None:
        repo_dir = tmp_path / "repo"
        gr = GitRepo(repo_dir=repo_dir, remote_url=str(seeded_remote))
        gr.clone()
        assert gr.diff_files() == []

    def test_returns_untracked_files(self, tmp_path: Path, seeded_remote: Path) -> None:
        repo_dir = tmp_path / "repo"
        gr = GitRepo(repo_dir=repo_dir, remote_url=str(seeded_remote))
        gr.clone()
        (repo_dir / "new.json").write_text("{}", encoding="utf-8")
        assert "new.json" in gr.diff_files()

    def test_raises_when_not_cloned(self, tmp_path: Path, seeded_remote: Path) -> None:
        gr = GitRepo(repo_dir=tmp_path / "repo", remote_url=str(seeded_remote))
        with pytest.raises(RepoNotInitializedError):
            gr.diff_files()


class TestLocalMode:
    """Tests for GitRepo with remote_url=None (local mode)."""

    @pytest.fixture
    def local_repo(self, tmp_path: Path, seeded_remote: Path) -> Path:
        """Clone a repo locally to simulate a user-managed clone."""
        repo_dir = tmp_path / "local_clone"
        git.Repo.clone_from(str(seeded_remote), repo_dir)
        repo = git.Repo(repo_dir)
        repo.config_writer().set_value("user", "name", "Test").release()
        repo.config_writer().set_value("user", "email", "test@test.com").release()
        return repo_dir

    def test_clone_is_noop_when_remote_url_none(self, tmp_path: Path) -> None:
        """clone() must not raise and must not create any files when remote_url is None."""
        repo_dir = tmp_path / "nonexistent"
        gr = GitRepo(repo_dir=repo_dir, remote_url=None)
        gr.clone()  # should not raise
        assert not repo_dir.exists()

    def test_is_cloned_false_when_dir_missing(self, tmp_path: Path) -> None:
        gr = GitRepo(repo_dir=tmp_path / "nonexistent", remote_url=None)
        assert gr.is_cloned() is False

    def test_push_works_on_local_repo(self, tmp_path: Path, local_repo: Path) -> None:
        gr = GitRepo(repo_dir=local_repo, remote_url=None)
        (local_repo / "new.json").write_text("{}", encoding="utf-8")
        result = gr.push("add new.json")
        assert result is True

    def test_pull_works_on_local_repo(
        self, tmp_path: Path, seeded_remote: Path, local_repo: Path
    ) -> None:
        # Push a new commit to the remote from a separate clone.
        other = tmp_path / "other"
        r = git.Repo.clone_from(str(seeded_remote), other)
        r.config_writer().set_value("user", "name", "Test").release()
        r.config_writer().set_value("user", "email", "test@test.com").release()
        (other / "extra.txt").write_text("hi", encoding="utf-8")
        r.index.add(["extra.txt"])
        r.index.commit("add extra")
        r.remotes.origin.push()

        gr = GitRepo(repo_dir=local_repo, remote_url=None)
        gr.pull()
        assert (local_repo / "extra.txt").exists()
