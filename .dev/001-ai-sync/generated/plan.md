# 实现计划

**需求编号：** 001  
**阶段：** Phase 04 — 实现计划  
**日期：** 2026-04-16  
**参考：** `research.md`

---

## 项目结构

```
ai-sync/
├── pyproject.toml
├── src/
│   └── ai_sync/
│       ├── __init__.py
│       ├── cli.py                  # typer 入口，定义 init/push/pull/status 命令
│       ├── models.py               # Pydantic 数据模型（AppConfig、Manifest、SyncItem 等）
│       ├── config_store.py         # ConfigStore — 读写 ~/.config/ai-sync/config.json
│       ├── path_mapper.py          # PathMapper — 占位符抽象与还原
│       ├── file_collector.py       # FileCollector — 收集本地文件，解析软链接
│       ├── git_repo.py             # GitRepo — git 操作封装（gitpython）
│       ├── github_client.py        # GitHubClient — GitHub API 封装（PyGithub）
│       ├── manifest.py             # ManifestManager — 读写 _manifest.json
│       ├── sync_engine.py          # SyncEngine — 编排 push/pull 流程
│       └── adapters/
│           ├── __init__.py
│           ├── base.py             # ToolAdapter ABC
│           ├── claude_code.py      # ClaudeCodeAdapter
│           ├── gemini.py           # GeminiAdapter
│           ├── opencode.py         # OpenCodeAdapter
│           └── shared_skills.py    # SharedSkillsAdapter（~/.skills/、~/.agents/skills/）
└── tests/
    ├── test_models.py
    ├── test_config_store.py
    ├── test_path_mapper.py
    ├── test_file_collector.py
    ├── test_git_repo.py
    ├── test_manifest.py
    ├── test_sync_engine.py
    └── adapters/
        ├── test_claude_code.py
        ├── test_gemini.py
        ├── test_opencode.py
        └── test_shared_skills.py
```

---

## 技术决策

| 技术 | 版本 | 理由 |
|---|---|---|
| Python | 3.11+ | `StrEnum`、`tomllib` 内置支持 |
| typer | latest | 声明式 CLI，类型注解驱动，与 Pydantic 配合好 |
| gitpython | latest | 纯 Python git 操作，无需系统 git 命令 |
| PyGithub | latest | GitHub REST API 封装，用于自动创建仓库 |
| rich | latest | 终端彩色输出、进度条、表格 |
| pydantic v2 | >=2.0 | 数据验证、序列化，替代裸 dict |
| uv | — | 分发方式：`uv tool install ai-sync` |

---

## 实现路径

每步独立可测，按依赖顺序排列：

### Step 1 — `models.py`（无依赖）

定义所有 Pydantic 数据模型：

- `AppConfig` — `{ github_token, repo_url }`
- `Manifest` — `{ version, last_push, source_os, source_home, tools }`
- `SyncItem` — `{ local_path: Path, repo_path: str, is_dir: bool, optional: bool }`
- `CollectedFile` — `{ repo_path: str, content: bytes, is_binary: bool }`
- `StatusEntry` — `{ path: str, state: Literal["added","modified","deleted","unchanged"] }`
- `Platform` — `StrEnum("darwin", "linux", "windows")`

### Step 2 — `config_store.py`（依赖 models）

`ConfigStore` 类：
- `load() -> AppConfig` — 读取 `~/.config/ai-sync/config.json`，不存在时抛 `ConfigNotFoundError`
- `save(config: AppConfig) -> None` — 写入，自动创建目录
- `exists() -> bool`

### Step 3 — `path_mapper.py`（依赖 models）

`PathMapper` 类：
- `__init__(platform: Platform, home: Path)` — 注入平台和 home，不自行检测
- `get_placeholders() -> dict[str, str]` — 返回占位符→真实路径映射
- `abstract_paths(content: str) -> str` — 真实路径 → 占位符（push 时用）
- `restore_paths(content: str) -> str` — 占位符 → 真实路径（pull 时用）
- `is_text_file(path: Path) -> bool` — 尝试 UTF-8 解码判断，二进制文件跳过路径替换

占位符映射（见 `research.md`）：

| 占位符 | macOS | Linux | Windows |
|---|---|---|---|
| `{{HOME}}` | `/Users/<user>` | `/home/<user>` | `C:\Users\<user>` |
| `{{CLAUDE_HOME}}` | `~/.claude` | `~/.claude` | `%APPDATA%\Claude` |
| `{{GEMINI_HOME}}` | `~/.gemini` | `~/.gemini` | `%USERPROFILE%\.gemini` |
| `{{OPENCODE_HOME}}` | `~/.config/opencode` | `~/.config/opencode` | `%APPDATA%\opencode` |
| `{{SKILLS_HOME}}` | `~/.skills` | `~/.skills` | `%USERPROFILE%\.skills` |
| `{{AGENTS_HOME}}` | `~/.agents` | `~/.agents` | `%USERPROFILE%\.agents` |

