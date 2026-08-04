# ai-code-switcher

Switch AI coding tool profiles and launch the correct CLI.

## Features

- Manage multiple AI coding tool profiles for Claude, Codex, and Grok
- Switch between API-mode and login-mode profiles
- Launch the matching CLI through one command entrypoint
- Per-profile default launch arguments (e.g., always pass `--model ...`)
- Upgrade supported AI CLIs through npm

## Install

```bash
pip install -e .
```

## Usage

List profiles:

```bash
code-ai list
```

Add a profile:

```bash
code-ai add
```

Show one profile:

```bash
code-ai show <profile-name>
```

Launch a profile:

```bash
code-ai run fox-grok
code-ai run 4399
code-ai run fox-claude -p "hi"
code-ai run --no-default-args fox-claude --model sonnet  # bypass profile defaults
```

### Default launch arguments

A profile may define `default_args` to be appended to every `code-ai run`
invocation for that profile. Useful for "this profile always uses model X" or
for forcing flags like `--dangerously-skip-permissions` on a sandboxed profile.

`default_args` accepts either a YAML list (recommended) or a single string
(parsed with POSIX shell rules):

```yaml
profiles:
  fox-claude:
    name: fox-claude
    type: claude
    mode: login
    credentials_path: ~/.claude-profiles/fox
    default_args:
      - --model
      - claude-opus-4-5
      - --dangerously-skip-permissions

  4399:
    name: 4399
    type: claude
    mode: api
    base_url: https://...
    token: sk-...
    default_args: "--model claude-opus-4-5"
```

Merge order: command-line arguments come first, `default_args` is appended
last. Most CLIs treat the last occurrence of a flag as authoritative, so
`default_args` effectively pins the configured value (e.g., the profile's
`--model claude-opus-4-5` overrides any `--model` the user passes on the
command line). Pass `--no-default-args` between `run` and the profile name
to skip `default_args` for a single invocation.

The interactive `code-ai add` flow asks for `default_args` at the end (leave
blank to skip). The value is stored verbatim as a string; switch to list
form by editing `~/.code-ai/config.yaml` directly.

Remove a profile:

```bash
code-ai remove <profile-name>
```

Upgrade supported CLIs:

```bash
code-ai upgrade
```

This upgrades:

- `@anthropic-ai/claude-code`
- `@openai/codex`
- `@xai-official/grok`

Version:

```bash
code-ai --version
```

Help:

```bash
code-ai --help
```

## Configuration

Profiles are stored under `~/.code-ai/config.yaml`.

Grok profiles support both modes. API mode sets `XAI_API_KEY` and optionally
`GROK_CLI_CHAT_PROXY_BASE_URL`; login mode isolates browser credentials and
configuration through `GROK_HOME`.

## Project Layout

```text
src/code_ai/
|-- __init__.py
|-- cli.py
|-- config.py
|-- launcher.py
`-- profiles.py
```

## Requirements

- Python >= 3.8
- pyyaml >= 5.0

## License

MIT

## Desktop launcher (`code-ai desktop`)

A double-clickable GUI (Windows + macOS) that starts and Steam-style stops the
Claude, ChatGPT, and Codex desktop apps. Each detected app shows separate launch
and stop actions; launch first stops any running instance so the new environment
is applied cleanly.

```bash
pip install ai-code-switcher[desktop]   # one-time: install the GUI deps
code-ai desktop install                 # create or recreate the shortcut
code-ai desktop run                     # open the launcher window
code-ai desktop uninstall               # remove the shortcut (asks about settings)
```

Settings live in `~/.code-ai/desktop.yaml` (separate from CLI profiles): a
"check system proxy" toggle, plus **通用** (common) and **专有** (per-app)
environment variables. Per-app values override common values on a shared key.
