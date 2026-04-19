# 配置项完整性调研报告

**需求编号：** 001  
**阶段：** Phase 02 — 前置调研  
**日期：** 2026-04-16  

---

## 调研目标

通过查阅 Claude Code、Gemini CLI、OpenCode 官方文档及源码，验证 `init.md` 中同步资产清单的完整性，补充遗漏项，修正错误项。

---

## 一、Claude Code (`~/.claude/`)

**文档来源：** GitHub `anthropics/claude-code`，官方文档 `https://code.claude.com/docs`

### 发现的配置项

| 路径 | 说明 | 状态 |
|---|---|---|
| `settings.json` | 核心配置（model、hooks、MCP servers、permissions、env） | 已包含 |
| `CLAUDE.md` | 全局指令文件 | 已包含 |
| `hooks/` | Hook 脚本目录（.mjs 文件） | 已包含 |
| `skills/` | Skills 目录 | 已包含 |
| `agents/` | 自定义 agent 定义 | **新增** |
| `plugins/installed_plugins.json` | 已安装插件列表 | 已包含 |
| `keybindings.json` | 键盘快捷键配置 | **新增** |

### 排除项验证

| 路径 | 原因 | 结论 |
|---|---|---|
| `sessions/` | 会话数据，机器本地 | 正确排除 |
| `history.jsonl` | 历史记录，机器本地 | 正确排除 |
| `tasks/` | 任务数据，机器本地 | 正确排除 |
| `plans/` | 计划数据，机器本地 | 正确排除 |
| `plugins/cache/` | 插件缓存 | 正确排除 |
| `cache/` | 通用缓存 | 正确排除 |
| `debug/` | 调试数据 | 正确排除 |

### Windows 路径

文档确认 Windows 使用 `%APPDATA%\Claude`，现有映射正确。

### 结论

新增 `agents/`（若存在）和 `keybindings.json`（若存在）到同步清单。

---

## 二、Gemini CLI (`~/.gemini/`)

**文档来源：** GitHub `google-gemini/gemini-cli`，源码 `packages/core/src/config/storage.ts`、`packages/core/src/config/constants.ts`

### 发现的配置项

| 路径 | 说明 | 状态 |
|---|---|---|
| `settings.json` | 核心配置（MCP servers、hooks 等） | 已包含 |
| `GEMINI.md` | 全局指令文件 | 已包含 |
| `commands/` | 用户自定义命令目录 | **新增** |
| `skills/` | 用户自定义 skills 目录 | **新增** |
| `memory.md` | 全局记忆文件 | **新增** |
| `policies/` | 策略配置目录 | **新增** |

### 排除项验证与补充

| 路径 | 原因 | 结论 |
|---|---|---|
| `oauth_creds.json` | OAuth 凭证，敏感 | 正确排除 |
| `google_accounts.json` | Google 账户信息，敏感 | 正确排除 |
| `history/` | 历史记录，机器本地 | 正确排除 |
| `antigravity-browser-profile/` | 浏览器配置，机器本地 | 正确排除 |
| `mcp-oauth-tokens.json` | MCP OAuth 令牌，敏感 | **新增排除** |
| `a2a-oauth-tokens.json` | A2A OAuth 令牌，敏感 | **新增排除** |
| `installation_id` | 安装 ID，机器唯一 | **新增排除** |

### Windows 路径

源码分析：Gemini CLI 在 Windows 上使用 `%USERPROFILE%\.gemini`（而非 `%APPDATA%\Gemini`）。环境变量 `GEMINI_CLI_HOME` 可覆盖默认路径。

**修正：** `{{GEMINI_HOME}}` Windows 路径从 `%APPDATA%\Gemini` 修正为 `%USERPROFILE%\.gemini`。

### 共享 Agent Skills

Gemini CLI 还使用 `~/.agents/skills/` 作为跨工具共享的 agent skills 目录，独立于 `~/.gemini/`。需作为独立共享路径同步。

---

## 三、OpenCode (`~/.config/opencode/`)

**文档来源：** GitHub `opencode-ai/opencode`，源码 `internal/config/config.go`、`cmd/schema/main.go`

### 配置文件位置（按优先级）

