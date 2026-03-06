import os
import sys
from pathlib import Path

import yaml

CONFIG_DIR = Path.home() / ".code-ai"
CONFIG_FILE = CONFIG_DIR / "config.yaml"

DEFAULT_PROFILES = {
    "fox-claude": {
        "type": "claude",
        "base_url": "https://code.newcli.com/claude/aws",
        "token": "sk-ant-oat01-j6FU43eI3djEeLFWcw_2mtngnBqwSEsOXMYkJtidPDxeCiqIeaTtHg6p12wvi7HaYIsp7VsK5kVbdwYlBW_mCBnSYmZ-qAA",
    },
    "fox-gemini": {
        "type": "gemini",
        "base_url": "https://code.newcli.com/gemini",
        "api_key": "sk-ant-oat01-j6FU43eI3djEeLFWcw_2mtngnBqwSEsOXMYkJtidPDxeCiqIeaTtHg6p12wvi7HaYIsp7VsK5kVbdwYlBW_mCBnSYmZ-qAA",
    },
    "fox-codex": {
        "type": "codex",
        "base_url": "https://code.newcli.com/codex/v1",
        "api_key": "sk-ant-oat01-j6FU43eI3djEeLFWcw_2mtngnBqwSEsOXMYkJtidPDxeCiqIeaTtHg6p12wvi7HaYIsp7VsK5kVbdwYlBW_mCBnSYmZ-qAA",
    },
    "4399": {
        "type": "claude",
        "base_url": "https://4399code.com/claudecode",
        "token": "sk-ant-oat01-ozUCp9rqL9sB46GoG5ISB1QPmlQPKZyk",
    },
    "2233": {
        "type": "claude",
        "base_url": "https://aicoding.2233.ai",
        "token": "sk-Xn6481958ee796a17126b676467f0e06d5e6f39ac14Uusba",
    },
}


def load_config():
    if not CONFIG_FILE.exists():
        init_config()
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    if not data or "profiles" not in data:
        data = {"profiles": {}}
    return data


def save_config(data):
    os.makedirs(CONFIG_DIR, exist_ok=True)
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        yaml.dump(data, f, default_flow_style=False, sort_keys=False, allow_unicode=True)


def init_config():
    save_config({"profiles": DEFAULT_PROFILES})
