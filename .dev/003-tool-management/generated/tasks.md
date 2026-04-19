# 任务列表 — 003-tool-management

## 状态表

| ID    | 任务名称                                              | 状态        | 备注 |
|-------|-------------------------------------------------------|-------------|------|
| T-001 | models.py — 新增 managed_tools 字段                   | done        |      |
| T-002 | 测试 managed_tools 数据模型                           | done        |      |
| T-003 | git_repo.py — 新增分支管理方法                        | done        |      |
| T-004 | 测试 GitRepo 分支管理方法                             | done        |      |
| T-005 | sync_engine.py — 修复 push 完整镜像                   | done        |      |
| T-006 | 测试 push 完整镜像语义                                | done        |      |
| T-007 | cli.py — 实现 _discover_tools() + _backup_branch_name() | done      |      |
| T-008 | cli.py — 实现 _backup_to_branch()                     | done        |      |
| T-009 | cli.py — 实现 _handle_conflict()                      | done        |      |
| T-010 | cli.py — 增强 init 命令                               | done        |      |
| T-011 | cli.py — 增强 pull 命令（pull 前调用 _backup_to_branch） | done     |      |
| T-012 | cli.py — 新增 manage 命令（list/add/remove）          | done        |      |
| T-013 | cli.py — _build_engine() 按 managed_tools 过滤 adapter | done      |      |
| T-014 | 测试增强后的 init 命令                                | done        |      |
| T-015 | 测试 pull 的 backup 分支行为                          | done        |      |
| T-016 | 测试 manage 命令                                      | done        |      |
| T-017 | 测试 _build_engine() adapter 过滤逻辑                 | done        |      |

---

## 任务详情

#### T-001 — models.py — 新增 managed_tools 字段

**Goal:** 在 `RemoteConfig` 和 `LocalConfig` 中新增 `managed_tools: list[str]`，默认空列表，向后兼容旧 config。

**Requirements:**
- `RemoteConfig` 新增 `managed_tools: list[str] = []`
- `LocalConfig` 新增 `managed_tools: list[str] = []`
- 旧 config.json 无此字段时，反序列化默认为 `[]`
- 字段定义遵循 Pydantic v2 `Annotated[..., Field(...)]` 格式

**Acceptance Criteria:**
- `RemoteConfig()` 和 `LocalConfig(local_repo_path=...)` 均可不传 `managed_tools` 正常实例化
- `model_dump(mode="json")` 输出包含 `managed_tools` 字段
- 旧格式 JSON（无 `managed_tools`）可正常反序列化，值为 `[]`

**References:** `plan.md § 数据模型`, `src/ai_sync/models.py`

**Implementation Summary:** *(done 后填写)*

---

#### T-002 — 测试 managed_tools 数据模型

**Goal:** 验证 `managed_tools` 字段的序列化、反序列化和向后兼容行为。

**Requirements:**
- 测试 `RemoteConfig` / `LocalConfig` 默认值为 `[]`
- 测试传入工具列表后正确保存和序列化
- 测试旧格式 JSON（无 `managed_tools`）反序列化为 `[]`（在 `test_config_store.py` 中）

**Acceptance Criteria:**
- 所有新增测试通过，无回归

**References:** `tests/test_models.py`, `tests/test_config_store.py`

**Implementation Summary:** *(done 后填写)*

---

#### T-003 — git_repo.py — 新增分支管理方法

**Goal:** 为 `GitRepo` 新增 4 个分支操作方法，支持 backup 分支的创建、提交和推送。

**Requirements:**
- `checkout_or_create_branch(name: str) -> None`：分支存在则切换，不存在则创建并切换
- `commit_all(message: str) -> bool`：`git add -A` + commit；无变更时返回 `False`，不抛异常
- `push_branch(name: str) -> None`：push 指定分支到 origin；Local 模式（`remote_url=None`）时静默跳过
- `checkout_branch(name: str) -> None`：切换到已存在的分支
- 所有方法在未 clone 时抛 `RepoNotInitializedError`
- git 操作失败时抛 `GitOperationError`

