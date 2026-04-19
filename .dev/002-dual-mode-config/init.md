# 需求 002 — dual-mode-config

## # Project Stage

```
project_stage: pre-launch
```

---

## # Spec

### 背景与动机

当前 `ai-sync init` 只支持一种配置模式：输入 GitHub Token + 仓库 URL，由 ai-sync 负责 clone 到 `~/.config/ai-sync/repo/`。

这对以下用户不友好：
- 使用 GitLab / Gitea / 自建 git server 的用户（无法通过 GitHub API 创建仓库）
- 已有本地克隆、自己管理 git 凭证的用户（不想再输入 token）
- 希望将 ai-sync 配置仓库与其他 dotfiles 仓库合并管理的用户

### 核心问题

`AppConfig` 模型与 `init` 命令强绑定 GitHub，导致其他托管平台和本地路径无法使用。

### 目标

将配置模式拆分为两种：

1. **Remote 模式**：用户提供远程仓库 URL，ai-sync 负责 clone 到默认目录。可选：通过 GitHub API 创建新仓库（需要 token）。
2. **Local 模式**：用户提供已有本地克隆的路径，ai-sync 直接使用该目录，不执行 clone。

`push` / `pull` / `status` 命令在两种模式下行为一致，git 操作均依赖仓库已有的 remote 配置。

---

## # Requirements

### 功能需求

**F-001 — 数据模型重构**
- 将 `AppConfig` 拆分为两个具体模型，使用 Pydantic v2 判别联合类型：
  ```python
  class RemoteConfig(BaseModel):
      mode: Literal["remote"] = "remote"
      repo_url: str
      token: str | None = None  # HTTPS 认证 token（可选，用于私有仓库）

  class LocalConfig(BaseModel):
      mode: Literal["local"] = "local"
      local_repo_path: Path

  AppConfig = Annotated[RemoteConfig | LocalConfig, Field(discriminator="mode")]
  ```
- `ConfigStore.load()` 改用 `TypeAdapter(AppConfig).validate_python(data)`

**F-002 — GitRepo 支持无 remote_url**
- `GitRepo.__init__` 的 `remote_url` 参数改为可选（`str | None = None`）
- `clone()` 在 `remote_url=None` 时直接跳过
- `pull()` / `push()` 使用仓库已有 remote，不依赖 `remote_url` 字段

**F-003 — init 命令双模式交互**
- 新增模式选择步骤：
  ```
  选择模式：
    1) Remote — 使用远程 git 仓库（GitHub / GitLab / Gitea / 自建…）
    2) Local  — 使用已有本地克隆（自己管理 git 凭证）
  ```
- Remote 模式流程：
  - 是否需要新建仓库？
    - 是 → 显示引导文字，指引用户手动在托管平台创建私有仓库并生成访问 token
  - 输入仓库 HTTPS clone URL
  - 是否需要 token 认证？（私有仓库需要）
    - 是 → 输入 token（隐藏输入），嵌入 URL 用于 git 认证
    - 否 → 跳过
  - clone 到 `~/.config/ai-sync/repo/`
- Local 模式流程：
  - 输入本地路径
  - 校验：路径存在 + 含 `.git/` 目录
  - 保存 `LocalConfig`，不执行 clone

**F-004 — _build_engine() 双模式分支**
- `RemoteConfig` → `repo_dir = ~/.config/ai-sync/repo/`，`remote_url = config.repo_url`（含 token 时已嵌入 URL）
- `LocalConfig` → `repo_dir = config.local_repo_path`，`remote_url = None`
- 两种模式均不再需要 `GitHubClient`（GitHub API 调用已移除）

### 技术需求

- Python 3.11+，Pydantic v2
- 移除 `PyGithub` 依赖（`github_client.py` 及相关测试一并删除）
- 不引入新依赖
- 现有 `config.json`（无 `mode` 字段）向后兼容：`ConfigStore.load()` 检测到无 `mode` 字段时自动注入 `"mode": "remote"` 后再解析

### 错误处理

- Local 模式：路径不存在 → 友好提示 + 退出码 1
- Local 模式：路径无 `.git/` → 提示"不是 git 仓库" + 退出码 1
- Remote 模式：clone 失败 → 现有 `GitOperationError` 处理

---

## # Action Items

**Prerequisite documents**（不需要）

**Required documents**（按顺序）：
- [ ] `generated/plan.md`              — Phase 04
- [ ] `generated/tasks.md`             — Phase 05
- [ ] `generated/start-and-resume.md`  — Phase 06（任务执行前必须存在）

---

## # Constitution

### Python 编码规范

- 所有标识符、注释、文档字符串使用英文
- 所有函数参数和返回值必须有类型注解
- 遵循 Google Style Guide 编写 docstring
- 每个文件、公共类、公共函数必须有文档注释
- DRY 原则，单一职责，避免深层嵌套
- 错误处理：显式处理，不静默吞异常，错误信息有意义且可操作

### 测试规范

- 每个模块的测试在进入下一个任务前必须通过
- 测试文件覆盖：正常路径、边界情况、错误/异常情况
- 核心逻辑覆盖率 ≥ 80%
- 使用 `tmp_path` fixture，不写入真实 home 目录
- 测试文件命名：`test_*.py`
