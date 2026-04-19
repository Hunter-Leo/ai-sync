# 实现计划 — 003-tool-management

---

## 项目结构（仅受影响文件）

```
src/ai_sync/
├── models.py          [CHANGED] RemoteConfig/LocalConfig 新增 managed_tools 字段
├── git_repo.py        [CHANGED] 新增分支管理方法（backup 分支支持）
├── cli.py             [CHANGED] 增强 init/pull 流程；新增 manage 命令
└── sync_engine.py     [CHANGED] push 修复：先清空工具目录再写入

tests/
├── test_models.py     [CHANGED] 新增 managed_tools 相关测试
├── test_git_repo.py   [CHANGED] 新增分支管理方法测试
├── test_cli.py        [CHANGED] 新增 init 工具发现、backup 分支、manage 命令测试
└── test_sync_engine.py [CHANGED] 新增 push 完整镜像测试
```

---

## 技术决策

- Python 3.11+，Pydantic v2（现有）
- `shutil.rmtree` 清空工具目录（标准库，仅用于 push 镜像）
- `socket.gethostname()` 获取主机名，用于 backup 分支命名
- `datetime.now().strftime` 生成 backup commit 时间戳
- 无新增第三方依赖

---

## 完整软件流程图

### 1. 组件总览

```
┌─────────────────────────────────────────────────────────────────┐
│                          CLI 层                                  │
│                                                                  │
│   init ──► _init_remote()          manage list                  │
│            _init_local()           manage add <tool>            │
│            _discover_tools()       manage remove <tool>         │
│            _handle_conflict()                                    │
│            _backup_to_branch() ◄── pull（每次 pull 前备份）      │
│                                                                  │
│   push ──► _build_engine() ──► SyncEngine.push()               │
│   pull ──► _backup_to_branch()                                  │
│            _build_engine() ──► SyncEngine.pull()               │
│   status ► _build_engine() ──► SyncEngine.status()             │
└──────────────────────┬──────────────────────────────────────────┘
                       │ 依赖注入
┌──────────────────────▼──────────────────────────────────────────┐
│                       SyncEngine                                 │
│                                                                  │
│  adapters（由 managed_tools 过滤）                               │
│  ┌────────────┐  ┌────────────┐  ┌────────────┐                │
│  │ClaudeCode  │  │  Gemini    │  │  OpenCode  │  ...           │
│  │ Adapter    │  │  Adapter   │  │  Adapter   │                │
│  └────────────┘  └────────────┘  └────────────┘                │
│                                                                  │
│  FileCollector ──► PathMapper (abstract/restore)                │
│  GitRepo       ──► ManifestManager                              │
└─────────────────────────────────────────────────────────────────┘

GitRepo（新增方法）
  checkout_or_create_branch(name)  切换/创建分支
  commit_all(message)              git add -A + commit
  push_branch(name)                push 指定分支到 remote
  checkout_branch(name)            切换到指定分支
```

---

### 2. init 流程（增强后）

```
ai-sync init
     │
     ▼
已有 config.json?
  yes → 确认覆盖? no → 退出
  yes / no ↓
     ▼
选择模式（1=Remote / 2=Local）
     │
     ▼
_discover_tools(home)
  扫描本地目录是否存在:
    ~/.claude/          → claude-code    ✓/✗
    ~/.gemini/          → gemini         ✓/✗
    ~/.config/opencode/ → opencode       ✓/✗
    ~/.skills/          → shared-skills  ✓/✗
  列出已发现工具，用户逐一确认
  → managed_tools = [选中的工具]
     │
     ▼
Remote 模式?                    Local 模式?
  输入 URL + token               输入本地路径
  git clone                      验证 .git/ 存在
     │                                │
     └──────────────┬─────────────────┘
                    ▼
          _handle_conflict(repo, managed_tools, home)
                    │
     repo 有文件 AND 本地被选工具目录有数据?
          │ yes                        │ no
          ▼                            ▼
     列出冲突工具               跳过，提示执行 ai-sync push
     _backup_to_branch()
     （见下方详细流程）
     git pull（以远程为主）
                    │
                    ▼
          写入 config.json
          { managed_tools: [...] }
                    │
                    ▼
                  完成
```

