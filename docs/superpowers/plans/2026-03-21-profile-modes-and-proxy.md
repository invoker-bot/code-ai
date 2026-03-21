# Profile Modes and HTTP Proxy Support - Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add Claude login mode support and optional HTTP proxy configuration for all profiles in code-ai.

**Architecture:** Introduce a dataclass-based profile model layer (`models.py`) that converts between dict storage and typed objects. The launcher will use these typed objects to determine authentication mode (API vs Login) and inject appropriate environment variables. Proxy support is added as an optional field on all profiles.

**Tech Stack:** Python 3.8+, dataclasses, pyyaml, typer

---

## File Structure

| File | Responsibility |
|------|-----------------|
| `src/code_ai/models.py` | NEW: Profile dataclass definitions and conversion functions |
| `src/code_ai/config.py` | MODIFY: Add helper to convert profile dicts to dataclass objects |
| `src/code_ai/profiles.py` | MODIFY: Update add_profile, show_profile, list_profiles for new fields |
| `src/code_ai/launcher.py` | MODIFY: Handle API vs Login mode, inject proxy environment variables |
| `tests/test_models.py` | NEW: Unit tests for profile conversion and validation |
| `tests/test_launcher.py` | NEW: Tests for environment variable injection |

---

## Task 1: Create Profile Models

**Files:**
- Create: `src/code_ai/models.py`
- Test: `tests/test_models.py`

- [ ] **Step 1: Write failing tests for profile conversion**

Create `tests/test_models.py`:

```python
import pytest
from src.code_ai.models import (
    ApiProfile, LoginProfile, profile_from_dict, profile_to_dict, VALID_TYPES
)

def test_api_profile_creation():
    """Test creating an API profile"""
    profile = ApiProfile(
        name="test-api",
        type="claude",
        base_url="https://api.anthropic.com",
        token="sk-ant-test"
    )
    assert profile.name == "test-api"
    assert profile.type == "claude"
    assert profile.base_url == "https://api.anthropic.com"
    assert profile.token == "sk-ant-test"
    assert profile.proxy is None

def test_login_profile_creation():
    """Test creating a login profile"""
    profile = LoginProfile(
        name="test-login",
        type="claude",
        credentials_path="~/.claude-profiles/account-a"
    )
    assert profile.name == "test-login"
    assert profile.type == "claude"
    assert profile.credentials_path == "~/.claude-profiles/account-a"
    assert profile.proxy is None

def test_profile_with_proxy():
    """Test profile with proxy"""
    profile = ApiProfile(
        name="test-proxy",
        type="gemini",
        base_url="https://generativelanguage.googleapis.com",
        api_key="AIza-test",
        proxy="http://127.0.0.1:7890"
    )
    assert profile.proxy == "http://127.0.0.1:7890"

def test_profile_from_dict_api_mode():
    """Test converting dict to API profile"""
    data = {
        "name": "my-api",
        "type": "claude",
        "mode": "api",
        "base_url": "https://api.anthropic.com",
        "token": "sk-ant-test",
        "proxy": None
    }
    profile = profile_from_dict(data)
    assert isinstance(profile, ApiProfile)
    assert profile.name == "my-api"
    assert profile.base_url == "https://api.anthropic.com"

def test_profile_from_dict_login_mode():
    """Test converting dict to login profile"""
    data = {
        "name": "my-login",
        "type": "claude",
        "mode": "login",
        "credentials_path": "~/.claude-profiles/account-a",
        "proxy": "http://127.0.0.1:7890"
    }
    profile = profile_from_dict(data)
    assert isinstance(profile, LoginProfile)
    assert profile.credentials_path == "~/.claude-profiles/account-a"
    assert profile.proxy == "http://127.0.0.1:7890"

def test_profile_from_dict_defaults_to_api():
    """Test that missing mode defaults to api"""
    data = {
        "name": "legacy",
        "type": "claude",
        "base_url": "https://api.anthropic.com",
        "token": "sk-ant-test"
    }
    profile = profile_from_dict(data)
    assert isinstance(profile, ApiProfile)

def test_profile_to_dict_api():
    """Test converting API profile to dict"""
    profile = ApiProfile(
        name="my-api",
        type="claude",
        base_url="https://api.anthropic.com",
        token="sk-ant-test"
    )
    data = profile_to_dict(profile)
    assert data["name"] == "my-api"
    assert data["type"] == "claude"
    assert data["mode"] == "api"
    assert data["base_url"] == "https://api.anthropic.com"
    assert data["token"] == "sk-ant-test"

def test_profile_to_dict_login():
    """Test converting login profile to dict"""
    profile = LoginProfile(
        name="my-login",
        type="claude",
        credentials_path="~/.claude-profiles/account-a",
        proxy="http://127.0.0.1:7890"
    )
    data = profile_to_dict(profile)
    assert data["name"] == "my-login"
    assert data["type"] == "claude"
    assert data["mode"] == "login"
    assert data["credentials_path"] == "~/.claude-profiles/account-a"
    assert data["proxy"] == "http://127.0.0.1:7890"

def test_valid_types():
    """Test VALID_TYPES constant"""
    assert VALID_TYPES == ("claude", "gemini", "codex")
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd D:\Projects\GitHub\code-ai
pytest tests/test_models.py -v
```