**Acceptance Criteria:**
- 4 个方法均有完整 docstring
- Local 模式下 `push_branch` 不抛异常

**References:** `plan.md § GitRepo 新增方法`, `src/ai_sync/git_repo.py`

**Implementation Summary:** *(done 后填写)*

---

#### T-004 — 测试 GitRepo 分支管理方法

**Goal:** 验证 4 个新增方法的正常流程、边界情况和错误处理。

**Requirements:**
- 测试 `checkout_or_create_branch`：新分支创建、已有分支切换
- 测试 `commit_all`：有变更返回 True，无变更返回 False
- 测试 `push_branch`：Remote 模式推送成功；Local 模式（`remote_url=None`）静默跳过
- 测试 `checkout_branch`：切换到已有分支；切换到不存在分支抛 `GitOperationError`
- 测试未 clone 时调用任意方法抛 `RepoNotInitializedError`

**Acceptance Criteria:**
- 所有新增测试通过，无回归

**References:** `tests/test_git_repo.py`

**Implementation Summary:** *(done 后填写)*

---

#### T-005 — sync_engine.py — 修复 push 完整镜像

**Goal:** `push` 前先清空每个被管理工具的 repo 子目录，再写入当前本地文件，实现完整镜像语义。

**Requirements:**
- 在写入文件前，对每个 adapter 执行 `shutil.rmtree(repo_dir / adapter.tool_id)`
- 清空后重建目录（`mkdir(parents=True, exist_ok=True)`）
- 仅清空被管理工具的目录，不触碰 `_manifest.json` 等其他文件
- 导入 `shutil`（标准库，无新依赖）

**Acceptance Criteria:**
- push 后，本地已删除的文件不再出现在 repo 中
- `_manifest.json` 不受影响

**References:** `plan.md § push 完整镜像修复`, `src/ai_sync/sync_engine.py:92-131`

**Implementation Summary:** *(done 后填写)*

---

#### T-006 — 测试 push 完整镜像语义

**Goal:** 验证 push 后 repo 中不再保留本地已删除的文件。

**Requirements:**
- 测试：push 后本地删除的文件在 repo 中消失
- 测试：push 后新增的文件出现在 repo 中
- 测试：push 后修改的文件内容更新
- 测试：`_manifest.json` 不被清空

**Acceptance Criteria:**
- 所有新增测试通过，无回归

**References:** `tests/test_sync_engine.py`

**Implementation Summary:** *(done 后填写)*

---

#### T-007 — cli.py — 实现 _discover_tools() + _backup_branch_name()

**Goal:** 实现工具发现和 backup 分支命名两个辅助函数。

**Requirements:**
- `_discover_tools(home: Path) -> list[str]`：
  - 扫描 `~/.claude/` → `claude-code`，`~/.gemini/` → `gemini`，`~/.config/opencode/` → `opencode`，`~/.skills/` → `shared-skills`
  - 只列出目录存在的工具，逐一 `typer.confirm` 询问用户
  - 返回用户选中的工具 ID 列表；无工具发现时提示并返回 `[]`
- `_backup_branch_name() -> str`：
  - `socket.gethostname().lower()` + `_detect_platform().value`
  - 格式：`backup/<hostname>-<platform>`（如 `backup/leoluo-macbook-darwin`）
  - hostname 中的空格替换为 `-`

**Acceptance Criteria:**
- 目录不存在的工具不出现在提示中
- 用户全部拒绝时返回 `[]`
- 分支名格式符合规范

**References:** `plan.md § init 工具发现`, `plan.md § backup 分支命名`, `src/ai_sync/cli.py`

**Implementation Summary:** *(done 后填写)*

---

#### T-008 — cli.py — 实现 _backup_to_branch()

**Goal:** 将本机当前配置快照 commit 到 backup 分支并推送到 remote。

