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
from ai_sync.manifest import ManifestManager
from ai_sync.models import AiSyncError, AppConfig, LocalConfig, Platform, RemoteConfig
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
    """Configure the sync repository and save credentials locally."""
    _console.print("[bold]ai-sync init[/bold]")

    store = ConfigStore(config_path=_DEFAULT_CONFIG_DIR / "config.json")

    if store.exists():
        overwrite = typer.confirm(
            "Config already exists. Overwrite?", default=False
        )
        if not overwrite:
            _console.print("Aborted.")
            raise typer.Exit()

    mode_input = typer.prompt(
        "Select mode\n  1) Remote — use a remote git repository\n  2) Local  — use an existing local clone\nChoice",
        default="1",
    )

    if mode_input.strip() == "2":
        _init_local(store)
    else:
        _init_remote(store)


def _init_remote(store: ConfigStore) -> None:
    """Handle init flow for remote repository mode.

    Args:
        store: ConfigStore instance to persist the configuration.
    """
    needs_new = typer.confirm("Do you need to create a new repository?", default=False)
    if needs_new:
        _console.print(
            "\n[bold]To create a new repository:[/bold]\n"
            "  1. Visit your hosting provider (e.g. github.com/new) and create a private repo.\n"
            "  2. Generate an access token with read/write access to repository contents.\n"
            "     GitHub: Settings → Developer settings → Fine-grained tokens → Contents: Read & Write\n"
            "  3. Copy the HTTPS clone URL and token, then continue below.\n"
        )

    repo_url = typer.prompt("Repository HTTPS clone URL")

    needs_token = typer.confirm("Does this repository require a token for HTTPS access?", default=True)
    token: str | None = None
    if needs_token:
        token = typer.prompt("Access token", hide_input=True)

    config = RemoteConfig(repo_url=repo_url, token=token)
    store.save(config)
    _console.print(f"[green]Config saved:[/green] {store._path}")

    _console.print("Cloning repository…")
    try:
        effective_url = _embed_token(repo_url, token)
        git_repo = GitRepo(repo_dir=_DEFAULT_REPO_DIR, remote_url=effective_url)
        git_repo.clone()
        _console.print(f"[green]Cloned to:[/green] {_DEFAULT_REPO_DIR}")
    except AiSyncError as exc:
        _err_console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(code=1) from exc


def _init_local(store: ConfigStore) -> None:
    """Handle init flow for local repository mode.

    Args:
        store: ConfigStore instance to persist the configuration.
    """
    path_str = typer.prompt("Path to your local git clone")
    local_path = Path(path_str).expanduser().resolve()

    if not local_path.exists():
        _err_console.print(f"[red]Error:[/red] Path does not exist: {local_path}")
        raise typer.Exit(code=1)

    if not (local_path / ".git").is_dir():
        _err_console.print(
            f"[red]Error:[/red] Not a git repository (no .git directory): {local_path}"
        )
        raise typer.Exit(code=1)

    config = LocalConfig(local_repo_path=local_path)
    store.save(config)
    _console.print(f"[green]Config saved:[/green] {store._path}")


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
    all components. Supports both RemoteConfig and LocalConfig modes.

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

    if isinstance(config, RemoteConfig):
        effective_url = _embed_token(config.repo_url, config.token)
        repo = GitRepo(repo_dir=_DEFAULT_REPO_DIR, remote_url=effective_url)
        repo_dir = _DEFAULT_REPO_DIR
    else:
        repo = GitRepo(repo_dir=config.local_repo_path, remote_url=None)
        repo_dir = config.local_repo_path

    collector = FileCollector(mapper=mapper)
    manifest_mgr = ManifestManager(repo_dir=repo_dir)

    return SyncEngine(
        adapters=adapters,
        repo=repo,
        mapper=mapper,
        collector=collector,
        manifest_mgr=manifest_mgr,
        repo_dir=repo_dir,
    )


def _embed_token(url: str, token: str | None) -> str:
    """Embed an authentication token into an HTTPS git URL.

    Transforms ``https://host/repo.git`` into
    ``https://<token>@host/repo.git`` when a token is provided.

    Args:
        url: The original HTTPS clone URL.
        token: Optional authentication token.

    Returns:
        The URL with the token embedded, or the original URL if token is None.
    """
    if not token:
        return url
    if "://" in url:
        scheme, rest = url.split("://", 1)
        return f"{scheme}://{token}@{rest}"
    return url


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
