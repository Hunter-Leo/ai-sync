# 任务清单

**需求编号：** 001  
**阶段：** Phase 05 — 任务规划  
**日期：** 2026-04-16  
**参考：** `plan.md`

---

## 状态表

| ID    | 任务名称                          | 状态        | 备注 |
|-------|-----------------------------------|-------------|------|
| T-001 | 初始化项目结构与 pyproject.toml   | done        |      |
| T-002 | 实现 models.py                    | done        |      |
| T-003 | models.py 单元测试                | done        |      |
| T-004 | 实现 config_store.py              | done        |      |
| T-005 | config_store.py 单元测试          | done        |      |
| T-006 | 实现 path_mapper.py               | done        |      |
| T-007 | path_mapper.py 单元测试           | done        |      |
| T-008 | 实现 adapters/base.py             | done        |      |
| T-009 | 实现四个 ToolAdapter              | done        |      |
| T-010 | ToolAdapter 单元测试              | done        |      |
| T-011 | 实现 file_collector.py            | done        |      |
| T-012 | file_collector.py 单元测试        | done        |      |
| T-013 | 实现 git_repo.py                  | done        |      |
| T-014 | git_repo.py 单元测试              | done        |      |
| T-015 | 实现 github_client.py             | done        |      |
| T-016 | github_client.py 单元测试         | done        |      |
| T-017 | 实现 manifest.py                  | done        |      |
| T-018 | manifest.py 单元测试              | done        |      |
| T-019 | 实现 sync_engine.py               | done        |      |
| T-020 | sync_engine.py 单元测试           | done        |      |
| T-021 | 实现 cli.py                       | done        |      |
| T-022 | cli.py 集成测试                   | done        |      |
| T-023 | F-001 修复路径遍历漏洞            | done        |      |
| T-024 | F-001 测试路径遍历防护            | done        |      |
| T-025 | F-002 修复 Token 明文输入         | done        |      |
| T-026 | F-003 修复 config.json 文件权限   | done        |      |
| T-027 | F-003 测试文件权限                | done        |      |
| T-028 | F-004 修复路径拼接脆弱性          | done        |      |
| T-029 | F-004 测试路径拼接                | done        |      |
| T-030 | F-005 改进二进制文件检测          | done        |      |
| T-031 | F-005 测试二进制检测              | done        |      |

---

## 任务详情

#### T-001 — 初始化项目结构与 pyproject.toml

**Goal:** 建立可运行的 uv 项目骨架，确保 `uv tool install` 流程可用。

**Requirements:**
- 创建 `pyproject.toml`，配置 `[project]`、`[project.scripts]`（`ai-sync = "ai_sync.cli:app"`）
- 添加依赖：`typer`、`gitpython`、`PyGithub`、`rich`、`pydantic>=2.0`
- 添加开发依赖：`pytest`、`pytest-cov`
- 创建 `src/ai_sync/__init__.py`、`tests/__init__.py`
- 确认 `uv sync` 成功，`uv run pytest` 可执行（空测试通过）

**Acceptance Criteria:**
- `uv sync` 无报错
- `uv run pytest tests/` 输出 "no tests ran" 或通过
- `uv run ai-sync --help` 输出帮助信息（即使命令为空）

**References:** `plan.md § 项目结构`、`plan.md § 技术决策`

**Implementation Summary:** *(done 后填写)*

---

#### T-002 — 实现 models.py

**Goal:** 定义所有 Pydantic v2 数据模型，作为全项目的数据契约。

**Requirements:**
- `Platform(StrEnum)` — `"darwin"` / `"linux"` / `"windows"`
- `AppConfig(BaseModel)` — `github_token: str`、`repo_url: str`
- `Manifest(BaseModel)` — `version: str`、`last_push: datetime`、`source_os: Platform`、`source_home: str`、`tools: list[str]`
- `SyncItem(BaseModel)` — `local_path: Path`、`repo_path: str`、`is_dir: bool`、`optional: bool = False`
- `CollectedFile(BaseModel)` — `repo_path: str`、`content: bytes`、`is_binary: bool`
- `StatusEntry(BaseModel)` — `path: str`、`state: Literal["added","modified","deleted","unchanged"]`
- 自定义异常类层次：`AiSyncError` → `ConfigNotFoundError`、`RepoNotInitializedError`、`GitOperationError`、`GitHubAPIError`