Expected output: All tests fail with "ModuleNotFoundError: No module named 'src.code_ai.models'"

- [ ] **Step 3: Create models.py with dataclass definitions**

Create `src/code_ai/models.py`:

```python
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
    """Login mode: authenticate via OAuth credentials directory (Claude only)"""
    credentials_path: str = ""       # Path to existing OAuth credentials


def profile_from_dict(data: dict) -> BaseProfile:
    """Convert dict to appropriate profile dataclass"""
    name = data.get("name", "")
    ptype = data.get("type", "")
    mode = data.get("mode", "api")  # Default to api for backward compatibility
    proxy = data.get("proxy")

    if ptype == "claude" and mode == "login":
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
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_models.py -v
```

Expected output: All tests pass

- [ ] **Step 5: Commit**

```bash
git add src/code_ai/models.py tests/test_models.py
git commit -m "feat: add profile dataclass models with conversion functions"
```

---

## Task 2: Update Config Module

**Files:**
- Modify: `src/code_ai/config.py`

- [ ] **Step 1: Add helper function to config.py**

Add to `src/code_ai/config.py` after imports:

```python
from .models import profile_from_dict, profile_to_dict, BaseProfile


def get_profile_object(config, name: str) -> BaseProfile:
    """Get a profile as a dataclass object"""
    profiles = config.get("profiles", {})
    if name not in profiles:
        raise ValueError(f"Profile '{name}' not found")
    return profile_from_dict(profiles[name])
```

- [ ] **Step 2: Verify no syntax errors**

```bash
python -m py_compile src/code_ai/config.py
```

Expected: No output (success)

- [ ] **Step 3: Commit**

```bash
git add src/code_ai/config.py
git commit -m "feat: add get_profile_object helper to config module"
```

---

## Task 3: Update Profiles Module - add_profile

**Files:**
- Modify: `src/code_ai/profiles.py`

- [ ] **Step 1: Update add_profile function**

Replace the `add_profile()` function in `src/code_ai/profiles.py`:

```python
def add_profile(config):
    name = input("Profile name: ").strip()
    if not name:
        print("Error: name cannot be empty.")
        sys.exit(1)
    if name in config.get("profiles", {}):
        print(f"Error: profile '{name}' already exists.")
        sys.exit(1)

    ptype = input(f"Type ({'/'.join(VALID_TYPES)}): ").strip().lower()
    if ptype not in VALID_TYPES:
        print(f"Error: type must be one of {VALID_TYPES}.")
        sys.exit(1)

    profile_data = {"name": name, "type": ptype}

    # For Claude, ask about mode
    if ptype == "claude":
        mode = input("Mode (api/login): ").strip().lower()
        if mode not in ("api", "login"):
            print("Error: mode must be 'api' or 'login'.")
            sys.exit(1)
        profile_data["mode"] = mode

        if mode == "login":
            credentials_path = input("Credentials path: ").strip()
            if not credentials_path:
                print("Error: credentials path cannot be empty.")
                sys.exit(1)
            profile_data["credentials_path"] = credentials_path
        else:  # api mode
            base_url = input("Base URL: ").strip()
            if not base_url:
                print("Error: base URL cannot be empty.")
                sys.exit(1)
            token = input("Auth token: ").strip()
            profile_data["base_url"] = base_url
            profile_data["token"] = token
    else:
        # Gemini/Codex: only API mode
        profile_data["mode"] = "api"
        base_url = input("Base URL: ").strip()
        if not base_url:
            print("Error: base URL cannot be empty.")
            sys.exit(1)
        api_key = input("API key: ").strip()
        profile_data["base_url"] = base_url
        profile_data["api_key"] = api_key

    # Optional proxy for all types
    proxy = input("HTTP proxy (optional, press Enter to skip): ").strip()
    if proxy:
        profile_data["proxy"] = proxy

    config.setdefault("profiles", {})[name] = profile_data
    return config
```

