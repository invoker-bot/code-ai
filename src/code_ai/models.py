from dataclasses import dataclass, asdict, field
from typing import Optional

VALID_TYPES = ("claude", "gemini", "codex")


@dataclass
class BaseProfile:
    """Common fields for all profiles"""
    name: str
    type: str                    # "claude" | "gemini" | "codex"
    proxy: Optional[str] = None  # e.g., "http://127.0.0.1:7890"


@dataclass
class ApiProfile(BaseProfile):
    """API mode: authenticate via base_url + token/api_key"""
    base_url: str = ""
    token: Optional[str] = None      # Claude only
    api_key: Optional[str] = None    # Gemini/Codex only


@dataclass
class LoginProfile(BaseProfile):
    """Login mode: authenticate via OAuth credentials directory (Claude/Codex)"""
    credentials_path: str = ""       # Path to existing OAuth credentials


def profile_from_dict(data: dict) -> BaseProfile:
    """Convert dict to appropriate profile dataclass"""
    name = data.get("name", "")
    ptype = data.get("type", "")
    mode = data.get("mode", "api")  # Default to api for backward compatibility
    proxy = data.get("proxy")

    if (ptype == "claude" or ptype == "codex") and mode == "login":
        return LoginProfile(
            name=name,
            type=ptype,
            credentials_path=data.get("credentials_path", ""),
            proxy=proxy
        )
    else:
        # API mode (default for all types)
        return ApiProfile(
            name=name,
            type=ptype,
            base_url=data.get("base_url", ""),
            token=data.get("token"),
            api_key=data.get("api_key"),
            proxy=proxy
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
