# 需求定义文档

**需求编号：** 001  
**需求名称：** ai-sync  
**文档语言：** 中文  
**执行模式：** 交互模式  
**项目阶段：** `pre-launch`

---

## # Spec

### 背景与动机

随着 Claude Code、Gemini CLI、OpenCode 等 AI 编程助手的普及，开发者积累了大量个人"AI 资产"：自定义 hooks、skills、MCP 服务器配置、全局指令文件（CLAUDE.md / GEMINI.md）等。

当开发者在多台机器（公司电脑、家用 Mac、Linux 服务器）之间切换时，重建这些配置耗时且容易出错。现有的 dotfiles 同步方案无法智能处理跨平台路径差异，也不了解各 AI 工具的配置结构。

### 核心问题

- 多台机器之间 AI 工具配置不一致
- 跨平台（Mac/Linux/Windows）路径不兼容
- 没有专门针对 AI 工具配置的同步解决方案

### 目标与愿景

打造一个 `uv tool` 安装的 Python CLI 工具，让开发者用一条命令把所有 AI 工具配置同步到私有 Git 仓库，在任意新机器上一键还原。

**口号：** "Bring your AI skills anywhere."

### 参考项目

- `.dev/proposal.md` — 项目提案
- BookmarkHub（`/Users/leoluo/Documents/code/BookmarkHub`）— 参考实现模式：工具与存储解耦，用户自有存储

---

## # Requirements

### 核心目标

1. 支持 Claude Code、Gemini CLI、OpenCode 三个工具的配置同步
2. 使用用户自有的 GitHub 私有仓库作为存储后端
3. 跨平台路径自动映射（Mac/Linux/Windows）
4. 支持跨工具共享配置（如 `~/.skills/`）
5. 以 `uv tool` 形式分发，无需额外依赖

### 功能需求

#### CLI 命令

| 命令 | 功能 |
|---|---|
| `ai-sync init` | 配置 GitHub Token + 仓库（支持自动创建或填入已有地址） |
| `ai-sync push` | 读取本地配置 → 路径抽象化 → commit & push 到远端仓库 |
| `ai-sync pull` | git pull → 路径还原 → 写入本地配置目录 |
| `ai-sync status` | 显示本地 vs 远端差异（哪些文件有变更） |

#### 同步资产清单

**Claude Code** (`~/.claude/`)

| 路径 | 说明 |
|---|---|
| `settings.json` | 核心配置（model、hooks、MCP servers、plugins、env） |
| `CLAUDE.md` | 全局指令文件 |
| `hooks/` | Hook 脚本目录（.mjs 文件） |
| `skills/` | Skills 目录 |
| `agents/` | 自定义 agent 定义（若存在） |
| `plugins/installed_plugins.json` | 已安装插件列表 |
| `keybindings.json` | 键盘快捷键配置（若存在） |

排除：`sessions/`、`history.jsonl`、`tasks/`、`plans/`、`plugins/cache/`、`cache/`、`debug/`

**Gemini CLI** (`~/.gemini/`)

| 路径 | 说明 |
|---|---|
| `settings.json` | 核心配置（MCP servers、hooks 等） |
| `GEMINI.md` | 全局指令文件 |
| `commands/` | 用户自定义命令目录 |
| `skills/` | 用户自定义 skills 目录 |
| `memory.md` | 全局记忆文件 |
| `policies/` | 策略配置目录 |

排除：`oauth_creds.json`、`google_accounts.json`、`history/`、`antigravity-browser-profile/`、`mcp-oauth-tokens.json`、`a2a-oauth-tokens.json`、`installation_id`

**OpenCode** (`~/.config/opencode/` 或 `~/.opencode.json`)

> 注：OpenCode 配置文件名为 `.opencode.json`（带点前缀）。实际路径按优先级：`$HOME/.opencode.json` > `$XDG_CONFIG_HOME/opencode/.opencode.json`。同步时以 `~/.config/opencode/` 为主目录，同时检查 `~/.opencode.json`。

| 路径 | 说明 |
|---|---|
| `.opencode.json` | 核心配置（model、MCP、agents、commands） |
| `agents/` | 自定义 agent 定义 |
| `commands/` | 自定义命令 |
| `modes/` | 模式配置 |
| `skills/` | Skills 目录 |
| `tools/` | 自定义工具 |
| `themes/` | 主题配置 |

**共享配置**

| 路径 | 说明 |
|---|---|
| `~/.skills/` | 跨工具共享的 skills |
| `~/.agents/skills/` | 跨工具共享的 agent skills（Gemini CLI 等工具使用） |

#### 远端仓库结构

```
ai-sync-config/
├── _manifest.json              # 元数据（版本、最后同步时间、source_os）
├── shared/
│   ├── skills/                 # ~/.skills/ 内容
│   └── agents/
│       └── skills/             # ~/.agents/skills/ 内容
├── claude-code/
│   ├── settings.json
│   ├── CLAUDE.md
│   ├── hooks/
│   ├── skills/
│   ├── agents/
│   ├── keybindings.json
│   └── plugins/
│       └── installed_plugins.json
├── gemini/
│   ├── settings.json
│   ├── GEMINI.md
│   ├── commands/
│   ├── skills/
│   ├── memory.md
│   └── policies/
└── opencode/
    ├── .opencode.json
    ├── agents/
    ├── commands/
    ├── modes/
    ├── skills/
    ├── tools/
    └── themes/
```

