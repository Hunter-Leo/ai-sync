# 任务清单

**需求编号：** 002  
**阶段：** Phase 05 — 任务规划  
**日期：** 2026-04-19  
**参考：** `plan.md`

---

## 状态表

| ID    | 任务名称                                      | 状态        | 备注 |
|-------|-----------------------------------------------|-------------|------|
| T-001 | 重构 models.py（判别联合）                    | done        |      |
| T-002 | models.py 单元测试                            | done        |      |
| T-003 | 重构 config_store.py（TypeAdapter + 迁移）    | done        |      |
| T-004 | config_store.py 单元测试                      | done        |      |
| T-005 | 重构 git_repo.py（remote_url 可选）           | done        |      |
| T-006 | git_repo.py 单元测试                          | done        |      |
| T-007 | 重构 cli.py（init 双模式 + _build_engine）    | done        |      |
| T-008 | cli.py 集成测试                               | done        |      |
| T-009 | 清理（删除 github_client，移除 PyGithub 依赖）| done        |      |

---

## 任务详情

#### T-001 — 重构 models.py（判别联合）

**Goal:** 将 `AppConfig` 替换为 `RemoteConfig | LocalConfig` 判别联合，删除 `GitHubAPIError`。

**Requirements:**
- 新增 `RemoteConfig(BaseModel)`：`mode: Literal["remote"]`、`repo_url: str`、`token: str | None = None`
- 新增 `LocalConfig(BaseModel)`：`mode: Literal["local"]`、`local_repo_path: Path`
- `AppConfig = Annotated[RemoteConfig | LocalConfig, Field(discriminator="mode")]`
- 删除原 `AppConfig` 类
- 删除 `GitHubAPIError`（github_client.py 将在 T-009 删除）

**Acceptance Criteria:**
- T-002 测试全部通过
- 无 linting 错误

**References:** `plan.md § Step 1`

**Implementation Summary:** *(done 后填写)*

---

#### T-002 — models.py 单元测试

**Goal:** 验证两种 config 模型的实例化、序列化、判别路由行为。

**Requirements:**
- 测试 `RemoteConfig` 正常实例化（含 token / 不含 token）
- 测试 `LocalConfig` 正常实例化
- 测试 `TypeAdapter(AppConfig).validate_python({"mode": "remote", ...})` 路由到 `RemoteConfig`
- 测试 `TypeAdapter(AppConfig).validate_python({"mode": "local", ...})` 路由到 `LocalConfig`
- 测试 `mode` 字段缺失时抛 `ValidationError`
- 测试 `model_dump(mode="json")` 将 `Path` 序列化为字符串

**Acceptance Criteria:**
- `uv run pytest tests/test_models.py -v` 全部通过
- 覆盖率 ≥ 80%

**References:** `plan.md § Step 1`

**Implementation Summary:** *(done 后填写)*

---

#### T-003 — 重构 config_store.py（TypeAdapter + 向后兼容迁移）

**Goal:** 更新 `ConfigStore.load()` 以支持判别联合，并自动迁移旧格式 config.json。

**Requirements:**
- `load()` 改用 `TypeAdapter(AppConfig).validate_python(data)`
- 向后兼容：读取 JSON 后，若无 `mode` 字段则执行迁移：
  - 注入 `"mode": "remote"`
  - 将旧字段 `github_token` 重命名为 `token`（若存在）
- `save()` 使用 `config.model_dump(mode="json")` 序列化（确保 Path 转为字符串）
- 返回类型注解更新为 `AppConfig`（即 `RemoteConfig | LocalConfig`）

**Acceptance Criteria:**
- T-004 测试全部通过

**References:** `plan.md § Step 2`

**Implementation Summary:** *(done 后填写)*

---

#### T-004 — config_store.py 单元测试

**Goal:** 验证两种 config 类型的读写，以及旧格式的自动迁移。

**Requirements:**
- 测试 `save(RemoteConfig(...))` 后 `load()` 返回 `RemoteConfig`
- 测试 `save(LocalConfig(...))` 后 `load()` 返回 `LocalConfig`
- 测试旧格式（无 `mode`，含 `github_token`）自动迁移为 `RemoteConfig`（`token` 字段正确）
- 测试旧格式（无 `mode`，无 `github_token`）自动迁移为 `RemoteConfig`（`token=None`）
- 使用 `tmp_path` fixture

**Acceptance Criteria:**
- `uv run pytest tests/test_config_store.py -v` 全部通过
- 覆盖率 ≥ 80%

**References:** `plan.md § Step 2`

**Implementation Summary:** *(done 后填写)*

---

#### T-005 — 重构 git_repo.py（remote_url 可选）

