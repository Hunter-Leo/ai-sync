# 实现计划 — 002 dual-mode-config

## 项目结构

仅列出受影响的文件（`+` 新增，`~` 修改，`-` 删除）：

```
src/ai_sync/
~ models.py            — AppConfig 拆分为 RemoteConfig | LocalConfig 判别联合
~ config_store.py      — load() 改用 TypeAdapter，加向后兼容迁移
~ git_repo.py          — remote_url 改为可选
~ cli.py               — init 双模式交互，_build_engine() 双分支
- github_client.py     — 删除（GitHub API 调用移除）

pyproject.toml         — 移除 PyGithub 依赖

tests/
~ test_models.py       — 新增两种 config 的序列化/反序列化测试
~ test_config_store.py — 新增两种类型的 save/load 测试，向后兼容测试
~ test_git_repo.py     — 新增 remote_url=None 时 clone 跳过的测试
~ test_cli.py          — 更新 init 测试，覆盖 remote/local 两种模式
- test_github_client.py — 删除
```

---

## 技术决策

- **Python 3.11+，Pydantic v2**：使用 `Annotated[RemoteConfig | LocalConfig, Field(discriminator="mode")]` 实现判别联合，`TypeAdapter` 处理联合类型的反序列化
- **移除 PyGithub**：GitHub API 调用（创建仓库）改为引导用户手动操作，消除外部 API 依赖
- **token 嵌入 URL**：HTTPS 认证通过 `https://<token>@host/repo.git` 实现，在 `_build_engine()` 中构造，不修改 `GitRepo` 内部逻辑

---

## 实现路径

### Step 1 — models.py

将 `AppConfig` 替换为判别联合：

```python
class RemoteConfig(BaseModel):
    mode: Literal["remote"] = "remote"
    repo_url: str
    token: str | None = None  # HTTPS 认证，可选

class LocalConfig(BaseModel):
    mode: Literal["local"] = "local"
    local_repo_path: Path

AppConfig = Annotated[RemoteConfig | LocalConfig, Field(discriminator="mode")]
```

同时删除 `GitHubAPIError`（`github_client.py` 删除后不再需要）。

### Step 2 — config_store.py

- `load()` 改用 `TypeAdapter(AppConfig).validate_python(data)`
- 向后兼容：读取 JSON 后，若无 `mode` 字段则注入 `"mode": "remote"`
- `save()` 使用 `model.model_dump(mode="json")` 序列化（Path 需转为字符串）

### Step 3 — git_repo.py

- `__init__` 签名：`remote_url: str | None = None`
- `clone()`：`remote_url` 为 `None` 时直接返回（不执行 clone）
- `pull()` / `push()`：使用仓库已有 remote，不依赖 `self._remote_url`（当前实现已通过 `repo.remotes.origin` 操作，无需改动）

### Step 4 — cli.py

**init 命令重构：**

```
选择模式（1=Remote / 2=Local）

Remote:
  → 是否需要新建仓库？（显示引导文字）
  → 输入仓库 HTTPS clone URL
  → 是否需要 token？→ 输入 token（隐藏）
  → 构造带 token 的 URL → clone → 保存 RemoteConfig

Local:
  → 输入本地路径
  → 校验：exists() + (path / ".git").is_dir()
  → 保存 LocalConfig
```

**_build_engine() 重构：**

```python
if isinstance(config, RemoteConfig):
    effective_url = _embed_token(config.repo_url, config.token)
    repo = GitRepo(repo_dir=_DEFAULT_REPO_DIR, remote_url=effective_url)
elif isinstance(config, LocalConfig):
    repo = GitRepo(repo_dir=config.local_repo_path, remote_url=None)
```

`_embed_token(url, token)` 私有函数：token 非空时将其嵌入 URL，否则原样返回。

### Step 5 — 删除 github_client.py 和 test_github_client.py

### Step 6 — pyproject.toml

移除 `PyGithub>=2.0.0` 依赖项。

### Step 7 — 更新测试

各模块测试随对应实现步骤同步完成（不单独列为最后一步）。

---

## 关键技术点

**判别联合的序列化**

Pydantic v2 的 `model_dump(mode="json")` 会将 `Path` 序列化为字符串，`load()` 时 `TypeAdapter` 会自动将字符串还原为 `Path`。`config.json` 示例：

```json
{"mode": "remote", "repo_url": "https://github.com/user/repo.git", "token": null}
{"mode": "local", "local_repo_path": "/Users/alice/dotfiles/ai-sync-config"}
```

**向后兼容迁移**

旧 `config.json` 格式（无 `mode` 字段）：
```json
{"github_token": "ghp_xxx", "repo_url": "https://..."}
```
迁移后自动变为：
```json
{"mode": "remote", "repo_url": "https://...", "token": "ghp_xxx"}
```
注意：旧字段名 `github_token` → 新字段名 `token`，迁移时需重命名。

**token 安全**

token 嵌入 URL 后存入 `config.json`（权限 0600）。`GitRepo` 不感知 token，只接收完整 URL。

**错误处理**

- Local 模式路径校验失败 → `typer.BadParameter` 或友好提示 + `Exit(1)`
- Remote clone 失败 → 现有 `GitOperationError` 处理链不变

---

## Out of Scope

- pull 冲突保护（B-002，单独需求）
- manifest-only 同步模式（B-001，单独需求）
- GitLab / Gitea API 集成（用户自行管理 token 和仓库创建）
- SSH 认证支持（依赖系统 git 配置，不在本需求范围内）

---

## Design Compliance Review

- [x] **SRP** — `RemoteConfig` 和 `LocalConfig` 各自只描述一种配置模式；`_build_engine()` 是组合根，if/else 分支在 CLI 层可接受
- [x] **OCP** — 新增配置模式只需新增模型类，不修改 `SyncEngine` / `GitRepo` 等业务逻辑
- [x] **LSP** — 两种 config 通过判别联合使用，调用方通过 `isinstance` 分支处理，不存在替换问题
- [x] **ISP** — 模型字段精简，无冗余
- [x] **DIP** — `SyncEngine` 依赖 `GitRepo` 抽象，不感知 config 类型
- [x] **Constitution** — 无硬编码 secret，无重复逻辑，无需为每种新 mode 修改业务层
