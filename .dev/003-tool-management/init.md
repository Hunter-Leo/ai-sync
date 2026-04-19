# 需求定义 — 003-tool-management

## Project Stage

```
project_stage: pre-launch
```

---

## Spec

### 背景与动机

当前 `ai-sync` 的工具列表（claude-code、gemini、opencode、shared-skills）在代码中硬编码，用户无法选择只同步部分工具。`init` 命令也不感知本地已安装的工具，不处理"仓库已有数据 + 本地也有数据"的冲突场景。此外，`push` 存在一个逻辑 bug：只写入文件、不清理旧文件，导致删除操作永远无法传播到远程仓库。

### 核心问题

1. 用户无法控制哪些工具被纳入同步管理
2. `init` 时不发现本地已安装工具，不处理冲突
3. `push` 不是完整镜像，删除操作无法同步
4. 没有命令供用户事后修改管理的工具列表

### 目标

- `init` 时自动扫描本地工具目录，让用户勾选纳入管理的工具
- `init` 时检测冲突（仓库有数据 + 本地有数据），备份本地后以远程为主
- `config.json` 新增 `managed_tools` 字段，记录用户选择
- 新增 `ai-sync manage` 子命令，支持事后增删工具
- 修复 `push`：先清空工具目录再写入，实现完整镜像语义

---

## Requirements

### 功能需求

#### F-01：managed_tools 数据模型

- `RemoteConfig` 和 `LocalConfig` 均新增字段 `managed_tools: list[str]`，默认 `[]`
- 空列表 = 向后兼容旧 config（沿用全部 4 个 adapter）
- 有效工具 ID：`claude-code`、`gemini`、`opencode`、`shared-skills`

#### F-02：init 工具发现

- `init` 时扫描各工具的本地目录是否存在：
  - `~/.claude/` → `claude-code`
  - `~/.gemini/` → `gemini`
  - `~/.config/opencode/` → `opencode`
  - `~/.skills/` → `shared-skills`
- 列出已发现的工具，让用户逐一确认是否纳入管理
- 未发现的工具不显示（不强制用户处理）

#### F-03：init 冲突处理

- 仓库有文件 AND 本地被选工具目录有数据时：
  - 列出冲突的工具名称
  - 备份本地目录：`<dir>.bak.<YYYYMMDD-HHMMSS>`（如 `~/.gemini.bak.20260419-120000`）
  - 若备份目标已存在，追加随机 4 位后缀
  - 执行 `pull`，以远程为主覆盖本地
- 仓库为空时：跳过冲突检测，提示用户执行 `ai-sync push`

#### F-04：ai-sync manage 命令

```
ai-sync manage list              # 显示当前 managed_tools
ai-sync manage add <tool>        # 添加工具（工具未安装时警告但允许）
ai-sync manage remove <tool>     # 移除工具（不清理 repo，由下次 push 处理）
```

- `add` 传入无效 tool ID 时报错退出
- `remove` 传入不在列表中的 tool ID 时报错退出

#### F-05：push 完整镜像修复

- `push` 前，对每个被管理工具的 repo 子目录执行清空（`shutil.rmtree`）
- 清空后再写入当前本地文件
- `git add -A` 即可正确 stage 删除，实现完整镜像语义

#### F-06：pull 行为不变

- `pull` 只写入 repo 中存在的文件，不删除本地多余文件（保持现有行为）

### 技术需求

- `managed_tools` 字段向后兼容：旧 config 无此字段时反序列化默认为 `[]`
- `manage` 命令修改 `config.json` 后立即持久化
- 备份操作在 `pull` 之前完成，确保数据安全
- 所有新增公共函数、类须有完整 docstring

---

## Action Items

**前置文档**（可选）：
- 跳过 Phase 02 & 03 — 设计已在 brainstorming 中完成，关键文件已在本会话中读取

**必须文档**（按顺序）：
- [ ] `generated/plan.md`             — Phase 04
- [ ] `generated/tasks.md`            — Phase 05
- [ ] `generated/start-and-resume.md` — Phase 06（任务执行前必须存在）

---

## Constitution

### 语言与命名

- 所有标识符、注释、docstring 使用英文
- Python snake_case，类名 PascalCase

### 类型系统

- 使用 Pydantic v2；所有函数参数和返回值须有类型注解
- 字段定义格式：`Annotated[Type, Field(...)] = default`

### 文档注释

- 每个文件须有模块级 docstring
- 每个公共类须有类级 docstring
- 每个公共函数须有完整 docstring（Args、Returns、Raises）

### 代码质量

- 单一职责：每个函数只做一件事
- 依赖注入：高层模块不直接实例化低层依赖
- 避免深层嵌套，使用 guard clause 提前返回

### 测试

- 每个模块的测试覆盖：正常情况、边界情况、异常情况
- 核心逻辑最低覆盖率 80%
- 测试文件命名：`test_*.py`

### 依赖管理

- 使用 `uv add` 添加依赖
- lint：`ruff check`；test：`pytest`
