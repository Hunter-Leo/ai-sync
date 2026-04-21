"""CLI entry point for ai-sync.

Defines the four user-facing commands (init, push, pull, status) using typer.
This module is responsible for:
- Assembling all dependencies (ConfigStore, GitRepo, adapters, SyncEngine, …)
- Calling the appropriate SyncEngine method
- Catching AiSyncError subclasses and displaying friendly error messages
- Exiting with a non-zero status code on failure
"""

import shutil
import socket
import sys
from datetime import datetime, timezone
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

import socket

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

    home = Path.home()
    managed_tools = _discover_tools(home)

    if mode_input.strip() == "2":
        _init_local(store, managed_tools, home)
    else:
        _init_remote(store, managed_tools, home)


def _init_remote(store: ConfigStore, managed_tools: list[str], home: Path) -> None:
    """Handle init flow for remote repository mode.

    Args:
        store: ConfigStore instance to persist the configuration.
        managed_tools: Tool IDs selected during discovery.
        home: The current user's home directory.
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
        _console.print(
            "\n[bold]GitHub token setup:[/bold]\n"
            "  [cyan]Option A — Fine-grained PAT[/cyan] (recommended, more secure)\n"
            "    Required permission: [bold]Contents: Read and Write[/bold]\n"
            "    Create: https://github.com/settings/personal-access-tokens/new\n\n"
            "  [cyan]Option B — Classic PAT[/cyan] (simpler)\n"
            "    Required scope: [bold]repo[/bold]\n"
            "    Create: https://github.com/settings/tokens/new\n"
        )
        token = typer.prompt("Access token", hide_input=True)

    config = RemoteConfig(repo_url=repo_url, token=token, managed_tools=managed_tools)
    store.save(config)
    _console.print(f"[green]Config saved:[/green] {store._path}")

    _console.print("Cloning repository…")
    try:
        effective_url = _embed_token(repo_url, token)
        git_repo = GitRepo(repo_dir=_DEFAULT_REPO_DIR, remote_url=effective_url)
        git_repo.clone()
        _console.print(f"[green]Cloned to:[/green] {_DEFAULT_REPO_DIR}")
        engine = _build_engine()
        _handle_conflict(git_repo, engine, _DEFAULT_REPO_DIR, managed_tools, home)
    except AiSyncError as exc:
        _err_console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(code=1) from exc


def _init_local(store: ConfigStore, managed_tools: list[str], home: Path) -> None:
    """Handle init flow for local repository mode.

    Args:
        store: ConfigStore instance to persist the configuration.
        managed_tools: Tool IDs selected during discovery.
        home: The current user's home directory.
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

    config = LocalConfig(local_repo_path=local_path, managed_tools=managed_tools)
    store.save(config)
    _console.print(f"[green]Config saved:[/green] {store._path}")

    try:
        git_repo = GitRepo(repo_dir=local_path, remote_url=None)
        engine = _build_engine()
        _handle_conflict(git_repo, engine, local_path, managed_tools, home)
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
        if "403" in str(exc):
            _err_console.print(
                "[yellow]Hint:[/yellow] your token may lack write access. "
                "Run [bold]ai-sync init[/bold] to update it."
            )
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
        _backup_to_branch(engine._repo, engine, engine._repo_dir)
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
        # Fetch silently — failure is non-fatal.
        engine._repo.fetch()
        behind = engine._repo.commits_behind()
        entries = engine.status()
        manifest = engine._manifest_mgr.read()
    except AiSyncError as exc:
        _err_console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(code=1) from exc

    # Header: last push info from manifest.
    if manifest:
        ts = manifest.last_push.strftime("%Y-%m-%d %H:%M UTC")
        _console.print(f"Last push: [cyan]{ts}[/cyan]  source: [cyan]{manifest.source_os}[/cyan]  tools: {', '.join(manifest.tools) or '—'}")
    else:
        _console.print("[dim]No manifest found — repository may be empty.[/dim]")

    # Remote sync state.
    if behind > 0:
        _console.print(f"[yellow]⚠ {behind} commit(s) behind origin/main — run [bold]ai-sync pull[/bold][/yellow]")
    else:
        _console.print("[green]✓ Up to date with origin/main[/green]")

    # File diff summary.
    changed = [e for e in entries if e.state != "unchanged"]
    if not changed:
        _console.print("[green]Local configs match the repository.[/green]")
        return

    counts = {"added": 0, "modified": 0, "deleted": 0}
    for e in changed:
        counts[e.state] = counts.get(e.state, 0) + 1
    summary = "  ".join(
        f"[{'green' if k == 'added' else 'yellow' if k == 'modified' else 'red'}]{v} {k}[/]"
        for k, v in counts.items() if v
    )
    _console.print(summary)

    table = Table(show_header=True, header_style="bold", box=None, padding=(0, 2))
    table.add_column("State", style="cyan", width=12)
    table.add_column("Path")

    state_colors = {"added": "green", "modified": "yellow", "deleted": "red", "unchanged": "dim"}
    for entry in entries:
        if entry.state == "unchanged":
            continue
        color = state_colors.get(entry.state, "white")
        table.add_row(f"[{color}]{entry.state}[/{color}]", entry.path)

    _console.print(table)


