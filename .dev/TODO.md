# Project TODO

Tracks out-of-scope bugs and features discovered during task execution.
Do not act on these during an active task — log and continue.

## Backlog

| ID | Type | Priority | Summary | Source | Status |
|---|---|---|---|---|---|
| B-001 | feature | medium | 新增 manifest-only 同步模式：只同步各工具的安装列表（插件、扩展等），在目标机器上根据列表重新安装，而非复制文件本身。类似 `uv export` 导出 lockfile、目标机器 `uv sync` 重装的模式。适用场景：跨架构机器（x86/arm）、插件含平台原生二进制时文件不可直接复制。 | 用户需求 | pending |
| B-002 | feature | high | pull 冲突保护：pull 前检测本地文件是否有未推送的改动，有则中止并提示用户先 push 或使用 --force 强制覆盖，防止本地改动被静默覆盖。 | [002] brainstorming | ignored |
| B-003 | feature | high | AI 工具化：提供非交互式 CLI 接口；构建 Agent Skill / Claude Code Plugin，在用户更新插件/MCP/配置后自动触发 ai-sync push。 | 用户需求 | pending |

## Details

### B-002 — pull 冲突保护

**Type:** feature
**Priority:** high
**Source:** [002] brainstorming
**Status:** ignored

**Description:**
当前 `pull()` 直接覆盖本地文件，不检查本地是否有未推送的改动。在多机器场景下，Machine B 本地修改了配置后直接 pull，改动会被静默覆盖。

**忽略原因：**
[003] 实现的 backup 分支方案已覆盖核心需求：每次 pull 前自动将本机状态 commit 到 `backup/<hostname>-<platform>` 分支并推送到远程，数据完整保留，随时可恢复。相比"拦截警告"，backup 分支提供了更强的保障，无需额外的 `--force` 机制。

---

### B-001 — manifest-only 同步模式

**背景：** 当前 push/pull 直接复制文件。但部分资产（如 Claude Code 插件、含原生二进制的扩展）在不同平台/架构间不能直接复制，需要在目标机器上重新安装。

**设想的交互：**
- `ai-sync push --mode=manifest` — 只记录安装列表，不复制文件内容
- `ai-sync pull --mode=manifest` — 读取安装列表，调用各工具的安装命令重装

**需要调研：**
- Claude Code 插件是否有 CLI 安装命令（如 `claude install <plugin>`）
- Gemini CLI / OpenCode 是否有类似的包管理机制
- 安装列表格式设计（工具名、版本、来源 URL）

---

### B-003 — AI 工具化：非交互式 CLI + 自动触发 push

**Type:** feature
**Priority:** high
**Source:** 用户需求
**Status:** pending

**Description:**
两个子目标：

1. **非交互式 CLI**：当前所有命令（init/push/pull）依赖 `typer.prompt` / `typer.confirm` 交互输入，无法被 AI Agent 直接调用。需提供 `--yes` / flag 参数跳过确认，或支持通过环境变量/参数传入所有必要值（repo_url、token、managed_tools 等），使 Agent 可以无人值守地执行。

2. **自动触发 push 的 Skill / Plugin**：构建 Claude Code Plugin 或 Agent Skill，监听用户对插件/MCP/配置的变更事件，自动调用 `ai-sync push`，无需用户手动执行。

**Notes:**
- 非交互式接口可参考 `ai-sync init --repo-url <url> --token <token> --tools claude-code,gemini` 形式
- 自动触发可通过 Claude Code hooks（PostToolUse on settings edit）或 OMC skill 实现
- 需要评估 Plugin API 能力边界
