import sys
import subprocess
from typing import Optional, List

import typer

from .config import load_config, save_config
from .profiles import list_profiles, add_profile, remove_profile, show_profile
from .launcher import launch
from .buddy import (
    RARITIES, SPECIES, RARITY_COLORS,
    roll_by_name, bruteforce_user_id,
    write_user_id_to_claude_config, get_claude_config_path,
    format_buddy_card,
)
from .models import profile_from_dict, LoginProfile
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


@app.command(name="roll-claude-buddy")
def roll_claude_buddy_command(
    profile: str = typer.Argument(..., help="Profile name to roll buddy for"),
    species: Optional[str] = typer.Option(None, "--name", "-n", help="Target species: duck/cat/dragon/capybara/..."),
    rarity: Optional[str] = typer.Option(None, "--type", "-t", help="Target rarity: common/uncommon/rare/epic/legendary"),
):
    """Roll a Claude Code buddy companion for a profile

    By default the buddy is deterministic per profile (same profile = same buddy).
    Use --name and/or --type to keep rolling until you get the target species/rarity.

    Examples:
      code-ai roll-claude-buddy fox-claude                           Roll buddy for profile
      code-ai roll-claude-buddy fox-claude --name capybara           Roll until capybara
      code-ai roll-claude-buddy fox-claude --type legendary          Roll until legendary
      code-ai roll-claude-buddy fox-claude --name dragon --type epic Roll until epic dragon
    """
    config = load_config()
    profiles = config.get("profiles", {})
    if profile not in profiles:
        typer.echo(f"Unknown profile: '{profile}'", err=True)
        typer.echo("Run 'code-ai list' to see available profiles.")
        raise typer.Exit(1)

    if rarity and rarity not in RARITIES:
        typer.echo(f"Invalid rarity: '{rarity}'. Choose from: {', '.join(RARITIES)}", err=True)
        raise typer.Exit(1)

    if species and species not in SPECIES:
        typer.echo(f"Invalid species: '{species}'. Choose from: {', '.join(SPECIES)}", err=True)
        raise typer.Exit(1)

    # Resolve the .claude.json path for this profile:
    # login mode → credentials_path/.claude.json
    # api mode   → ~/.claude.json
    profile_obj = profile_from_dict(profiles[profile])
    config_dir = None
    if isinstance(profile_obj, LoginProfile) and profile_obj.credentials_path:
        import os
        config_dir = os.path.expanduser(profile_obj.credentials_path)

    import io
    out = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

    if species or rarity:
        claude_json = get_claude_config_path(config_dir)
        out.write("\n")
        target_desc = " + ".join(filter(None, [
            rarity.capitalize() if rarity else None,
            species.capitalize() if species else None,
        ]))
        out.write(f"  Bruteforcing userID for {target_desc}...\n")
        out.flush()
        user_id, bones = bruteforce_user_id(target_rarity=rarity, target_species=species)
        write_user_id_to_claude_config(user_id, config_dir)
        out.write(f"  Written userID to {claude_json}\n")
    else:
        bones = roll_by_name(profile)
        user_id = None

    color = RARITY_COLORS[bones.rarity]
    card = format_buddy_card(bones)
    out.write("\n")
    out.write(typer.style(f"  [{profile}] You rolled a Claude Buddy!", bold=True) + "\n")
    out.write("\n")
    out.write(typer.style(card, fg=color) + "\n")
    if user_id:
        out.write("\n")
        out.write(f"  Restart Claude Code to see your new buddy!\n")
    out.write("\n")
    out.flush()


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

    # On Windows, npm is a .cmd file, need to use shell=True or npm.cmd
    if sys.platform == "win32":
        # Use shell=True on Windows for better compatibility
        cmd = "npm install -g " + " ".join(UPGRADE_PACKAGES)
        result = subprocess.run(cmd, shell=True)
    else:
        result = subprocess.run(
            ["npm", "install", "-g"] + UPGRADE_PACKAGES,
        )
    sys.exit(result.returncode)


if __name__ == "__main__":
    app()