# ---------------------------------------------------------------------------
# manage sub-commands
# ---------------------------------------------------------------------------

manage_app = typer.Typer(name="manage", help="Manage which tools are synced.")
app.add_typer(manage_app)


@manage_app.command("list")
def manage_list() -> None:
    """List the tools currently under management."""
    store = ConfigStore(config_path=_DEFAULT_CONFIG_DIR / "config.json")
    try:
        config = store.load()
    except AiSyncError as exc:
        _err_console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(code=1) from exc

    tools = config.managed_tools
    if not tools:
        _console.print("Managing [bold]all tools[/bold] (backward-compatible mode).")
    else:
        _console.print("Managed tools:")
        for t in tools:
            _console.print(f"  • {t}")


@manage_app.command("add")
def manage_add(tool: str = typer.Argument(..., help="Tool ID to add")) -> None:
    """Add a tool to the managed list."""
    if tool not in VALID_TOOL_IDS:
        _err_console.print(
            f"[red]Error:[/red] Unknown tool '{tool}'. "
            f"Valid IDs: {', '.join(sorted(VALID_TOOL_IDS))}"
        )
        raise typer.Exit(code=1)

    store = ConfigStore(config_path=_DEFAULT_CONFIG_DIR / "config.json")
    try:
        config = store.load()
    except AiSyncError as exc:
        _err_console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(code=1) from exc

    if tool in config.managed_tools:
        _console.print(f"[yellow]{tool}[/yellow] is already in the managed list.")
        return

    home = Path.home()
    rel = _TOOL_DIRS.get(tool, "")
    if rel and not (home / rel).is_dir():
        _console.print(f"[yellow]Warning:[/yellow] local directory for '{tool}' not found ({home / rel}).")

    config.managed_tools.append(tool)
    store.save(config)
    _console.print(f"[green]Added[/green] {tool} to managed tools.")


@manage_app.command("remove")
def manage_remove(tool: str = typer.Argument(..., help="Tool ID to remove")) -> None:
    """Remove a tool from the managed list."""
    store = ConfigStore(config_path=_DEFAULT_CONFIG_DIR / "config.json")
    try:
        config = store.load()
    except AiSyncError as exc:
        _err_console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(code=1) from exc

    if tool not in config.managed_tools:
        _err_console.print(
            f"[red]Error:[/red] '{tool}' is not in the managed list."
        )
        raise typer.Exit(code=1)

    config.managed_tools.remove(tool)
    store.save(config)
    _console.print(
        f"[green]Removed[/green] {tool}. "
        "Its files will be cleared from the repo on the next [bold]ai-sync push[/bold]."
    )


# Maps tool IDs to their adapter classes. Used for managed_tools filtering.
ADAPTER_MAP: dict[str, type] = {
    "claude-code":   ClaudeCodeAdapter,
    "gemini":        GeminiAdapter,
    "opencode":      OpenCodeAdapter,
    "shared-skills": SharedSkillsAdapter,
}


