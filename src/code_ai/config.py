import os
import sys
from pathlib import Path

import yaml

from .models import profile_from_dict, profile_to_dict, BaseProfile

CONFIG_DIR = Path.home() / ".code-ai"
CONFIG_FILE = CONFIG_DIR / "config.yaml"


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
    save_config({"profiles": {}})


def get_profile_object(config, name: str) -> BaseProfile:
    """Get a profile object from config by name."""
    if name not in config.get("profiles", {}):
        raise ValueError(f"Profile '{name}' not found in config")
    profile_dict = config["profiles"][name]
    return profile_from_dict(profile_dict)
