# ai-sync

> Bring your AI skills anywhere.

Sync your AI coding assistant configs across machines using a private git repository.

Supports **Claude Code**, **Gemini CLI**, **OpenCode**, and shared skills/agents.

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

## Usage flows

### Machine A — first setup

```
ai-sync init
     │
     ├─ Select mode
     │    1) Remote — HTTPS clone URL + optional token
     │    2) Local  — path to an existing local clone
     │
     ├─ Tool discovery
     │    Scans ~/.claude/  ~/.gemini/  ~/.config/opencode/  ~/.skills/
     │    Asks which tools to manage → saved as managed_tools in config.json
     │
     ├─ Clone / connect repository
     │
     └─ Conflict check
          Repo empty? → prompt to run ai-sync push
          Repo has data + local has data?
            → snapshot local to backup/<hostname>-<platform> branch
            → pull (remote wins)

ai-sync push
     │
     ├─ For each managed tool:
     │    Clear repo/<tool>/ (full mirror — deletions propagate)
     │    Read local config files
     │    Abstract paths: /Users/alice → {{HOME}}
     │    Write to repo/<tool>/
     │
     ├─ Write _manifest.json
     └─ git commit + push → origin/main
```

### Machine B — joining an existing setup

```
ai-sync init
     │
     ├─ Select mode + tool discovery (same as Machine A)
     ├─ Clone / connect same repository
     │
     └─ Conflict check
          Repo has data (from Machine A) + local has data?
            → backup local to backup/macbook-b-linux branch (pushed to remote)
            → pull: restore Machine A's config to local dirs
                    {{HOME}} → /home/bob  (paths restored for this machine)

Done — Machine B now has Machine A's config.
```

### Daily sync

```
Made changes on Machine A:
  ai-sync push   →  commits full mirror to origin/main

On Machine B:
  ai-sync pull
     │
     ├─ Snapshot current local state
     │    commit to backup/macbook-b-linux (pushed to remote)
     │
     └─ git pull origin/main
          restore paths for this machine
          write files locally
```

### Backup branch

Every `pull` (and conflicting `init`) automatically preserves the local state:

```
Remote repository branches:
  main                        ← shared sync state (all machines)
  backup/alice-macbook-darwin ← Machine A snapshots (one commit per pull)
  backup/bob-server-linux     ← Machine B snapshots (one commit per pull)

To recover a previous state on Machine B:
  git -C ~/.config/ai-sync/repo checkout backup/bob-server-linux
  git -C ~/.config/ai-sync/repo log --oneline   # find the snapshot
  git -C ~/.config/ai-sync/repo show <commit>:gemini/settings.json
```

---

## Commands

### `ai-sync init`

Configure the sync repository on this machine. Detects installed tools and handles conflicts.

```bash
ai-sync init
```

### `ai-sync push`

Collect local configs and push to the repository. **Full mirror** — files deleted locally are also deleted from the repo.

```bash
ai-sync push
```

### `ai-sync pull`

Snapshot local state to backup branch, then pull from the repository and restore configs.

```bash
ai-sync pull
```

### `ai-sync status`

Show what differs between local configs and the repository. Fetches from remote first (silently skips if offline).

```bash
ai-sync status
```

```
Last push: 2026-04-20 09:30 UTC  source: darwin  tools: claude-code, gemini
⚠ 2 commit(s) behind origin/main — run ai-sync pull
2 modified  1 added

  State       Path
  modified    claude-code/settings.json
  modified    gemini/settings.json
  added       gemini/GEMINI.md
```

### `ai-sync manage`

View and modify which tools are synced on this machine.

```bash
ai-sync manage list              # show managed tools
ai-sync manage add gemini        # add a tool
ai-sync manage remove opencode   # remove a tool
```

Valid tool IDs: `claude-code`, `gemini`, `opencode`, `shared-skills`

> Removing a tool only updates the local config. Its files are cleared from the repo on the next `ai-sync push`.

---

## How path abstraction works

Config files often contain absolute paths (e.g. MCP server paths). ai-sync replaces them with platform-neutral placeholders on push and restores them on pull:

```
push (Machine A, macOS):
  /Users/alice/.claude/plugins/server.js  →  {{CLAUDE_HOME}}/plugins/server.js

pull (Machine B, Linux):
  {{CLAUDE_HOME}}/plugins/server.js  →  /home/bob/.claude/plugins/server.js
```

| Placeholder | macOS / Linux | Windows |
|---|---|---|
| `{{CLAUDE_HOME}}` | `~/.claude` | `%APPDATA%\Claude` |
| `{{GEMINI_HOME}}` | `~/.gemini` | `%USERPROFILE%\.gemini` |
| `{{OPENCODE_HOME}}` | `~/.config/opencode` | `%APPDATA%\opencode` |
| `{{HOME}}` | `~` | `%USERPROFILE%` |

---

## Local state

```
~/.config/ai-sync/
├── config.json      # mode, repo URL, token, managed_tools (chmod 0600)
└── repo/            # local git clone (Remote mode only)
```

### Remote mode config

```json
{
  "mode": "remote",
  "repo_url": "https://github.com/you/ai-configs.git",
  "token": "ghp_...",
  "managed_tools": ["claude-code", "gemini"]
}
```

### Local mode config

```json
{
  "mode": "local",
  "local_repo_path": "/Users/alice/projects/ai-configs",
  "managed_tools": ["claude-code"]
}
```

---

## Remote repo structure

```
ai-configs/
├── _manifest.json          # last push metadata (timestamp, OS, tools)
├── claude-code/
│   ├── settings.json
│   ├── CLAUDE.md
│   └── hooks/
├── gemini/
│   └── settings.json
├── opencode/
│   └── .opencode.json
└── shared/
    └── skills/
```

---

## Security

- Token stored only in `~/.config/ai-sync/config.json` with `0600` permissions
- Token input is hidden during `ai-sync init`
- Token is embedded into the git URL at runtime only — never written to the repo
- Path traversal attacks from malicious repo content are blocked
- No encryption — use a **private** repository

---

## Development

```bash
git clone https://github.com/Hunter-Leo/ai-sync
cd ai-sync
uv sync
uv run pytest
uv run ai-sync --help
```
