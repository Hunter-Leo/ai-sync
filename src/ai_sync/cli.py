"""CLI entry point for ai-sync."""

import typer

app = typer.Typer(
    name="ai-sync",
    help="Sync AI coding assistant configs across machines.",
    no_args_is_help=True,
)


@app.command()
def init() -> None:
    """Configure GitHub Token and repository."""
    typer.echo("init — not yet implemented")


@app.command()
def push() -> None:
    """Read local configs and push to remote repository."""
    typer.echo("push — not yet implemented")


@app.command()
def pull() -> None:
    """Pull configs from remote repository and restore locally."""
    typer.echo("pull — not yet implemented")


@app.command()
def status() -> None:
    """Show diff between local and remote configs."""
    typer.echo("status — not yet implemented")
