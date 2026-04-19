# ai-sync

> Bring your AI skills anywhere.

Sync your AI coding assistant configs across machines using a private GitHub repository. One command to push, one command to restore on any new machine.

Supports **Claude Code**, **Gemini CLI**, and **OpenCode**.

---

## What it syncs

| Tool | Config location | What's included |
|---|---|---|
| Claude Code | `~/.claude/` | `settings.json`, `CLAUDE.md`, `hooks/`, `skills/`, `agents/`, `plugins/` |
| Gemini CLI | `~/.gemini/` | `settings.json`, `GEMINI.md`, `commands/`, `skills/`, `memory.md` |
| OpenCode | `~/.config/opencode/` | `.opencode.json`, `agents/`, `commands/`, `modes/`, `skills/`, `tools/`, `themes/` |
| Shared | `~/.skills/`, `~/.agents/skills/` | Cross-tool shared skills |

Sensitive files (OAuth tokens, session history, cache) are never synced.

---

## Installation

Requires [uv](https://docs.astral.sh/uv/).

```bash
uv tool install ai-sync
```

---

## Quick start

**1. Initialize** — connect to your GitHub account and create (or link) a private repo:

```bash
ai-sync init
```

You'll be prompted for a GitHub personal access token (repo scope) and whether to create a new repository or use an existing one.

**2. Push** — collect local configs and push to the remote repo:

```bash
ai-sync push
```

**3. On a new machine** — install ai-sync, run init with the same repo URL, then pull:

```bash
ai-sync init   # use existing repo URL
ai-sync pull
```

**4. Check status** — see what's changed locally vs. the remote:

```bash
ai-sync status
```

---

## How it works

```
push:  local configs → path abstraction → git commit & push
pull:  git pull → path restoration → write to local config dirs
```

Absolute paths in config files are replaced with platform-neutral placeholders on push (`{{CLAUDE_HOME}}`, `{{HOME}}`, etc.) and restored to the correct paths on pull. This means configs work correctly across macOS, Linux, and Windows.

Symlinks are resolved to their real content — the remote repo always stores plain files.

---

## Local state

```
~/.config/ai-sync/
├── config.json      # GitHub token + repo URL (chmod 0600)
└── repo/            # local git clone
```

---

## Remote repo structure

```
ai-sync-config/
├── _manifest.json
├── shared/
│   ├── skills/
│   └── agents/skills/
├── claude-code/
├── gemini/
└── opencode/
```

---

## Security

- GitHub token is stored only in `~/.config/ai-sync/config.json` with `0600` permissions
- Token input is hidden during `ai-sync init`
- Path traversal attacks from malicious repo content are blocked
- No encryption — use a **private** repository

---

## Development

```bash
git clone https://github.com/you/agent-infra-sync
cd agent-infra-sync
uv sync
uv run pytest
```

```bash
uv run ai-sync --help
```