**Acceptance Criteria:**
- 所有模型可正常实例化和序列化
- T-003 测试全部通过

**References:** `plan.md § Step 1`

**Implementation Summary:** *(done 后填写)*

---

#### T-003 — models.py 单元测试

**Goal:** 验证所有数据模型的实例化、验证、序列化行为。

**Requirements:**
- 测试每个模型的正常实例化
- 测试字段类型校验（传入错误类型应抛 `ValidationError`）
- 测试 `Platform` 枚举值
- 测试异常类继承关系

**Acceptance Criteria:**
- `uv run pytest tests/test_models.py -v` 全部通过
- 覆盖率 ≥ 80%

**References:** `plan.md § Step 1`

**Implementation Summary:** *(done 后填写)*

---

#### T-004 — 实现 config_store.py

**Goal:** 封装 `~/.config/ai-sync/config.json` 的读写操作。

**Requirements:**
- `ConfigStore` 类，构造函数接收 `config_path: Path`（默认 `~/.config/ai-sync/config.json`）
- `load() -> AppConfig` — 文件不存在时抛 `ConfigNotFoundError`，JSON 格式错误时抛有意义的错误
- `save(config: AppConfig) -> None` — 自动创建父目录，以缩进 JSON 写入
- `exists() -> bool`

**Acceptance Criteria:**
- T-005 测试全部通过

**References:** `plan.md § Step 2`

**Implementation Summary:** *(done 后填写)*

---

#### T-005 — config_store.py 单元测试

**Goal:** 验证配置读写的正常路径和错误路径。

**Requirements:**
- 测试 `save()` 后 `load()` 返回相同数据
- 测试文件不存在时 `load()` 抛 `ConfigNotFoundError`
- 测试 `exists()` 在文件存在/不存在时的返回值
- 使用 `tmp_path` fixture，不写入真实 home 目录

**Acceptance Criteria:**
- `uv run pytest tests/test_config_store.py -v` 全部通过
- 覆盖率 ≥ 80%

**References:** `plan.md § Step 2`

**Implementation Summary:** *(done 后填写)*

---

#### T-006 — 实现 path_mapper.py

**Goal:** 实现跨平台路径占位符的抽象与还原。

**Requirements:**
- `PathMapper(platform: Platform, home: Path)` — 依赖注入，不自行检测平台
- `get_placeholders() -> dict[str, str]` — 返回占位符→真实路径的有序映射（长路径优先，避免部分替换）
- `abstract_paths(content: str) -> str` — 真实路径替换为占位符
- `restore_paths(content: str) -> str` — 占位符替换为真实路径
- `is_text_file(path: Path) -> bool` — 读取前 8KB 尝试 UTF-8 解码
- 路径替换同时处理正斜杠和反斜杠形式（Windows 兼容）

**Acceptance Criteria:**
- T-007 测试全部通过

**References:** `plan.md § Step 3`

**Implementation Summary:** *(done 后填写)*

---

#### T-007 — path_mapper.py 单元测试

**Goal:** 验证三个平台的路径抽象与还原的正确性。

**Requirements:**
- 测试 macOS / Linux / Windows 三个平台的 `abstract_paths` 和 `restore_paths`
- 测试 `abstract_paths(restore_paths(x)) == x` 的往返一致性
- 测试包含多个占位符的内容
- 测试 `is_text_file` 对文本文件和二进制文件的判断
- 测试长路径优先替换（避免 `{{HOME}}` 替换掉 `{{CLAUDE_HOME}}` 的一部分）