def _build_engine() -> SyncEngine:
    """Assemble and return a fully configured SyncEngine.

    Reads the local config, detects the current platform, and wires together
    all components. Supports both RemoteConfig and LocalConfig modes.
    Filters adapters by config.managed_tools; empty list means all adapters.

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

    if config.managed_tools:
        adapters = []
        for tool_id in config.managed_tools:
            cls = ADAPTER_MAP.get(tool_id)
            if cls is None:
                _err_console.print(f"[yellow]Warning:[/yellow] unknown tool ID '{tool_id}' in managed_tools — skipped.")
            else:
                adapters.append(cls(home=home))
    else:
        adapters = [cls(home=home) for cls in ADAPTER_MAP.values()]

    if isinstance(config, RemoteConfig):
        effective_url = _embed_token(config.repo_url, config.token)
        repo = GitRepo(repo_dir=_DEFAULT_REPO_DIR, remote_url=effective_url)
        repo.sync_remote_url()
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


# Tool ID → local directory mapping used for discovery.
_TOOL_DIRS: dict[str, str] = {
    "claude-code": ".claude",
    "gemini": ".gemini",
    "opencode": ".config/opencode",
    "shared-skills": ".skills",
}

VALID_TOOL_IDS: frozenset[str] = frozenset(_TOOL_DIRS.keys())


def _discover_tools(home: Path) -> list[str]:
    """Scan local directories and ask the user which tools to manage.

    Args:
        home: The current user's home directory.

    Returns:
        List of tool IDs the user chose to manage. Empty list if none selected.
    """
    found: list[str] = []
    for tool_id, rel in _TOOL_DIRS.items():
        if (home / rel).is_dir():
            found.append(tool_id)

    if not found:
        _console.print("[yellow]No known tool directories found. You can add tools later with `ai-sync manage add`.[/yellow]")
        return []

    selected: list[str] = []
    _console.print("\n[bold]Detected tool directories:[/bold]")
    for tool_id in found:
        if typer.confirm(f"  Manage {tool_id}?", default=True):
            selected.append(tool_id)

    return selected


def _backup_branch_name() -> str:
    """Return the backup branch name for the current machine.

    Format: ``backup/<hostname>-<platform>``
    (e.g. ``backup/leoluo-macbook-darwin``)

    Returns:
        Branch name string safe for use as a git ref.
    """
    hostname = socket.gethostname().lower().replace(" ", "-")
    platform = _detect_platform().value
    return f"backup/{hostname}-{platform}"


def _backup_to_branch(repo: GitRepo, engine: "SyncEngine", repo_dir: Path) -> None:
    """Snapshot the current local config to a machine-specific backup branch.

    Mirrors local files to the repo directory (same logic as push), commits
    to the backup branch, and pushes to remote. If the push fails, a warning
    is printed but execution continues so the caller can proceed with pull.

    Args:
        repo: GitRepo instance managing the local clone.
        engine: SyncEngine used to collect local config files.
        repo_dir: Root directory of the local git clone.
    """
    branch = _backup_branch_name()
    _console.print(f"Backing up local config to branch [cyan]{branch}[/cyan]…")

    for adapter in engine._adapters:
        tool_dir = repo_dir / adapter.tool_id
        if tool_dir.exists():
            shutil.rmtree(tool_dir)
        tool_dir.mkdir(parents=True, exist_ok=True)
        files = engine._collector.collect(adapter)
        for cf in files:
            dest = (repo_dir / cf.repo_path).resolve()
            if not dest.is_relative_to(repo_dir.resolve()):
                continue
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(cf.content)

    repo.checkout_or_create_branch(branch)
    ts = datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    repo.commit_all(f"backup: pre-pull snapshot {ts}")

    try:
        repo.push_branch(branch)
    except AiSyncError as exc:
        _err_console.print(
            f"[yellow]Warning:[/yellow] backup push failed (local commit preserved): {exc}"
        )

    repo.checkout_branch("main")


def _handle_conflict(
    repo: GitRepo,
    engine: "SyncEngine",
    repo_dir: Path,
    managed_tools: list[str],
    home: Path,
) -> None:
    """Detect init-time conflicts and resolve by backing up then pulling.

    A conflict exists when the repo already contains tool files AND the local
    tool directory also has data. In that case the remote wins: local files
    are snapshotted to the backup branch, then overwritten by pull.

    If the repo is empty, the user is prompted to run ``ai-sync push`` instead.

    Args:
        repo: GitRepo instance managing the local clone.
        engine: SyncEngine used for backup and pull.
        repo_dir: Root directory of the local git clone.
        managed_tools: Tool IDs selected by the user during init.
        home: The current user's home directory.
    """
    tools_to_check = managed_tools if managed_tools else list(VALID_TOOL_IDS)

    repo_has_files = any(
        (repo_dir / tool_id).is_dir() and any((repo_dir / tool_id).iterdir())
        for tool_id in tools_to_check
    )

    if not repo_has_files:
        _console.print(
            "[yellow]Repository is empty. Run [bold]ai-sync push[/bold] to upload your local config.[/yellow]"
        )
        return

    conflicting: list[str] = []
    for tool_id in tools_to_check:
        rel = _TOOL_DIRS.get(tool_id)
        if rel and (home / rel).is_dir() and any((home / rel).iterdir()):
            conflicting.append(tool_id)

    if not conflicting:
        return

    _console.print(
        f"[yellow]Conflict detected for:[/yellow] {', '.join(conflicting)}\n"
        "Remote will overwrite local. Backing up first…"
    )
    _backup_to_branch(repo, engine, repo_dir)
    engine.pull()