**Requirements:**
- 函数签名：`_backup_to_branch(repo: GitRepo, engine: SyncEngine, repo_dir: Path) -> None`
- 收集本地当前文件（复用 SyncEngine 的 collector，同 push 逻辑）
- 清空 repo_dir 工具目录并写入当前文件（同 push 镜像写入）
- 调用 `repo.checkout_or_create_branch(_backup_branch_name())`
- 调用 `repo.commit_all(f"backup: pre-pull snapshot {datetime.now(tz=timezone.utc).isoformat()}")`
- 调用 `repo.push_branch(branch_name)`（失败时打印警告，不中止）
- 调用 `repo.checkout_branch("main")` 切回主分支

**Acceptance Criteria:**
- backup 分支有新 commit
- push 失败时不抛异常，打印警告后继续
- 切回 main 分支后函数返回

**References:** `plan.md § _backup_to_branch() 详细流程`, `src/ai_sync/cli.py`

**Implementation Summary:** *(done 后填写)*

---

#### T-009 — cli.py — 实现 _handle_conflict()

**Goal:** init 时检测冲突，调用 _backup_to_branch 后以远程为主执行 pull。

**Requirements:**
- 函数签名：`_handle_conflict(repo: GitRepo, engine: SyncEngine, repo_dir: Path, managed_tools: list[str], home: Path) -> None`
- 检测条件：repo_dir 下有工具目录文件 AND 本地被选工具目录有数据
- 有冲突：列出冲突工具名称 → 调用 `_backup_to_branch()` → 调用 `engine.pull()`
- 无冲突（repo 为空）：跳过，打印提示"仓库为空，请执行 ai-sync push"

**Acceptance Criteria:**
- repo 为空时不调用 backup 和 pull
- 有冲突时 backup 分支存在且 pull 被调用

**References:** `plan.md § init 冲突处理`, `src/ai_sync/cli.py`

**Implementation Summary:** *(done 后填写)*

---

#### T-010 — cli.py — 增强 init 命令

**Goal:** 将 `_discover_tools()` 和 `_handle_conflict()` 接入 `init` 流程。

**Requirements:**
- 模式选择后调用 `_discover_tools(home)` 获取 `managed_tools`
- clone/连接仓库后调用 `_handle_conflict()`
- 将 `managed_tools` 写入 config（`RemoteConfig` / `LocalConfig` 构造时传入）
- 流程顺序：模式选择 → 工具发现 → clone/连接 → 冲突处理 → 写入 config

**Acceptance Criteria:**
- `config.json` 包含正确的 `managed_tools` 字段
- 冲突场景下 backup 分支被创建，pull 被调用
- 无冲突场景下正常完成

**References:** `plan.md § init 流程`, `src/ai_sync/cli.py:49-134`

**Implementation Summary:** *(done 后填写)*

---

#### T-011 — cli.py — 增强 pull 命令

**Goal:** `pull` 命令在执行 `SyncEngine.pull()` 前调用 `_backup_to_branch()`。

**Requirements:**
- 在 `engine.pull()` 之前调用 `_backup_to_branch(repo, engine, repo_dir)`
- backup 失败（非 push 失败）时中止 pull 并报错
- 输出提示："正在备份本机配置到 backup 分支…"

**Acceptance Criteria:**
- pull 后 backup 分支有新 commit
- backup push 失败时仍继续执行 pull

**References:** `plan.md § pull 流程`, `src/ai_sync/cli.py:156-170`

**Implementation Summary:** *(done 后填写)*

---

#### T-012 — cli.py — 新增 manage 命令

**Goal:** 实现 `ai-sync manage list/add/remove` 子命令。

**Requirements:**
- 使用 `typer.Typer()` 创建 `manage_app`，挂载到主 `app`（`app.add_typer(manage_app, name="manage")`）
- `manage list`：打印 `managed_tools`；空列表提示"管理所有工具（向后兼容模式）"
- `manage add <tool>`：验证有效 ID → 检查重复 → 警告未安装 → 追加并保存
- `manage remove <tool>`：验证在列表中 → 移除并保存 → 提示下次 push 时清除
- 有效工具 ID 常量：`VALID_TOOL_IDS = {"claude-code", "gemini", "opencode", "shared-skills"}`