**Acceptance Criteria:**
- `uv run pytest tests/test_path_mapper.py -v` 全部通过
- 覆盖率 ≥ 80%

**References:** `plan.md § Step 3`

**Implementation Summary:** *(done 后填写)*

---

#### T-008 — 实现 adapters/base.py

**Goal:** 定义 `ToolAdapter` 抽象基类，作为所有工具适配器的契约。

**Requirements:**
- `ToolAdapter(ABC)` 含三个抽象方法：`tool_id`（property）、`get_sync_items()`、`get_base_dir()`
- 模块级 docstring，每个方法有完整 docstring

**Acceptance Criteria:**
- 无法直接实例化 `ToolAdapter`（抽象类）
- 子类实现所有方法后可正常实例化

**References:** `plan.md § Step 4`

**Implementation Summary:** *(done 后填写)*

---

#### T-009 — 实现四个 ToolAdapter

**Goal:** 实现 `ClaudeCodeAdapter`、`GeminiAdapter`、`OpenCodeAdapter`、`SharedSkillsAdapter`。

**Requirements:**

`ClaudeCodeAdapter`：
- `tool_id = "claude-code"`
- `get_base_dir()` 返回 `~/.claude`
- `get_sync_items()` 返回完整同步项列表（含 optional 项）

`GeminiAdapter`：
- `tool_id = "gemini"`
- `get_base_dir()` 返回 `~/.gemini`
- `get_sync_items()` 返回完整同步项列表

`OpenCodeAdapter`：
- `tool_id = "opencode"`
- `get_base_dir()` 按优先级检测：`~/.opencode.json` 存在则返回 `~/.`，否则返回 `~/.config/opencode`
- `get_sync_items()` 返回完整同步项列表（均为 optional）

`SharedSkillsAdapter`：
- `tool_id = "shared"`
- `get_sync_items()` 返回 `~/.skills/`（→ `shared/skills/`）和 `~/.agents/skills/`（→ `shared/agents/skills/`），均为 optional

**Acceptance Criteria:**
- T-010 测试全部通过

**References:** `plan.md § Step 5`

**Implementation Summary:** *(done 后填写)*

---

#### T-010 — ToolAdapter 单元测试

**Goal:** 验证四个 Adapter 返回正确的同步项列表。

**Requirements:**
- 测试每个 Adapter 的 `tool_id` 值
- 测试 `get_sync_items()` 返回的路径和 optional 标志
- 测试 `OpenCodeAdapter.get_base_dir()` 的路径检测逻辑（mock 文件系统）
- 使用 `tmp_path` 模拟 home 目录

**Acceptance Criteria:**
- `uv run pytest tests/adapters/ -v` 全部通过
- 覆盖率 ≥ 80%

**References:** `plan.md § Step 5`

**Implementation Summary:** *(done 后填写)*

---

#### T-011 — 实现 file_collector.py

**Goal:** 遍历 Adapter 的同步项，解析软链接，收集文件内容。

**Requirements:**
- `FileCollector` 类，构造函数接收 `mapper: PathMapper`
- `collect(adapter: ToolAdapter) -> list[CollectedFile]`
  - optional 项不存在时跳过（不报错）
  - 软链接用 `Path.resolve()` 解析，悬空链接输出 `rich` 警告并跳过
  - 目录递归遍历，跳过 Adapter 排除列表中的路径
  - 文本文件：读取内容，调用 `mapper.abstract_paths()` 替换路径
  - 二进制文件：直接读取原始字节，不做路径替换
- `_is_excluded(path: Path, exclude_patterns: list[str]) -> bool` — 私有方法

**Acceptance Criteria:**
- T-012 测试全部通过

**References:** `plan.md § Step 6`

**Implementation Summary:** *(done 后填写)*

---

#### T-012 — file_collector.py 单元测试

**Goal:** 验证文件收集、软链接解析、排除规则的正确性。