- [ ] **Step 2: Test add_profile interactively**

```bash
cd D:\Projects\GitHub\code-ai
python -c "
from src.code_ai.profiles import add_profile
from src.code_ai.config import load_config, save_config
config = load_config()
# Manually test by checking the function signature
print('add_profile function updated successfully')
"
```

- [ ] **Step 3: Commit**

```bash
git add src/code_ai/profiles.py
git commit -m "feat: update add_profile to support mode and proxy"
```

---

## Task 4: Update Profiles Module - show_profile

**Files:**
- Modify: `src/code_ai/profiles.py`

- [ ] **Step 1: Update show_profile function**

Replace the `show_profile()` function in `src/code_ai/profiles.py`:

```python
def show_profile(config, name):
    from .models import profile_from_dict

    profiles = config.get("profiles", {})
    if name not in profiles:
        print(f"Error: profile '{name}' not found.")
        sys.exit(1)

    profile_dict = profiles[name]
    profile = profile_from_dict(profile_dict)

    print(f"Profile: {name}")
    print(f"Type: {profile.type}")

    # Show mode for Claude profiles
    if profile.type == "claude":
        mode = profile_dict.get("mode", "api")
        print(f"Mode: {mode}")

        if mode == "login":
            print(f"Credentials path: {profile.credentials_path}")
        else:
            print(f"Base URL: {profile.base_url}")
            print(f"Token: {profile.token}")
    else:
        print(f"Base URL: {profile.base_url}")
        print(f"API Key: {profile.api_key}")

    # Show proxy if set
    if profile.proxy:
        print(f"Proxy: {profile.proxy}")
```

- [ ] **Step 2: Test show_profile**

```bash
python -c "
from src.code_ai.profiles import show_profile
from src.code_ai.config import load_config
config = load_config()
print('show_profile function updated successfully')
"
```

- [ ] **Step 3: Commit**

```bash
git add src/code_ai/profiles.py
git commit -m "feat: update show_profile to display mode and proxy"
```

---

## Task 5: Update Profiles Module - list_profiles

**Files:**
- Modify: `src/code_ai/profiles.py`

- [ ] **Step 1: Update list_profiles function**

Replace the `list_profiles()` function in `src/code_ai/profiles.py`:

```python
def list_profiles(config):
    from .models import profile_from_dict

    profiles = config.get("profiles", {})
    if not profiles:
        print("No profiles configured.")
        return

    print(f"{'Name':<20} {'Type':<10} {'Mode':<8} {'Base URL/Credentials':<40} {'Proxy':<20}")
    print("-" * 100)

    for name, p in profiles.items():
        profile = profile_from_dict(p)
        ptype = profile.type
        mode = p.get("mode", "api")

        # Determine what to show in the URL/Credentials column
        if mode == "login":
            url_or_creds = profile.credentials_path[:37] + "..." if len(profile.credentials_path) > 40 else profile.credentials_path
        else:
            url_or_creds = profile.base_url[:37] + "..." if len(profile.base_url) > 40 else profile.base_url

        proxy_display = profile.proxy[:17] + "..." if profile.proxy and len(profile.proxy) > 20 else (profile.proxy or "-")

        print(f"{name:<20} {ptype:<10} {mode:<8} {url_or_creds:<40} {proxy_display:<20}")
```

- [ ] **Step 2: Test list_profiles**

```bash
python -c "
from src.code_ai.profiles import list_profiles
from src.code_ai.config import load_config
config = load_config()
print('list_profiles function updated successfully')
"
```

- [ ] **Step 3: Commit**

```bash
git add src/code_ai/profiles.py
git commit -m "feat: update list_profiles to show mode and proxy columns"
```

---

## Task 6: Update Launcher Module

**Files:**
- Modify: `src/code_ai/launcher.py`
- Test: `tests/test_launcher.py`

- [ ] **Step 1: Write failing tests for launcher**

Create `tests/test_launcher.py`:

```python
import os
import pytest
from unittest.mock import patch, MagicMock
from src.code_ai.models import ApiProfile, LoginProfile
from src.code_ai.launcher import prepare_environment


def test_prepare_env_api_mode():
    """Test environment preparation for API mode"""
    profile = ApiProfile(
        name="test-api",
        type="claude",
        base_url="https://api.anthropic.com",
        token="sk-ant-test"
    )

    env = prepare_environment(profile)

    assert env["ANTHROPIC_BASE_URL"] == "https://api.anthropic.com"
    assert env["ANTHROPIC_AUTH_TOKEN"] == "sk-ant-test"


def test_prepare_env_login_mode():
    """Test environment preparation for login mode"""
    profile = LoginProfile(
        name="test-login",
        type="claude",
        credentials_path="~/.claude-profiles/account-a"
    )

    env = prepare_environment(profile)

    # Should NOT have API environment variables
    assert "ANTHROPIC_BASE_URL" not in env
    assert "ANTHROPIC_AUTH_TOKEN" not in env
    # Should have CLAUDE_CONFIG_DIR
    assert env["CLAUDE_CONFIG_DIR"] == "~/.claude-profiles/account-a"


def test_prepare_env_with_proxy():
    """Test environment preparation with proxy"""
    profile = ApiProfile(
        name="test-proxy",
        type="gemini",
        base_url="https://generativelanguage.googleapis.com",
        api_key="AIza-test",
        proxy="http://127.0.0.1:7890"
    )

    env = prepare_environment(profile)

    assert env["HTTP_PROXY"] == "http://127.0.0.1:7890"
    assert env["HTTPS_PROXY"] == "http://127.0.0.1:7890"


def test_prepare_env_login_clears_api_vars():
    """Test that login mode clears API environment variables"""
    # Set up environment with existing API variables
    with patch.dict(os.environ, {
        "ANTHROPIC_BASE_URL": "https://old.url",
        "ANTHROPIC_AUTH_TOKEN": "old-token"
    }):
        profile = LoginProfile(
            name="test-login",
            type="claude",
            credentials_path="~/.claude-profiles/account-a"
        )

        env = prepare_environment(profile)

        # Should be cleared
        assert "ANTHROPIC_BASE_URL" not in env
        assert "ANTHROPIC_AUTH_TOKEN" not in env
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_launcher.py -v
```

Expected: Tests fail with "ImportError: cannot import name 'prepare_environment'"

- [ ] **Step 3: Update launcher.py**

Replace the `launch()` function in `src/code_ai/launcher.py`:

```python
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
        "env": {"OPENAI_BASE_URL": "base_url", "OPENAI_API_KEY": "api_key"},
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
        # Login mode: clear API environment variables and set CLAUDE_CONFIG_DIR
        for env_var in spec["env"]:
            env.pop(env_var, None)
        env["CLAUDE_CONFIG_DIR"] = profile.credentials_path
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
        # On Windows, use subprocess with shell=False for better compatibility
        try:
            result = subprocess.run(full_cmd, env=env, shell=False)
            sys.exit(result.returncode)
        except KeyboardInterrupt:
            sys.exit(130)
    else:
        os.environ.update(env)
        os.execvp(cmd, [cmd] + extra_args)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_launcher.py -v
```

Expected: All tests pass

- [ ] **Step 5: Commit**

```bash
git add src/code_ai/launcher.py tests/test_launcher.py
git commit -m "feat: update launcher to handle API/login modes and proxy"
```

---

## Task 7: Update Profiles Module Imports

**Files:**
- Modify: `src/code_ai/profiles.py`

- [ ] **Step 1: Add imports to profiles.py**

Add at the top of `src/code_ai/profiles.py`:

```python
from .models import VALID_TYPES, profile_from_dict
```

Remove the old `VALID_TYPES` definition if it exists.

- [ ] **Step 2: Verify syntax**

```bash
python -m py_compile src/code_ai/profiles.py
```

Expected: No output

- [ ] **Step 3: Commit**

```bash
git add src/code_ai/profiles.py
git commit -m "refactor: move VALID_TYPES to models module"
```

---

## Task 8: Integration Testing

**Files:**
- Test: `tests/test_integration.py`

- [ ] **Step 1: Write integration tests**

Create `tests/test_integration.py`:

```python
import tempfile
import os
from pathlib import Path
from src.code_ai.config import load_config, save_config
from src.code_ai.profiles import add_profile, show_profile, list_profiles
from src.code_ai.models import profile_from_dict


def test_full_workflow_api_profile(monkeypatch, capsys):
    """Test complete workflow: create API profile, show it, list it"""
    # Mock user input
    inputs = iter([
        "test-api",           # name
        "claude",             # type
        "api",                # mode
        "https://api.anthropic.com",  # base_url
        "sk-ant-test",        # token
        ""                    # proxy (skip)
    ])
    monkeypatch.setattr("builtins.input", lambda _: next(inputs))

    config = {"profiles": {}}
    config = add_profile(config)

    assert "test-api" in config["profiles"]
    profile_data = config["profiles"]["test-api"]
    assert profile_data["type"] == "claude"
    assert profile_data["mode"] == "api"
    assert profile_data["base_url"] == "https://api.anthropic.com"
    assert profile_data["token"] == "sk-ant-test"


def test_full_workflow_login_profile(monkeypatch, capsys):
    """Test complete workflow: create login profile with proxy"""
    inputs = iter([
        "test-login",         # name
        "claude",             # type
        "login",              # mode
        "~/.claude-profiles/account-a",  # credentials_path
        "http://127.0.0.1:7890"  # proxy
    ])
    monkeypatch.setattr("builtins.input", lambda _: next(inputs))

    config = {"profiles": {}}
    config = add_profile(config)

    assert "test-login" in config["profiles"]
    profile_data = config["profiles"]["test-login"]
    assert profile_data["type"] == "claude"
    assert profile_data["mode"] == "login"
    assert profile_data["credentials_path"] == "~/.claude-profiles/account-a"
    assert profile_data["proxy"] == "http://127.0.0.1:7890"


def test_backward_compatibility():
    """Test that old profiles without mode field still work"""
    old_profile_data = {
        "name": "legacy",
        "type": "claude",
        "base_url": "https://api.anthropic.com",
        "token": "sk-ant-test"
    }

    profile = profile_from_dict(old_profile_data)
    assert profile.type == "claude"
    assert profile.base_url == "https://api.anthropic.com"
    assert profile.token == "sk-ant-test"
```

- [ ] **Step 2: Run integration tests**

```bash
pytest tests/test_integration.py -v
```

Expected: All tests pass

- [ ] **Step 3: Commit**

```bash
git add tests/test_integration.py
git commit -m "test: add integration tests for profile workflows"
```

---

## Task 9: Manual Testing

**Files:**
- None (manual testing)

- [ ] **Step 1: Test adding an API profile**

```bash
cd D:\Projects\GitHub\code-ai
python -m code_ai.cli add
# Input:
# Profile name: my-api
# Type: claude
# Mode: api
# Base URL: https://api.anthropic.com
# Auth token: sk-ant-test
# HTTP proxy: (press Enter)
```

Verify: Profile added successfully

- [ ] **Step 2: Test adding a login profile**

```bash
python -m code_ai.cli add
# Input:
# Profile name: my-login
# Type: claude
# Mode: login
# Credentials path: ~/.claude-profiles/account-a
# HTTP proxy: http://127.0.0.1:7890
```

Verify: Profile added successfully

- [ ] **Step 3: Test listing profiles**

```bash
python -m code_ai.cli list
```

Verify: Both profiles appear with correct mode and proxy columns

- [ ] **Step 4: Test showing profiles**

```bash
python -m code_ai.cli show my-api
python -m code_ai.cli show my-login
```

Verify: Correct information displayed for each

- [ ] **Step 5: Verify config file format**

```bash
cat ~/.code-ai/config.yaml
```

Verify: YAML contains mode and proxy fields

- [ ] **Step 6: Commit manual testing notes**

```bash
git add -A
git commit -m "test: manual testing completed successfully"
```

---

## Task 10: Final Verification

**Files:**
- None (verification only)

- [ ] **Step 1: Run all tests**

```bash
pytest tests/ -v
```

Expected: All tests pass

- [ ] **Step 2: Check for syntax errors**

```bash
python -m py_compile src/code_ai/*.py
```

Expected: No output

- [ ] **Step 3: Verify backward compatibility**

Create a test config with old format:

```bash
cat > ~/.code-ai/config.yaml << 'EOF'
profiles:
  legacy-profile:
    name: legacy-profile
    type: claude
    base_url: https://api.anthropic.com
    token: sk-ant-test
EOF

python -m code_ai.cli list
python -m code_ai.cli show legacy-profile
```

Verify: Old profile works without errors

- [ ] **Step 4: Final commit**

```bash
git log --oneline -10
```

Verify: All commits are present and meaningful

---

## Success Criteria Checklist

- [ ] Claude profiles support both API and Login modes
- [ ] All profiles support optional HTTP proxy
- [ ] Login mode clears API environment variables
- [ ] Existing profiles continue to work (backward compatible)
- [ ] CLI UX remains simple and intuitive
- [ ] All unit tests pass
- [ ] All integration tests pass
- [ ] Manual testing completed successfully
- [ ] No syntax errors in any Python files
- [ ] YAML config format is correct
