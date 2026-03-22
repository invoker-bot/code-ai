# ai-code-switcher

Switch AI coding tool profiles and launch the correct CLI.

## Features

- Manage multiple AI coding tool profiles for Claude, Codex, and Gemini
- Switch between API-mode and login-mode profiles
- Launch the matching CLI through one command entrypoint
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
code-ai run fox-gemini
code-ai run 4399
code-ai run fox-claude -p "hi"
```

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
- `@google/gemini-cli`

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