**Requirements:**
- 测试普通文件收集（文本 + 二进制）
- 测试软链接解析为真实内容
- 测试悬空软链接被跳过并输出警告
- 测试目录软链接递归复制内容
- 测试 optional 项不存在时跳过
- 测试排除规则生效
- 使用 `tmp_path` 构造测试文件系统

**Acceptance Criteria:**
- `uv run pytest tests/test_file_collector.py -v` 全部通过
- 覆盖率 ≥ 80%

**References:** `plan.md § Step 6`

**Implementation Summary:** *(done 后填写)*

---

#### T-013 — 实现 git_repo.py

**Goal:** 封装 gitpython 的 clone/pull/push/diff 操作。

**Requirements:**
- `GitRepo(repo_dir: Path, remote_url: str)`
- `clone() -> None` — 若已存在则跳过
- `pull() -> None` — fetch + merge，失败抛 `GitOperationError`
- `push(commit_message: str) -> None` — `git add -A` + commit + push，无变更时跳过
- `diff_files() -> list[str]` — 返回相对于 HEAD 有变更的文件路径列表
- `is_cloned() -> bool` — 检查 `.git` 目录是否存在

**Acceptance Criteria:**
- T-014 测试全部通过

**References:** `plan.md § Step 7`

**Implementation Summary:** *(done 后填写)*

---

#### T-014 — git_repo.py 单元测试

**Goal:** 验证 git 操作的正常路径和错误路径。

**Requirements:**
- 使用 `tmp_path` 创建本地 bare repo 作为 remote，测试 clone/pull/push 完整流程
- 测试 `push()` 在无变更时不创建空 commit
- 测试 `is_cloned()` 在 clone 前后的返回值
- 测试 git 操作失败时抛 `GitOperationError`

**Acceptance Criteria:**
- `uv run pytest tests/test_git_repo.py -v` 全部通过
- 覆盖率 ≥ 80%

**References:** `plan.md § Step 7`

**Implementation Summary:** *(done 后填写)*

---

#### T-015 — 实现 github_client.py

**Goal:** 封装 PyGithub 的仓库创建和检查操作。

**Requirements:**
- `GitHubClient(token: str)`
- `create_private_repo(name: str) -> str` — 创建私有仓库，返回 HTTPS clone URL，已存在时抛有意义错误
- `repo_exists(repo_url: str) -> bool` — 通过 URL 解析 owner/repo 后检查是否存在
- API 失败时抛 `GitHubAPIError`（含状态码）

**Acceptance Criteria:**
- T-016 测试全部通过

**References:** `plan.md § Step 8`

**Implementation Summary:** *(done 后填写)*

---

#### T-016 — github_client.py 单元测试

**Goal:** 验证 GitHub API 封装的正常路径和错误路径（使用 mock）。

**Requirements:**
- mock `PyGithub` 的 `Github` 类，不发起真实网络请求
- 测试 `create_private_repo()` 返回正确 URL
- 测试仓库已存在时的错误处理
- 测试 `repo_exists()` 的 True/False 两种情况
- 测试 API 失败时抛 `GitHubAPIError`

**Acceptance Criteria:**
- `uv run pytest tests/test_github_client.py -v` 全部通过
- 覆盖率 ≥ 80%

**References:** `plan.md § Step 8`

**Implementation Summary:** *(done 后填写)*

---

#### T-017 — 实现 manifest.py

**Goal:** 封装 `_manifest.json` 的读写操作。

**Requirements:**
- `ManifestManager(repo_dir: Path)`
- `read() -> Manifest | None` — 文件不存在返回 None，格式错误抛有意义错误
- `write(manifest: Manifest) -> None` — 以缩进 JSON 写入，自动创建父目录

**Acceptance Criteria:**
- T-018 测试全部通过

**References:** `plan.md § Step 9`

**Implementation Summary:** *(done 后填写)*

---

#### T-018 — manifest.py 单元测试

**Goal:** 验证 manifest 读写的正常路径和边界情况。