**Acceptance Criteria:**
- `ai-sync manage --help` 列出三个子命令
- 无效 tool ID 时 exit code 为 1
- config 修改后立即持久化

**References:** `plan.md § manage 命令流程`, `src/ai_sync/cli.py`

**Implementation Summary:** *(done 后填写)*

---

#### T-013 — cli.py — _build_engine() 按 managed_tools 过滤 adapter

**Goal:** `_build_engine()` 根据 `config.managed_tools` 决定实例化哪些 adapter。

**Requirements:**
- 定义模块级常量 `ADAPTER_MAP: dict[str, type[ToolAdapter]]`
- `managed_tools` 非空时：只实例化列表中的 adapter
- `managed_tools` 为空时：实例化全部 4 个 adapter（向后兼容）
- 无效 tool ID（不在 `ADAPTER_MAP` 中）打印警告并跳过，不崩溃

**Acceptance Criteria:**
- `managed_tools=["gemini"]` 时只有 `GeminiAdapter` 被实例化
- `managed_tools=[]` 时全部 4 个 adapter 被实例化
- 无回归（现有 push/pull/status 测试通过）

**References:** `plan.md § managed_tools 过滤逻辑`, `src/ai_sync/cli.py:210-255`

**Implementation Summary:** *(done 后填写)*

---

#### T-014 — 测试增强后的 init 命令

**Goal:** 验证 init 的工具发现、冲突处理、config 写入行为。

**Requirements:**
- 测试：发现工具后 config 包含正确的 `managed_tools`
- 测试：repo 为空时跳过冲突处理，不调用 backup
- 测试：repo 有数据 + 本地有数据时，backup 分支被创建，pull 被调用
- 测试：用户拒绝所有工具时 `managed_tools=[]`

**Acceptance Criteria:**
- 所有新增测试通过，无回归

**References:** `tests/test_cli.py`

**Implementation Summary:** *(done 后填写)*

---

#### T-015 — 测试 pull 的 backup 分支行为

**Goal:** 验证 pull 命令在执行前正确创建 backup 分支 commit。

**Requirements:**
- 测试：pull 后 backup 分支有新 commit
- 测试：backup push 失败时 pull 仍然继续执行
- 测试：backup commit 内容包含当前本地文件（路径已抽象）

**Acceptance Criteria:**
- 所有新增测试通过，无回归

**References:** `tests/test_cli.py`

**Implementation Summary:** *(done 后填写)*

---

#### T-016 — 测试 manage 命令

**Goal:** 验证 manage list/add/remove 的正常流程和错误处理。

**Requirements:**
- 测试 `manage list`：空列表和非空列表的输出
- 测试 `manage add`：正常添加、重复添加（提示）、无效 ID（exit 1）、本地目录不存在时的警告
- 测试 `manage remove`：正常移除、移除不存在的工具（exit 1）
- 测试每次操作后 config 正确持久化

**Acceptance Criteria:**
- 所有新增测试通过，无回归

**References:** `tests/test_cli.py`

**Implementation Summary:** *(done 后填写)*

---

#### T-017 — 测试 _build_engine() adapter 过滤逻辑

**Goal:** 验证 `_build_engine()` 根据 `managed_tools` 正确过滤 adapter。

**Requirements:**
- 测试：`managed_tools=["gemini"]` 时 SyncEngine 只收到 GeminiAdapter
- 测试：`managed_tools=[]` 时 SyncEngine 收到全部 4 个 adapter
- 测试：包含无效 tool ID 时打印警告，不崩溃，其余有效 adapter 正常实例化

**Acceptance Criteria:**
- 所有新增测试通过，无回归

**References:** `tests/test_cli.py`

**Implementation Summary:** *(done 后填写)*
