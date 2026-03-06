import os
import sys
import shutil
import subprocess

ENV_MAP = {
    "claude": {
        "env": {"ANTHROPIC_BASE_URL": "base_url", "ANTHROPIC_AUTH_TOKEN": "token"},
        "cmd": "claude",
    },
    "gemini": {
        "env": {"GOOGLE_GEMINI_BASE_URL": "base_url", "GEMINI_API_KEY": "api_key"},
        "cmd": "gemini",
    },
    "codex": {
        "env": {"OPENAI_BASE_URL": "base_url", "OPENAI_API_KEY": "api_key"},
        "cmd": "codex",
    },
}


def launch(profile, extra_args):
    ptype = profile["type"]
    if ptype not in ENV_MAP:
        print(f"Error: unknown profile type '{ptype}'.")
        sys.exit(1)

    spec = ENV_MAP[ptype]
    cmd = spec["cmd"]

    if not shutil.which(cmd):
        print(f"Error: '{cmd}' not found in PATH. Install it first.")
        sys.exit(1)

    env = os.environ.copy()
    for env_var, config_key in spec["env"].items():
        value = profile.get(config_key)
        if value:
            env[env_var] = value

    full_cmd = [cmd] + extra_args

    if sys.platform == "win32":
        result = subprocess.run(full_cmd, env=env)
        sys.exit(result.returncode)
    else:
        os.environ.update(env)
        os.execvp(cmd, full_cmd)