**Requirements:**
- 测试 `write()` 后 `read()` 返回相同数据
- 测试文件不存在时 `read()` 返回 None
- 使用 `tmp_path` fixture

**Acceptance Criteria:**
- `uv run pytest tests/test_manifest.py -v` 全部通过
- 覆盖率 ≥ 80%

**References:** `plan.md § Step 9`

**Implementation Summary:** *(done 后填写)*

---

#### T-019 — 实现 sync_engine.py

**Goal:** 编排 push/pull/status 完整流程。

**Requirements:**
- `SyncEngine` 通过构造函数接收所有依赖（`adapters`、`repo`、`mapper`、`collector`、`manifest_mgr`）
- `push() -> PushResult` — 收集所有 Adapter 文件 → 写入 repo_dir → 更新 manifest → git push
- `pull() -> PullResult` — git pull → 读取 repo_dir 文件 → 路径还原 → 写入本地（覆盖）
- `status() -> list[StatusEntry]` — 收集本地文件（抽象路径后）与 repo_dir 文件对比哈希
- `PushResult` / `PullResult` 为 Pydantic 模型，含文件数量、工具列表等统计信息

**Acceptance Criteria:**
- T-020 测试全部通过

**References:** `plan.md § Step 10`

**Implementation Summary:** *(done 后填写)*

---

#### T-020 — sync_engine.py 单元测试

**Goal:** 验证 push/pull/status 流程的正确性（使用 mock 依赖）。

**Requirements:**
- mock `GitRepo`、`FileCollector`、`ManifestManager`，不依赖真实文件系统和 git
- 测试 `push()` 调用链：collect → write files → write manifest → git push
- 测试 `pull()` 调用链：git pull → read files → restore paths → write local
- 测试 `status()` 正确识别 added/modified/deleted/unchanged
- 测试多个 Adapter 的文件不互相覆盖

**Acceptance Criteria:**
- `uv run pytest tests/test_sync_engine.py -v` 全部通过
- 覆盖率 ≥ 80%

**References:** `plan.md § Step 10`

**Implementation Summary:** *(done 后填写)*

---

#### T-021 — 实现 cli.py

**Goal:** 用 typer 实现四个 CLI 命令，组装依赖并调用 SyncEngine。

**Requirements:**
- `app = typer.Typer()`，入口为 `ai_sync.cli:app`
- `init` 命令：交互式询问 token + repo（支持自动创建或手动填写），写 config，clone 仓库
- `push` 命令：加载 config → 组装 SyncEngine → 调用 `push()`，rich 进度输出
- `pull` 命令：加载 config → 组装 SyncEngine → 调用 `pull()`，rich 进度输出
- `status` 命令：加载 config → 组装 SyncEngine → 调用 `status()`，rich 表格输出
- 所有 `AiSyncError` 子类在此层统一捕获，输出友好错误信息后以非零退出码退出

**Acceptance Criteria:**
- T-022 测试全部通过
- `uv run ai-sync --help` 显示四个命令

**References:** `plan.md § Step 11`

**Implementation Summary:** *(done 后填写)*

---

#### T-022 — cli.py 集成测试

**Goal:** 验证 CLI 命令的端到端行为（使用 typer 的 `CliRunner`）。

**Requirements:**
- 使用 `typer.testing.CliRunner` 调用命令
- mock `SyncEngine`、`ConfigStore`、`GitHubClient`，不依赖真实网络和文件系统
- 测试 `init` 命令在 token/repo 输入后写入 config
- 测试 `push` / `pull` / `status` 命令的正常输出格式
- 测试 config 不存在时 `push`/`pull`/`status` 输出友好错误并退出码非零
- 测试 `--help` 输出包含所有命令

**Acceptance Criteria:**
- `uv run pytest tests/test_cli.py -v` 全部通过
- 覆盖率 ≥ 80%

**References:** `plan.md § Step 11`

**Implementation Summary:** *(done 后填写)*
