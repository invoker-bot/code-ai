import sys
import subprocess
from typing import Optional, List

import typer

from .config import load_config, save_config
from .profiles import list_profiles, add_profile, remove_profile, show_profile
from .launcher import launch
from . import __version__

app = typer.Typer(
    help="Switch AI coding tool profiles and launch the correct CLI",
    add_completion=False,
)


@app.command(name="list")
def list_command():
    """List all profiles"""
    config = load_config()
    list_profiles(config)


@app.command(name="show")
def show_command(name: str = typer.Argument(..., help="Profile name to show")):
    """Show profile details (platform, URL, and credentials)"""
    config = load_config()
    show_profile(config, name)


@app.command(name="add")
def add_command():
    """Add a new profile interactively"""
    config = load_config()
    config = add_profile(config)
    save_config(config)
    typer.echo("Profile added.")


@app.command(name="remove")
def remove_command(name: str = typer.Argument(..., help="Profile name to remove")):
    """Remove a profile"""
    config = load_config()
    config = remove_profile(config, name)
    save_config(config)


@app.command(name="upgrade")
def upgrade_command():
    """Upgrade claude, codex, and gemini CLI via npm"""
    upgrade()


@app.command(
    name="run",
    context_settings={"allow_extra_args": True, "ignore_unknown_options": True},
)
def run_command(
    ctx: typer.Context,
    profile: str = typer.Argument(..., help="Profile name to launch"),
):
    """Launch a profile with optional arguments

    Examples:
      code-ai run fox-claude
      code-ai run fox-claude -p "hello"
      code-ai run 4399 --help
    """
    config = load_config()
    profiles = config.get("profiles", {})
    if profile not in profiles:
        typer.echo(f"Unknown profile: '{profile}'", err=True)
        typer.echo("Run 'code-ai list' to see available profiles.")
        raise typer.Exit(1)
    launch(profiles[profile], ctx.args)


def version_callback(value: bool):
    if value:
        typer.echo(f"code-ai {__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: Optional[bool] = typer.Option(
        None, "--version", "-v", callback=version_callback, is_eager=True, help="Show version"
    ),
):
    """
    Switch AI coding tool profiles and launch the correct CLI.

    Examples:
      code-ai list                      List all profiles
      code-ai show fox-claude           Show profile details
      code-ai run fox-gemini            Launch Gemini CLI with fox profile
      code-ai run 4399                  Launch Claude CLI with 4399 profile
      code-ai run fox-claude -p "hi"    Pass extra args to Claude CLI
    """
    pass


UPGRADE_PACKAGES = [
    "@anthropic-ai/claude-code",
    "@openai/codex",
    "@google/gemini-cli",
]


def upgrade():
    typer.echo("Upgrading claude, codex, gemini CLI...")
    result = subprocess.run(
        ["npm", "install", "-g"] + UPGRADE_PACKAGES,
    )
    sys.exit(result.returncode)


if __name__ == "__main__":
    app()



