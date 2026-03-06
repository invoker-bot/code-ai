import sys
import subprocess

from .config import load_config, save_config
from .profiles import list_profiles, add_profile, remove_profile
from .launcher import launch


USAGE = """\
usage: code-ai <profile|command> [args...]

commands:
  list              List all profiles
  add               Add a new profile interactively
  upgrade           Upgrade claude, codex, and gemini CLI via npm
  remove <name>     Remove a profile
  --version         Show version
  --help            Show this help

examples:
  code-ai fox-gemini          Launch Gemini CLI with fox profile
  code-ai 4399                Launch Claude CLI with 4399 profile
  code-ai fox-claude -p "hi"  Pass extra args to Claude CLI\
"""


def main():
    args = sys.argv[1:]

    if not args or args[0] in ("-h", "--help"):
        print(USAGE)
        return

    if args[0] == "--version":
        from . import __version__
        print(f"code-ai {__version__}")
        return

    cmd = args[0]
    config = load_config()

    if cmd == "list":
        list_profiles(config)
    elif cmd == "add":
        config = add_profile(config)
        save_config(config)
        print("Profile added.")
    elif cmd == "upgrade":
        upgrade()
    elif cmd == "remove":
        if len(args) < 2:
            print("Usage: code-ai remove <name>")
            sys.exit(1)
        config = remove_profile(config, args[1])
        save_config(config)
    else:
        profiles = config.get("profiles", {})
        if cmd not in profiles:
            print(f"Unknown profile or command: '{cmd}'")
            print("Run 'code-ai list' to see available profiles.")
            sys.exit(1)
        launch(profiles[cmd], args[1:])


UPGRADE_PACKAGES = [
    "@anthropic-ai/claude-code",
    "@openai/codex",
    "@google/gemini-cli",
]


def upgrade():
    print("Upgrading claude, codex, gemini CLI...")
    result = subprocess.run(
        ["npm", "install", "-g"] + UPGRADE_PACKAGES,
    )
    sys.exit(result.returncode)