**Goal:** 将 `remote_url` 改为可选参数，`clone()` 在无 remote_url 时跳过。

**Requirements:**
- `__init__` 签名：`remote_url: str | None = None`
- `clone()`：`self._remote_url is None` 时直接返回，不执行任何 git 操作
- `pull()` / `push()`：使用 `repo.remotes.origin`，不依赖 `self._remote_url`（验证现有实现是否已满足）
- 更新 docstring

**Acceptance Criteria:**
- T-006 测试全部通过
- 现有 git_repo 测试无回归

**References:** `plan.md § Step 3`

**Implementation Summary:** *(done 后填写)*

---

#### T-006 — git_repo.py 单元测试

**Goal:** 验证 `remote_url=None` 时 clone 跳过，push/pull 正常使用已有 remote。

**Requirements:**
- 测试 `remote_url=None` 时 `clone()` 不抛异常、不创建任何文件
- 测试 `remote_url=None` 时 `is_cloned()` 返回 False（目录不存在时）
- 测试已有本地 repo（`remote_url=None`）的 `push()` 和 `pull()` 正常工作
- 现有测试（remote_url 非空）全部保持通过

**Acceptance Criteria:**
- `uv run pytest tests/test_git_repo.py -v` 全部通过
- 覆盖率 ≥ 80%

**References:** `plan.md § Step 3`

**Implementation Summary:** *(done 后填写)*

---

#### T-007 — 重构 cli.py（init 双模式 + _build_engine）

**Goal:** 重构 `init` 命令支持 Remote / Local 双模式，更新 `_build_engine()` 双分支。

**Requirements:**

`init` 命令：
- 模式选择：`typer.prompt("Mode (1=Remote, 2=Local)")`
- Remote 流程：
  - 询问是否需要新建仓库（显示引导文字，指引用户手动创建）
  - 输入仓库 HTTPS clone URL
  - 询问是否需要 token（`hide_input=True`）
  - 构造 `RemoteConfig`，clone 到 `_DEFAULT_REPO_DIR`
- Local 流程：
  - 输入本地路径
  - 校验：`path.exists()` 且 `(path / ".git").is_dir()`，失败则友好提示 + `Exit(1)`
  - 构造 `LocalConfig`，不执行 clone

`_build_engine()`：
- `isinstance(config, RemoteConfig)` → `repo_dir = _DEFAULT_REPO_DIR`，`remote_url = _embed_token(config.repo_url, config.token)`
- `isinstance(config, LocalConfig)` → `repo_dir = config.local_repo_path`，`remote_url = None`
- 新增私有函数 `_embed_token(url: str, token: str | None) -> str`

**Acceptance Criteria:**
- T-008 测试全部通过
- `uv run ai-sync --help` 正常显示

**References:** `plan.md § Step 4`

**Implementation Summary:** *(done 后填写)*

---

#### T-008 — cli.py 集成测试

**Goal:** 验证 init 双模式和 _build_engine 双分支的端到端行为。

**Requirements:**
- 测试 Remote 模式 init（无 token）：保存 `RemoteConfig`，调用 clone
- 测试 Remote 模式 init（含 token）：token 嵌入 URL
- 测试 Local 模式 init：保存 `LocalConfig`，不调用 clone
- 测试 Local 模式 init 路径不存在：退出码 1，友好提示
- 测试 Local 模式 init 路径无 `.git/`：退出码 1，友好提示
- 测试 `_build_engine()` 在 `RemoteConfig` 下使用 `_DEFAULT_REPO_DIR`
- 测试 `_build_engine()` 在 `LocalConfig` 下使用 `local_repo_path`
- mock `GitRepo`、`ConfigStore`，不依赖真实文件系统和网络

**Acceptance Criteria:**
- `uv run pytest tests/test_cli.py -v` 全部通过
- 覆盖率 ≥ 80%

**References:** `plan.md § Step 4`

**Implementation Summary:** *(done 后填写)*

---

#### T-009 — 清理（删除 github_client，移除 PyGithub 依赖）

**Goal:** 移除所有 GitHub API 相关代码和依赖。

**Requirements:**
- 删除 `src/ai_sync/github_client.py`
- 删除 `tests/test_github_client.py`
- 从 `pyproject.toml` 的 `dependencies` 中移除 `PyGithub>=2.0.0`
- 检查 `cli.py` 中的 `from ai_sync.github_client import GitHubClient` import 已移除（T-007 应已处理）
- 运行 `uv run pytest` 确认全部测试通过

**Acceptance Criteria:**
- `uv run pytest` 全部通过，无 import 错误
- `uv sync` 成功（PyGithub 不再安装）

**References:** `plan.md § Step 5 & 6`

**Implementation Summary:** *(done 后填写)*