---

### 3. _backup_to_branch() 详细流程

**在 pull 命令和 init 冲突处理中均调用此流程。**

```
_backup_to_branch(repo, adapters, repo_dir, home)
     │
     ▼
生成分支名：
  hostname = socket.gethostname()   → "leoluo-macbook"
  platform = darwin / linux / windows
  branch   = "backup/leoluo-macbook-darwin"
     │
     ▼
收集本地当前文件（FileCollector，同 push 逻辑）
  PathMapper.abstract_paths()  ← 真实路径 → {{占位符}}
     │
     ▼
清空 repo_dir/<tool_id>/ 并写入当前本地文件
（与 push 的镜像写入逻辑相同）
     │
     ▼
GitRepo.checkout_or_create_branch("backup/leoluo-macbook-darwin")
     │
     ▼
GitRepo.commit_all("backup: pre-pull snapshot 2026-04-19 12:00:00")
     │
     ▼
Remote 模式?
  yes → GitRepo.push_branch("backup/leoluo-macbook-darwin")
        push 失败? → 警告（非致命，本地 commit 已存在，继续）
  no  → 跳过 push
     │
     ▼
GitRepo.checkout_branch("main")
     │
     ▼
返回（调用方继续执行 pull）
```

---

### 4. push 流程（修复后）

```
ai-sync push
     │
     ▼
_build_engine()
  读取 config.json → managed_tools
  过滤 adapters → 只保留 managed_tools 中的工具
     │
     ▼
SyncEngine.push()
     │
     ▼
for each adapter in adapters:
  │
  ├─► 清空 repo_dir/<tool_id>/          ← 新增（完整镜像关键步骤）
  │     shutil.rmtree(tool_dir)
  │     tool_dir.mkdir()
  │
  ├─► FileCollector.collect(adapter)
  │     读取本地文件
  │     PathMapper.abstract_paths()     ← 真实路径 → {{占位符}}
  │
  └─► 写入 repo_dir/<tool_id>/<file>
     │
     ▼
写入 _manifest.json
     │
     ▼
GitRepo.push()
  git add -A    ← 删除操作已被正确 stage
  有变更? → git commit + git push origin main
  无变更? → 跳过，返回 committed=False
```

**修复前 vs 修复后：**

```
修复前（增量写入）:
  本地删了 ~/.claude/custom.md
  push → repo/claude-code/custom.md 仍然存在 ✗

修复后（完整镜像）:
  本地删了 ~/.claude/custom.md
  push → 先 rmtree(repo/claude-code/) → 重新写入
       → repo/claude-code/custom.md 不存在
       → git add -A stage 删除 ✓
```

---

### 5. pull 流程（增加 backup 步骤）

```
ai-sync pull
     │
     ▼
_build_engine()
  读取 config.json → managed_tools
  过滤 adapters
     │
     ▼
_backup_to_branch()              ← 新增：pull 前备份本机状态到分支
  → backup/leoluo-macbook-darwin 分支追加一个 commit
     │
     ▼
SyncEngine.pull()
     │
     ▼
GitRepo.pull()
  git pull origin main（Remote 模式）
  git pull（Local 模式，repo 有 remote 时）
     │
     ▼
遍历 repo_dir 所有文件:
  跳过 _ 开头文件（_manifest.json 等）
  跳过不在 managed_tools 中的工具目录
     │
     ▼
PathMapper.restore_paths()
  {{CLAUDE_HOME}} → /Users/leoluo/.claude
  {{HOME}}        → /Users/leoluo
     │
     ▼
写入本地文件（只写入，不删除本地多余文件）
```

**仓库分支结构示意：**

