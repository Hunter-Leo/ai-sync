"""CLI entry point for ai-sync.

Defines the four user-facing commands (init, push, pull, status) using typer.
This module is responsible for:
- Assembling all dependencies (ConfigStore, GitRepo, adapters, SyncEngine, …)
- Calling the appropriate SyncEngine method
- Catching AiSyncError subclasses and displaying friendly error messages
- Exiting with a non-zero status code on failure
"""

import sys
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from ai_sync.adapters.claude_code import ClaudeCodeAdapter
from ai_sync.adapters.gemini import GeminiAdapter
from ai_sync.adapters.opencode import OpenCodeAdapter
from ai_sync.adapters.shared_skills import SharedSkillsAdapter
from ai_sync.config_store import ConfigStore
from ai_sync.file_collector import FileCollector
from ai_sync.git_repo import GitRepo
from ai_sync.github_client import GitHubClient
from ai_sync.manifest import ManifestManager
from ai_sync.models import AppConfig, AiSyncError, Platform
from ai_sync.path_mapper import PathMapper
from ai_sync.sync_engine import SyncEngine

app = typer.Typer(
    name="ai-sync",
    help="Sync AI coding assistant configs across machines.",
    no_args_is_help=True,
)

_console = Console()
_err_console = Console(stderr=True)

_DEFAULT_CONFIG_DIR = Path.home() / ".config" / "ai-sync"
_DEFAULT_REPO_DIR = _DEFAULT_CONFIG_DIR / "repo"


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------


@app.command()
def init() -> None:
    """Configure GitHub Token and repository, then clone it locally."""
    _console.print("[bold]ai-sync init[/bold]")

    store = ConfigStore(config_path=_DEFAULT_CONFIG_DIR / "config.json")

    if store.exists():
        overwrite = typer.confirm(
            "Config already exists. Overwrite?", default=False
        )
        if not overwrite:
            _console.print("Aborted.")
            raise typer.Exit()

    token = typer.prompt("GitHub personal access token (repo scope)")

    create_new = typer.confirm("Create a new private repository on GitHub?", default=True)

    if create_new:
        repo_name = typer.prompt("Repository name", default="ai-sync-config")
        try:
            gh = GitHubClient(token=token)
            repo_url = gh.create_private_repo(repo_name)
            _console.print(f"[green]Created:[/green] {repo_url}")
        except AiSyncError as exc:
            _err_console.print(f"[red]Error:[/red] {exc}")
            raise typer.Exit(code=1) from exc
    else:
        repo_url = typer.prompt(
            "Repository HTTPS clone URL",
            default="https://github.com/you/ai-sync-config.git",
        )

    config = AppConfig(github_token=token, repo_url=repo_url)
    store.save(config)
    _console.print(f"[green]Config saved:[/green] {store._path}")

    _console.print("Cloning repository…")
    try:
        git_repo = GitRepo(repo_dir=_DEFAULT_REPO_DIR, remote_url=repo_url)
        git_repo.clone()
        _console.print(f"[green]Cloned to:[/green] {_DEFAULT_REPO_DIR}")
    except AiSyncError as exc:
        _err_console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(code=1) from exc


@app.command()
def push() -> None:
    """Read local configs and push to the remote repository."""
    try:
        engine = _build_engine()
        _console.print("Collecting local configs…")
        result = engine.push()
    except AiSyncError as exc:
        _err_console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(code=1) from exc

    if result.committed:
        _console.print(
            f"[green]Pushed[/green] {result.file_count} file(s) "
            f"from {len(result.tools)} tool(s): {', '.join(result.tools)}"
        )
    else:
        _console.print("[yellow]Nothing to push — no changes detected.[/yellow]")


@app.command()
def pull() -> None:
    """Pull configs from the remote repository and restore them locally."""
    try:
        engine = _build_engine()
        _console.print("Pulling from remote…")
        result = engine.pull()
    except AiSyncError as exc:
        _err_console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(code=1) from exc

    _console.print(
        f"[green]Restored[/green] {result.file_count} file(s) "
        f"for {len(result.tools)} tool(s): {', '.join(result.tools)}"
    )


@app.command()
def status() -> None:
    """Show the diff between local configs and the remote repository."""
    try:
        engine = _build_engine()
        entries = engine.status()
    except AiSyncError as exc:
        _err_console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(code=1) from exc

    if not entries:
        _console.print("[green]Everything is in sync.[/green]")
        return

    table = Table(title="ai-sync status", show_header=True, header_style="bold")
    table.add_column("State", style="cyan", width=12)
    table.add_column("Path")

    state_colors = {
        "added": "green",
        "modified": "yellow",
        "deleted": "red",
        "unchanged": "dim",
    }

    for entry in entries:
        color = state_colors.get(entry.state, "white")
        table.add_row(f"[{color}]{entry.state}[/{color}]", entry.path)

    _console.print(table)


# ---------------------------------------------------------------------------
# Dependency assembly
# ---------------------------------------------------------------------------


def _build_engine() -> SyncEngine:
    """Assemble and return a fully configured SyncEngine.

    Reads the local config, detects the current platform, and wires together
    all components. Called by push, pull, and status commands.

    Returns:
        A ready-to-use SyncEngine instance.

    Raises:
        ConfigNotFoundError: If config.json does not exist.
        RepoNotInitializedError: If the local clone does not exist.
    """
    store = ConfigStore(config_path=_DEFAULT_CONFIG_DIR / "config.json")
    config = store.load()

    home = Path.home()
    platform = _detect_platform()
    mapper = PathMapper(platform=platform, home=home)

    adapters = [
        ClaudeCodeAdapter(home=home),
        GeminiAdapter(home=home),
        OpenCodeAdapter(home=home),
        SharedSkillsAdapter(home=home),
    ]

    repo = GitRepo(repo_dir=_DEFAULT_REPO_DIR, remote_url=config.repo_url)
    collector = FileCollector(mapper=mapper)
    manifest_mgr = ManifestManager(repo_dir=_DEFAULT_REPO_DIR)

    return SyncEngine(
        adapters=adapters,
        repo=repo,
        mapper=mapper,
        collector=collector,
        manifest_mgr=manifest_mgr,
        repo_dir=_DEFAULT_REPO_DIR,
    )


def _detect_platform() -> Platform:
    """Detect the current operating system.

    Returns:
        Platform enum value for the current OS.
    """
    import platform as _p
    system = _p.system().lower()
    if system == "darwin":
        return Platform.DARWIN
    if system == "windows":
        return Platform.WINDOWS
    return Platform.LINUX
