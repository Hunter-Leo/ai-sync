# Project TODO

Tracks out-of-scope bugs and features discovered during task execution.
Do not act on these during an active task — log and continue.

## Backlog

| ID | Type | Priority | Summary | Source | Status |
|---|---|---|---|---|---|
| B-001 | feature | medium | 新增 manifest-only 同步模式：只同步各工具的安装列表（插件、扩展等），在目标机器上根据列表重新安装，而非复制文件本身。类似 `uv export` 导出 lockfile、目标机器 `uv sync` 重装的模式。适用场景：跨架构机器（x86/arm）、插件含平台原生二进制时文件不可直接复制。 | 用户需求 | pending |

## Details

### B-001 — manifest-only 同步模式

**背景：** 当前 push/pull 直接复制文件。但部分资产（如 Claude Code 插件、含原生二进制的扩展）在不同平台/架构间不能直接复制，需要在目标机器上重新安装。

**设想的交互：**
- `ai-sync push --mode=manifest` — 只记录安装列表，不复制文件内容
- `ai-sync pull --mode=manifest` — 读取安装列表，调用各工具的安装命令重装

**需要调研：**
- Claude Code 插件是否有 CLI 安装命令（如 `claude install <plugin>`）
- Gemini CLI / OpenCode 是否有类似的包管理机制
- 安装列表格式设计（工具名、版本、来源 URL）
