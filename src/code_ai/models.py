from dataclasses import dataclass, asdict, field
from typing import List, Optional, Union

VALID_TYPES = ("claude", "grok", "codex")

# default_args is stored in either form the user wrote it: a YAML list, or a
# single command-line string parsed at use-site via shlex.split.
DefaultArgs = Optional[Union[List[str], str]]


@dataclass
class BaseProfile:
    """Common fields for all profiles"""
    name: str
    type: str                            # "claude" | "grok" | "codex"
    proxy: Optional[str] = None          # e.g., "http://127.0.0.1:7890"
    default_args: DefaultArgs = None     # appended after CLI extra_args at launch


@dataclass
class ApiProfile(BaseProfile):
    """API mode: authenticate with a token/key and an optional endpoint."""
    base_url: str = ""
    token: Optional[str] = None      # Claude only
    api_key: Optional[str] = None    # Grok/Codex only


@dataclass
class LoginProfile(BaseProfile):
    """Login mode: authenticate via an isolated credentials directory."""
    credentials_path: str = ""       # Path to existing OAuth credentials


def profile_from_dict(data: dict) -> BaseProfile:
    """Convert dict to appropriate profile dataclass"""
    name = data.get("name", "")
    ptype = data.get("type", "")
    mode = data.get("mode", "api")  # Default to api for backward compatibility
    proxy = data.get("proxy")
    default_args = data.get("default_args")

    if ptype in VALID_TYPES and mode == "login":
        return LoginProfile(
            name=name,
            type=ptype,
            credentials_path=data.get("credentials_path", ""),
            proxy=proxy,
            default_args=default_args,
        )
    else:
        # API mode (default for all types)
        return ApiProfile(
            name=name,
            type=ptype,
            base_url=data.get("base_url", ""),
            token=data.get("token"),
            api_key=data.get("api_key"),
            proxy=proxy,
            default_args=default_args,
        )


def profile_to_dict(profile: BaseProfile) -> dict:
    """Convert profile dataclass to dict"""
    data = asdict(profile)

    # Add mode field
    if isinstance(profile, LoginProfile):
        data["mode"] = "login"
    else:
        data["mode"] = "api"

    # Remove None values for cleaner YAML
    return {k: v for k, v in data.items() if v is not None}
