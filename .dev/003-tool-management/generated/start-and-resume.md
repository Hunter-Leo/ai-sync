# Start and Resume Guide — 003-tool-management

## Quick Start
1. Read `init.md` — requirement scope
2. Read `plan.md` — technical approach and flow diagrams
3. Read `tasks.md` — find the next `not-started` task
4. Review the standards sections below before writing any code

## Resuming After Interruption
1. Open `tasks.md` and find the first task not in `done`
2. If a task is `in-progress`, read its Notes for context before continuing
3. If a task is `blocked`, read the Notes and address the blocker first
4. Review the standards sections below before continuing

## Key Documents
- Requirement: `.dev/003-tool-management/init.md`
- Plan: `.dev/003-tool-management/generated/plan.md`
- Tasks: `.dev/003-tool-management/generated/tasks.md`

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

---

## OOP & SOLID Principles (applicable rules)

### Single Responsibility Principle
Each class/function has one reason to change. `_discover_tools`, `_backup_to_branch`, `_handle_conflict` are separate functions — do not merge them.

### Open/Closed Principle
`ADAPTER_MAP` is a dict — adding a new tool adapter requires only adding one entry, not editing existing logic.

### Dependency Inversion Principle
`SyncEngine` receives adapters via constructor injection. `_backup_to_branch` receives `repo` and `engine` as parameters — never instantiate them internally.

### Interface Segregation Principle
`GitRepo` new branch methods are additive — existing callers are unaffected.

---

## Coding Standards (applicable rules)

### Python Type Annotations
All function parameters and return values must be annotated. No untyped signatures.

### Pydantic v2
- Field definition: `Annotated[Type, Field(description=...)] = default`
- Use `model_dump(mode="json")` for serialization

### Error Handling
- `GitOperationError` for git failures
- `AiSyncError` for domain errors surfaced to CLI
- Never silently swallow exceptions — backup push failure is the only allowed warning-and-continue case

### New GitRepo methods — docstring format
```python
def checkout_or_create_branch(self, name: str) -> None:
    """Switch to branch, creating it if it does not exist.

    Args:
        name: Branch name (e.g. "backup/host-darwin").

    Raises:
        RepoNotInitializedError: If the repository has not been cloned.
        GitOperationError: If the git operation fails.
    """
```

---

## Git Workflow

Branch: `feat/003-tool-management`

```bash
git checkout -b feat/003-tool-management
```

Commit format:
```
[003] T-XXX <type>: <imperative summary ≤ 72 chars>
```

Types: `feat` · `fix` · `refactor` · `test` · `docs` · `chore`

Examples:
```
[003] T-001 feat: add managed_tools field to RemoteConfig and LocalConfig
[003] T-002 test: add managed_tools serialization and backward-compat tests
[003] T-003 feat: add branch management methods to GitRepo
[003] T-005 fix: clear tool dir before writing in push for full mirror
```