```
main                          ← 共享同步状态（所有机器共用）
backup/leoluo-macbook-darwin  ← 机器 A 每次 pull 前的快照（追加 commit）
backup/ubuntu-linux           ← 机器 B 每次 pull 前的快照（追加 commit）

git log backup/leoluo-macbook-darwin:
  backup: pre-pull snapshot 2026-04-19 14:00:00
  backup: pre-pull snapshot 2026-04-18 09:30:00
  backup: pre-pull snapshot 2026-04-17 11:00:00
```

---

### 6. manage 命令流程

```
ai-sync manage list
  读取 config.json → managed_tools
  打印列表（空列表提示"管理所有工具（向后兼容模式）"）

─────────────────────────────────────────────────

ai-sync manage add <tool>
  验证 tool 是有效 ID?
    no  → 报错退出（列出有效 ID）
  已在 managed_tools 中?
    yes → 提示"已在管理列表中"，退出
  本地目录存在?
    no  → 警告"未找到本地安装"（但继续）
  追加到 managed_tools → 写入 config.json

─────────────────────────────────────────────────

ai-sync manage remove <tool>
  验证 tool 在 managed_tools 中?
    no  → 报错退出
  从 managed_tools 移除 → 写入 config.json
  提示："repo 中的文件将在下次 push 时清除"
```

---

## 关键技术要点

### GitRepo 新增方法

```python
def checkout_or_create_branch(self, name: str) -> None:
    """切换到分支，不存在则创建。"""

def commit_all(self, message: str) -> bool:
    """git add -A + commit。无变更时返回 False。"""

def push_branch(self, name: str) -> None:
    """push 指定分支到 origin。"""

def checkout_branch(self, name: str) -> None:
    """切换到已存在的分支。"""
```

### backup 分支命名

```python
def _backup_branch_name() -> str:
    hostname = socket.gethostname().lower().replace(" ", "-")
    platform = _detect_platform().value   # "darwin" / "linux" / "windows"
    return f"backup/{hostname}-{platform}"
```

### managed_tools 过滤逻辑

```python
ADAPTER_MAP: dict[str, type[ToolAdapter]] = {
    "claude-code":    ClaudeCodeAdapter,
    "gemini":         GeminiAdapter,
    "opencode":       OpenCodeAdapter,
    "shared-skills":  SharedSkillsAdapter,
}

if config.managed_tools:
    adapters = [ADAPTER_MAP[t](home=home)
                for t in config.managed_tools if t in ADAPTER_MAP]
else:
    adapters = [cls(home=home) for cls in ADAPTER_MAP.values()]  # 向后兼容
```

### push 清空逻辑

```python
tool_dir = self._repo_dir / adapter.tool_id
if tool_dir.exists():
    shutil.rmtree(tool_dir)
tool_dir.mkdir(parents=True, exist_ok=True)
```

### 错误处理策略

| 场景 | 处理方式 |
|------|----------|
| manage add 无效 tool ID | `AiSyncError` → exit code 1 |
| backup 分支 checkout 失败 | `GitOperationError` → 中止 pull/init |
| backup commit 失败（无变更） | 正常，跳过 commit，继续 pull |
| backup push 失败 | 警告（非致命）→ 继续执行 pull |
| pull 失败（backup 后） | 报错，本地 backup commit 已存在可手动恢复 |
| rmtree 失败（push 中） | `GitOperationError` → 中止 push |

---

## 实现顺序

1. **models.py** — 新增 `managed_tools` 字段（无依赖）
2. **git_repo.py** — 新增分支管理方法（依赖 models）
3. **sync_engine.py** — 修复 push 清空逻辑（依赖 models）
4. **cli.py** — 增强 init/pull + 新增 manage 命令（依赖以上所有）
5. **tests** — 每步完成后立即补测试

---

## 不在范围内

- pull 删除本地多余文件
- 软链接方案
- 工具配置文件的字段级合并
- 自动定时同步
- 新增工具 adapter（如 cursor、windsurf）
- backup 分支的自动清理/轮转