### Step 4 — `adapters/base.py`（依赖 models）

`ToolAdapter` ABC：

```python
class ToolAdapter(ABC):
    @property
    @abstractmethod
    def tool_id(self) -> str: ...          # "claude-code" / "gemini" / "opencode" / "shared"

    @abstractmethod
    def get_sync_items(self) -> list[SyncItem]: ...   # 返回该工具的同步项列表

    @abstractmethod
    def get_base_dir(self) -> Path: ...    # 本地配置根目录
```

### Step 5 — 四个 Adapter 实现（依赖 base）

各 Adapter 只负责声明自己的 `SyncItem` 列表，不含 IO 逻辑：

**`ClaudeCodeAdapter`**：
- base_dir: `~/.claude`
- 同步项：`settings.json`、`CLAUDE.md`、`hooks/`、`skills/`、`agents/`（optional）、`plugins/installed_plugins.json`、`keybindings.json`（optional）
- 排除：`sessions/`、`history.jsonl`、`tasks/`、`plans/`、`plugins/cache/`、`cache/`、`debug/`

**`GeminiAdapter`**：
- base_dir: `~/.gemini`
- 同步项：`settings.json`、`GEMINI.md`、`commands/`（optional）、`skills/`（optional）、`memory.md`（optional）、`policies/`（optional）
- 排除：`oauth_creds.json`、`google_accounts.json`、`history/`、`antigravity-browser-profile/`、`mcp-oauth-tokens.json`、`a2a-oauth-tokens.json`、`installation_id`

**`OpenCodeAdapter`**：
- base_dir: 按优先级检测 `~/.opencode.json` 或 `~/.config/opencode/`
- 同步项：`.opencode.json`、`agents/`（optional）、`commands/`（optional）、`modes/`（optional）、`skills/`（optional）、`tools/`（optional）、`themes/`（optional）

**`SharedSkillsAdapter`**：
- 同步项：`~/.skills/`（→ `shared/skills/`）、`~/.agents/skills/`（→ `shared/agents/skills/`）
- 两项均为 optional（不存在则跳过）

### Step 6 — `file_collector.py`（依赖 adapters/base、models）

`FileCollector` 类：
- `collect(adapter: ToolAdapter) -> list[CollectedFile]`
  - 遍历 `adapter.get_sync_items()`
  - 对每个 `SyncItem`：
    - 若 `optional=True` 且路径不存在，跳过
    - 若路径是软链接，用 `Path.resolve()` 解析为真实路径
    - 若解析后路径不存在（悬空链接），输出警告并跳过
    - 文件：读取内容，判断是否二进制
    - 目录：递归遍历，应用排除规则，每个文件单独收集

软链接处理流程：
```
path.is_symlink()
    → resolved = path.resolve()
    → resolved.exists() ? 继续 : warn + skip
    → 以 resolved 路径读取内容
    → 写入仓库时使用原始 repo_path（不含链接信息）
```

### Step 7 — `git_repo.py`（依赖 models）

`GitRepo` 类：
- `clone(url: str, dest: Path) -> None`
- `pull() -> None`
- `push(commit_message: str) -> None` — add all + commit + push
- `diff_files() -> list[str]` — 返回有变更的文件列表（用于 status）
- `is_cloned() -> bool`

### Step 8 — `github_client.py`（依赖 models）

`GitHubClient` 类：
- `__init__(token: str)`
- `create_private_repo(name: str) -> str` — 创建私有仓库，返回 clone URL
- `repo_exists(repo_url: str) -> bool`

### Step 9 — `manifest.py`（依赖 models）

`ManifestManager` 类：
- `__init__(repo_dir: Path)`
- `read() -> Manifest | None`
- `write(manifest: Manifest) -> None`

### Step 10 — `sync_engine.py`（依赖所有上层模块）

`SyncEngine` 类（依赖注入所有组件）：

```python
class SyncEngine:
    def __init__(
        self,
        adapters: list[ToolAdapter],
        repo: GitRepo,
        mapper: PathMapper,
        collector: FileCollector,
        manifest_mgr: ManifestManager,
    ) -> None: ...
```

