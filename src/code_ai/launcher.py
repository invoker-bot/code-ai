import os
import sys
import shutil
import subprocess
from .models import profile_from_dict, ApiProfile, LoginProfile

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
        "env": {"OPENAI_API_KEY": "api_key"},
        "cmd": "codex",
    },
}


def prepare_environment(profile):
    """Prepare environment variables based on profile type and mode"""
    env = os.environ.copy()
    ptype = profile.type

    if ptype not in ENV_MAP:
        raise ValueError(f"Unknown profile type '{ptype}'")

    spec = ENV_MAP[ptype]

    # Handle authentication based on profile type
    if isinstance(profile, LoginProfile):
        # Login mode: clear API environment variables and set CONFIG_DIR
        for env_var in spec["env"]:
            env.pop(env_var, None)
        # Expand ~ to home directory
        credentials_path = os.path.expanduser(profile.credentials_path)
        # Set the appropriate CONFIG_DIR based on profile type
        config_dir_var = f"{ptype.upper()}_CONFIG_DIR"
        env[config_dir_var] = credentials_path
    elif isinstance(profile, ApiProfile):
        # API mode: set API environment variables
        for env_var, config_key in spec["env"].items():
            value = getattr(profile, config_key, None)
            if value:
                env[env_var] = value

    # Handle proxy (all modes)
    if profile.proxy:
        env["HTTP_PROXY"] = profile.proxy
        env["HTTPS_PROXY"] = profile.proxy

    return env


def launch(profile_dict, extra_args):
    # Convert dict to dataclass
    profile = profile_from_dict(profile_dict)
    ptype = profile.type

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

    # Prepare environment
    env = prepare_environment(profile)

    full_cmd = [cmd_path] + extra_args

    if sys.platform == "win32":
        # On Windows, use subprocess with full environment
        try:
            result = subprocess.run(full_cmd, env=env, shell=False)
            sys.exit(result.returncode)
        except KeyboardInterrupt:
            sys.exit(130)
    else:
        # On Unix, update os.environ and use execvp
        os.environ.update(env)
        os.execvp(cmd, [cmd] + extra_args)
