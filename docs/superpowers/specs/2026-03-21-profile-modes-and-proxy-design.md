# Profile Modes and HTTP Proxy Support - Design Spec

**Date**: 2026-03-21
**Status**: Design Phase
**Scope**: Add Claude login mode support and optional HTTP proxy for all profiles

---

## Overview

This spec adds two new features to code-ai:

1. **Claude Profile Modes**: Support both API mode (existing) and Login mode (new) for Claude profiles
2. **HTTP Proxy Support**: Optional proxy configuration for all profile types

### Feature 1: Claude Profile Modes

#### API Mode (Existing)
- Uses `base_url` + `token` for authentication
- Current behavior, remains default
- Works for all profile types (claude, gemini, codex)

#### Login Mode (New, Claude-only)
- Uses `credentials_path` pointing to an existing OAuth credentials directory
- Launches Claude CLI with `CLAUDE_CONFIG_DIR` environment variable set
- Clears API environment variables (`ANTHROPIC_BASE_URL`, `ANTHROPIC_AUTH_TOKEN`) to prevent pollution
- Only available for Claude profiles

### Feature 2: HTTP Proxy Support
- Optional `proxy` field on all profiles
- Format: `http://host:port` or `https://host:port`
- When set, injects `HTTP_PROXY` and `HTTPS_PROXY` environment variables at launch time
- Works with both API and Login modes

---

## Data Model

### Dataclass Hierarchy

New file: `src/code_ai/models.py`

```python
from dataclasses import dataclass
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
```

### YAML Storage Format

Profiles remain stored as dicts in `~/.code-ai/config.yaml`:

**API Mode Example**:
```yaml
profiles:
  my-claude-api:
    name: my-claude-api
    type: claude
    mode: api
    base_url: https://api.anthropic.com
    token: sk-ant-...
    proxy: null

  my-gemini:
    name: my-gemini
    type: gemini
    mode: api
    base_url: https://generativelanguage.googleapis.com
    api_key: AIza...
    proxy: http://127.0.0.1:7890
```

**Login Mode Example**:
```yaml
profiles:
  my-claude-login:
    name: my-claude-login
    type: claude
    mode: login
    credentials_path: ~/.claude-profiles/account-a
    proxy: null
```

---

## Implementation Changes

### 1. New File: `src/code_ai/models.py`

- Define `BaseProfile`, `ApiProfile`, `LoginProfile` dataclasses
- Add factory methods:
  - `profile_from_dict(data: dict) -> BaseProfile`: Convert dict to appropriate dataclass
  - `profile_to_dict(profile: BaseProfile) -> dict`: Convert dataclass to dict
- Add validation methods for each profile type

### 2. Modified: `src/code_ai/config.py`

- Add `profile_from_dict()` and `profile_to_dict()` imports
- No changes to `load_config()` or `save_config()` (keep dict-based I/O)
- Add helper: `get_profile_object(config, name) -> BaseProfile` to convert on-demand

### 3. Modified: `src/code_ai/profiles.py`

**`add_profile(config)`**:
- For Claude: Ask mode (API or Login)
  - API: Prompt for base_url + token
  - Login: Prompt for credentials_path
- For Gemini/Codex: Only API mode (prompt for base_url + api_key)
- For all types: Optional proxy prompt
- Save as dict to config

**`show_profile(config, name)`**:
- Convert dict to dataclass using `profile_from_dict()`
- Display mode (if Claude)
- Display credentials_path (if Login mode)
- Display proxy (if set)

**`list_profiles(config)`**:
- Table columns: `Name | Type | Mode | Base URL/Credentials | Proxy`
- Mode column shows "api" or "login" (or "-" for non-Claude)

### 4. Modified: `src/code_ai/launcher.py`

**`launch(profile_dict, extra_args)`**:
1. Convert dict to dataclass: `profile = profile_from_dict(profile_dict)`
2. Get environment spec from `ENV_MAP[profile.type]`
3. Copy current environment: `env = os.environ.copy()`

4. **Handle authentication**:
   - If `ApiProfile`: Set API environment variables from base_url/token/api_key
   - If `LoginProfile`:
     - Clear API environment variables (prevent pollution)
     - Set `CLAUDE_CONFIG_DIR = profile.credentials_path`

5. **Handle proxy** (all modes):
   - If `profile.proxy` is set:
     - `env["HTTP_PROXY"] = profile.proxy`
     - `env["HTTPS_PROXY"] = profile.proxy`

6. Execute subprocess with updated environment

---

## User Workflows

### Adding a Claude API Profile
```
$ code-ai add
Profile name: my-api
Type (claude/gemini/codex): claude
Mode (api/login): api
Base URL: https://api.anthropic.com
Auth token: sk-ant-...
HTTP proxy (optional, press Enter to skip):
Profile added.
```

### Adding a Claude Login Profile
```
$ code-ai add
Profile name: my-login
Type (claude/gemini/codex): claude
Mode (api/login): login
Credentials path: ~/.claude-profiles/account-a
HTTP proxy (optional, press Enter to skip): http://127.0.0.1:7890
Profile added.
```

### Listing Profiles
```
$ code-ai list
Name              Type    Mode   Base URL/Credentials              Proxy
my-api            claude  api    https://api.anthropic.com         -
my-login          claude  login  ~/.claude-profiles/account-a      http://127.0.0.1:7890
my-gemini         gemini  api    https://generativelanguage...     -
```

### Launching
```
$ code-ai run my-login
# Sets: CLAUDE_CONFIG_DIR=~/.claude-profiles/account-a
# Clears: ANTHROPIC_BASE_URL, ANTHROPIC_AUTH_TOKEN
# Launches: claude [extra_args]

$ code-ai run my-api
# Sets: ANTHROPIC_BASE_URL, ANTHROPIC_AUTH_TOKEN
# Launches: claude [extra_args]

$ code-ai run my-gemini
# Sets: GOOGLE_GEMINI_BASE_URL, GEMINI_API_KEY, HTTP_PROXY, HTTPS_PROXY
# Launches: gemini [extra_args]
```

---

## Backward Compatibility

- Existing profiles without `mode` field default to `api`
- Existing profiles without `proxy` field default to `None`
- No breaking changes to CLI commands
- YAML format remains dict-based

---

## Error Handling

1. **Login mode without credentials_path**: Validation error during profile creation
2. **credentials_path doesn't exist**: Warning at launch time (Claude CLI will handle)
3. **Invalid proxy format**: Validation during profile creation (basic URL validation)
4. **Non-Claude profile with login mode**: Reject during profile creation

---

## Testing Strategy

1. **Unit tests** for dataclass conversion (`profile_from_dict`, `profile_to_dict`)
2. **Integration tests** for profile CRUD operations
3. **Launcher tests** for environment variable injection
4. **Manual testing** for actual Claude/Gemini/Codex CLI launches

---

## Files Modified

| File | Changes |
|------|---------|
| `src/code_ai/models.py` | NEW: Dataclass definitions and conversion functions |
| `src/code_ai/config.py` | ADD: Helper functions for profile conversion |
| `src/code_ai/profiles.py` | MODIFY: add_profile, show_profile, list_profiles |
| `src/code_ai/launcher.py` | MODIFY: launch function for mode/proxy handling |
| `src/code_ai/cli.py` | No changes (commands remain the same) |

---

## Success Criteria

- ✓ Claude profiles support both API and Login modes
- ✓ All profiles support optional HTTP proxy
- ✓ Login mode clears API environment variables
- ✓ Existing profiles continue to work (backward compatible)
- ✓ CLI UX remains simple and intuitive
- ✓ All tests pass