- `push() -> PushResult` — 收集 → 路径抽象 → 写入仓库 → commit/push → 更新 manifest
- `pull() -> PullResult` — git pull → 读仓库文件 → 路径还原 → 写入本地
- `status() -> list[StatusEntry]` — 对比本地（抽象后）与仓库文件的哈希

**push 数据流：**
```
ToolAdapter.get_sync_items()
    → FileCollector.collect()          # 解析软链接，读取内容
    → PathMapper.abstract_paths()      # 替换真实路径为占位符
    → 写入 repo_dir/<tool>/<path>
    → ManifestManager.write()
    → GitRepo.push()
```

**pull 数据流：**
```
GitRepo.pull()
    → 读取 repo_dir/<tool>/<path>
    → PathMapper.restore_paths()       # 替换占位符为真实路径
    → 写入本地配置目录
    → 若目标文件已存在，直接覆盖
```

### Step 11 — `cli.py`（依赖 sync_engine、config_store、github_client、rich）

用 typer 定义四个命令，在命令层组装依赖并调用 SyncEngine：

- `ai-sync init` — 交互式配置 token + repo（支持自动创建或手动填写），写入 `config.json`，clone 仓库
- `ai-sync push` — 加载 config → 组装 SyncEngine → 调用 `push()`，rich 进度输出
- `ai-sync pull` — 加载 config → 组装 SyncEngine → 调用 `pull()`，rich 进度输出
- `ai-sync status` — 加载 config → 组装 SyncEngine → 调用 `status()`，rich 表格输出

---

## 关键技术要点

### 工具适配器模式（OCP）

新增工具支持只需：
1. 新建 `adapters/<tool>.py`，继承 `ToolAdapter`
2. 在 `cli.py` 的适配器列表中添加实例

无需修改 `FileCollector`、`SyncEngine`、`PathMapper` 等任何现有代码。

### 依赖注入（DIP）

`SyncEngine` 通过构造函数接收所有依赖，不自行实例化。CLI 层负责组装。便于测试时替换 mock 实现。

### 软链接解析

`FileCollector` 统一处理，`ToolAdapter` 无需感知软链接。解析逻辑集中在一处（SRP）。

### 文本/二进制判断

`PathMapper.is_text_file()` 尝试以 UTF-8 读取前 8KB，失败则视为二进制。二进制文件直接复制，不做路径替换。

### OpenCode 配置路径检测

`OpenCodeAdapter` 在 `get_base_dir()` 中按优先级检测：
1. `Path.home() / ".opencode.json"` 存在 → base_dir = `Path.home()`，配置文件为 `.opencode.json`
2. 否则 → base_dir = `Path.home() / ".config" / "opencode"`

### 错误处理

```
AiSyncError (base)
├── ConfigNotFoundError    — config.json 不存在，提示运行 ai-sync init
├── RepoNotInitializedError — 仓库未 clone，提示运行 ai-sync init
├── GitOperationError      — git 操作失败（含原始错误信息）
└── GitHubAPIError         — GitHub API 失败（含状态码和提示）
```

所有异常在 CLI 层统一捕获，用 `rich.console.print_exception()` 输出，非零退出码。

---

## 超出范围

- 加密/脱敏（第一版完整同步，不加密）
- 冲突解决（pull 直接覆盖本地）
- 多仓库支持
- 自动定时同步
- 第四个及以上工具的支持
- Windows 实际路径验证（OpenCode，标记为待验证）
- GUI / TUI 界面

---

## 设计合规审查

**SOLID 原则：**
- [x] **SRP** — `FileCollector` 只收集文件；`PathMapper` 只做路径替换；`GitRepo` 只做 git 操作；`SyncEngine` 只编排流程
- [x] **OCP** — 新增工具 = 新增 Adapter 类，不修改现有代码
- [x] **LSP** — 所有 `ToolAdapter` 子类可无差别替换，`SyncEngine` 不感知具体类型
- [x] **ISP** — `ToolAdapter` 接口精简（3 个方法），无冗余方法
- [x] **DIP** — `SyncEngine` 依赖 `ToolAdapter` 抽象，不依赖具体 Adapter；依赖注入

**Constitution：**
- [x] 所有标识符、注释、文档使用英文
- [x] 所有数据结构使用 Pydantic v2 模型，无裸 `Dict[str, Any]`
- [x] 无硬编码密钥，Token 只存于 `~/.config/ai-sync/config.json`
- [x] 无 `if/elif` 工具类型判断链，用多态替代
- [x] 无重复逻辑（软链接处理集中在 `FileCollector`，路径替换集中在 `PathMapper`）