1. `$HOME/.opencode.json`
2. `$XDG_CONFIG_HOME/opencode/.opencode.json`（通常为 `~/.config/opencode/`）
3. `./.opencode.json`（项目级，不同步）

**重要：** 配置文件名为 `.opencode.json`（带点前缀），原清单中 `opencode.json` 有误，已修正。

### 发现的配置项

| 路径 | 说明 | 状态 |
|---|---|---|
| `.opencode.json` | 核心配置（model、MCP、agents、commands） | 已包含（名称已修正） |
| `agents/` | 自定义 agent 定义 | 已包含 |
| `commands/` | 自定义命令 | 已包含 |
| `modes/` | 模式配置 | 已包含（文档未明确，但目录存在） |
| `skills/` | Skills 目录 | 已包含（文档未明确，但目录存在） |
| `tools/` | 自定义工具 | 已包含（文档未明确，但目录存在） |
| `themes/` | 主题配置 | 已包含（主题通过 `tui.theme` 字段引用） |

### Windows 路径

官方文档未明确说明 Windows 路径。根据 Go 应用惯例及社区反馈，推测为 `%APPDATA%\opencode`。**待实际 Windows 环境验证。**

### `settings.json` 核心结构参考

```json
{
  "data": { "directory": ".opencode" },
  "providers": { "openai": {}, "anthropic": {} },
  "agents": { "coder": {}, "task": {}, "title": {} },
  "shell": { "path": "...", "args": [] },
  "mcpServers": {},
  "lsp": {},
  "tui": { "theme": "opencode" },
  "autoCompact": true
}
```

---

## 四、共享配置路径

| 路径 | 说明 | 使用工具 |
|---|---|---|
| `~/.skills/` | 跨工具共享 skills | 通用约定 |
| `~/.agents/skills/` | 跨工具共享 agent skills | Gemini CLI 明确使用 |

---

## 五、跨平台路径映射修正汇总

| 占位符 | macOS | Linux | Windows | 变更说明 |
|---|---|---|---|---|
| `{{HOME}}` | `/Users/<user>` | `/home/<user>` | `C:\Users\<user>` | 无变更 |
| `{{CLAUDE_HOME}}` | `~/.claude` | `~/.claude` | `%APPDATA%\Claude` | 无变更 |
| `{{GEMINI_HOME}}` | `~/.gemini` | `~/.gemini` | `%USERPROFILE%\.gemini` | **Windows 路径修正** |
| `{{OPENCODE_HOME}}` | `~/.config/opencode` | `~/.config/opencode` | `%APPDATA%\opencode` | 无变更（待验证） |
| `{{SKILLS_HOME}}` | `~/.skills` | `~/.skills` | `%USERPROFILE%\.skills` | **Windows 路径修正** |
| `{{AGENTS_HOME}}` | `~/.agents` | `~/.agents` | `%USERPROFILE%\.agents` | **新增** |

---

## 六、软链接处理

调研发现部分工具（如 Claude Code 的 skills/hooks）用户可能使用软链接指向其他位置。

**处理策略：**
- push 时：遇到软链接，解析为真实文件内容后以普通文件写入仓库，不保存链接本身
- push 时：目录软链接，递归复制链接目标目录内容
- push 时：悬空链接（目标不存在），跳过并输出警告
- pull 时：始终以普通文件/目录写入本地，不创建软链接

---

## 七、结论与 init.md 变更清单

以下变更已同步更新至 `init.md`：

1. **Claude Code 新增：** `agents/`、`keybindings.json`
2. **Gemini CLI 新增同步项：** `commands/`、`skills/`、`memory.md`、`policies/`
3. **Gemini CLI 新增排除项：** `mcp-oauth-tokens.json`、`a2a-oauth-tokens.json`、`installation_id`
4. **OpenCode 修正：** 配置文件名 `opencode.json` → `.opencode.json`
5. **共享配置新增：** `~/.agents/skills/`
6. **路径映射修正：** `{{GEMINI_HOME}}` Windows、`{{SKILLS_HOME}}` Windows
7. **路径映射新增：** `{{AGENTS_HOME}}`
8. **新增软链接处理规则**

### 待验证项

- OpenCode Windows 实际路径（需 Windows 环境测试）
- OpenCode `modes/`、`skills/`、`tools/`、`themes/` 目录是否在所有版本中存在
