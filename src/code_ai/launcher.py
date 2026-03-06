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

    # On Windows, npm global commands are .cmd files
    if sys.platform == "win32":
        cmd_path = shutil.which(f"{cmd}.cmd") or shutil.which(cmd)
    else:
        cmd_path = shutil.which(cmd)

    if not cmd_path:
        print(f"Error: '{cmd}' not found in PATH. Install it first.")
        sys.exit(1)

    env = os.environ.copy()
    for env_var, config_key in spec["env"].items():
        value = profile.get(config_key)
        if value:
            env[env_var] = value

    full_cmd = [cmd_path] + extra_args

    if sys.platform == "win32":
        # On Windows, use subprocess with shell=False for better compatibility
        try:
            result = subprocess.run(full_cmd, env=env, shell=False)
            sys.exit(result.returncode)
        except KeyboardInterrupt:
            sys.exit(130)
    else:
        os.environ.update(env)
        os.execvp(cmd, [cmd] + extra_args)