#### 跨平台路径映射

push 时将绝对路径替换为占位符，pull 时还原为目标平台路径：

| 占位符 | macOS | Linux | Windows |
|---|---|---|---|
| `{{HOME}}` | `/Users/<user>` | `/home/<user>` | `C:\Users\<user>` |
| `{{CLAUDE_HOME}}` | `~/.claude` | `~/.claude` | `%APPDATA%\Claude` |
| `{{GEMINI_HOME}}` | `~/.gemini` | `~/.gemini` | `%USERPROFILE%\.gemini` |
| `{{OPENCODE_HOME}}` | `~/.config/opencode` | `~/.config/opencode` | `%APPDATA%\opencode` |
| `{{SKILLS_HOME}}` | `~/.skills` | `~/.skills` | `%USERPROFILE%\.skills` |
| `{{AGENTS_HOME}}` | `~/.agents` | `~/.agents` | `%USERPROFILE%\.agents` |

路径映射作用于所有配置文件的文本内容（JSON 字符串值、.md 文件、.mjs 脚本中的路径引用）。

#### 软链接处理

push 时遇到软链接（symlink）必须解析为真实文件内容后再复制，不保存软链接本身：

- 文件软链接：读取链接目标的文件内容，以普通文件写入仓库
- 目录软链接：递归复制链接目标目录的内容，以普通目录写入仓库
- 若链接目标不存在（悬空链接），跳过并输出警告

pull 时始终以普通文件/目录写入本地，不创建软链接。

#### 本地工作目录

```
~/.config/ai-sync/
├── config.json      # { "github_token": "...", "repo_url": "..." }
└── repo/            # git clone 的本地副本
```

### 技术需求

- **语言：** Python 3.11+
- **分发：** `uv tool install ai-sync`（打包为 Python package）
- **依赖：**
  - `typer` — CLI 框架
  - `gitpython` — Git 操作
  - `PyGithub` — GitHub API（用于自动创建仓库）
  - `rich` — 终端输出美化
  - `pydantic` v2 — 数据模型与验证
- **平台：** macOS、Linux、Windows
- **Python 包名：** `ai-sync`，命令名：`ai-sync`

### 接口描述

#### `_manifest.json` 格式

```json
{
  "version": "1.0",
  "last_push": "2026-04-16T10:00:00Z",
  "source_os": "darwin",
  "source_home": "{{HOME}}",
  "tools": ["claude-code", "gemini", "opencode"]
}
```

#### `~/.config/ai-sync/config.json` 格式

```json
{
  "github_token": "ghp_xxx",
  "repo_url": "https://github.com/user/ai-sync-config.git"
}
```

---

## # Action Items

**前置文档**（按需）：
- [x] `generated/research.md` — 配置项完整性调研，包含：
  - 通过 context7 查阅 Claude Code 官方文档，确认 `~/.claude/` 下所有需同步的配置项
  - 通过 context7 查阅 Gemini CLI 官方文档，确认 `~/.gemini/` 下所有需同步的配置项
  - 通过 context7 查阅 OpenCode 官方文档，确认 `~/.config/opencode/` 下所有需同步的配置项及 Windows 路径
  - 对比现有同步资产清单，补充遗漏项或修正错误项

**必需文档**（按序）：
- [x] `generated/plan.md` — Phase 04
- [x] `generated/tasks.md` — Phase 05
- [x] `generated/start-and-resume.md` — Phase 06（执行前必须存在）

---

## # Constitution

### 语言与命名

- 所有标识符（变量、函数、类、常量）使用英文
- 所有注释和文档使用英文
- Python 命名规范：`snake_case` 变量/函数，`PascalCase` 类，`UPPER_SNAKE_CASE` 常量

### 类型系统

- 使用 Pydantic v2 定义所有数据结构
- 所有函数参数和返回值必须有类型注解
- 使用 `StrEnum` 或 `Literal` 表示固定选项值
- 禁止裸 `Dict[str, Any]`，用 Pydantic 模型替代

### 文档注释

- 每个文件必须有模块级 docstring
- 每个公开类和函数必须有完整 docstring（含 Args、Returns、Raises）
- 复杂算法必须附 ASCII 图或示例

### OOP 原则

- **单一职责**：每个类只做一件事（如 `GitRepo`、`PathMapper`、`ConfigCollector` 各自独立）
- **开闭原则**：新增工具支持通过添加新类实现，不修改现有代码（工具适配器模式）
- **依赖倒置**：高层模块依赖抽象接口，不依赖具体实现

### 错误处理

- 显式处理所有错误，不静默吞掉异常
- 错误信息必须有意义且可操作（告诉用户怎么修复）
- 区分可恢复错误（返回/抛出领域错误）和编程错误（让其传播）

### 测试

- 每个模块写完后立即写测试，再进入下一个模块
- 覆盖：正常情况、边界情况、错误/异常情况
- 核心逻辑最低覆盖率：80%
- 测试文件命名：`test_*.py`

### 依赖管理

```bash
uv add <package>    # 添加依赖
uv run <script>     # 运行脚本
uv sync             # 同步依赖
```

### 安全

- 不硬编码任何密钥或 Token
- GitHub Token 只存储在 `~/.config/ai-sync/config.json`（用户本地文件）
