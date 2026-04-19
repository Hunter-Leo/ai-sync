# Start and Resume Guide — 002-dual-mode-config

## Quick Start
1. Read `init.md` — requirement scope
2. Read `plan.md` — technical approach
3. Read `tasks.md` — find the next `not-started` task
4. Review the standards sections below before writing any code

## Resuming After Interruption
1. Open `tasks.md` and find the first task not in `done`
2. If a task is `in-progress`, read its Notes for context before continuing
3. If a task is `blocked`, read the Notes and address the blocker first
4. Review the standards sections below before continuing

## Key Documents
- Requirement: `.dev/002-dual-mode-config/init.md`
- Plan: `.dev/002-dual-mode-config/generated/plan.md`
- Tasks: `.dev/002-dual-mode-config/generated/tasks.md`

---

## Constitution

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

---

## OOP & SOLID Principles (applicable rules)

- **SRP** — 每个类/模块只有一个职责；`RemoteConfig` 和 `LocalConfig` 各自只描述一种配置模式
- **OCP** — 新增配置模式只需新增模型类，不修改 `SyncEngine` / `GitRepo` 等业务逻辑
- **DIP** — `SyncEngine` 依赖 `GitRepo` 抽象，不感知 config 类型；config 类型判断集中在 CLI 组合根
- 避免在业务层使用 `if/elif` 链处理不同 config 类型——类型判断只在 `_build_engine()` 这一个组合根中出现

---

## Coding Standards (applicable rules)

### Python

- 类型注解：所有函数参数和返回值必须标注
- Docstring：Google Style，每个文件/类/公共函数必须有
- 错误处理：显式 raise，不 pass/swallow
- 无硬编码 secret 或环境特定值
- 使用 `ruff check` 检查 linting

### Testing

- 测试文件：`tests/test_*.py`
- 覆盖率：核心逻辑 ≥ 80%
- Fixture：使用 `tmp_path`，不依赖真实文件系统
- 每个测试文件覆盖：正常路径 + 边界情况 + 错误/异常情况

---

## Git Workflow

Branch: `feat/002-dual-mode-config`

Commit format:
```
[002] T-XXX <type>: <imperative summary ≤ 72 chars>
```
Types: `feat` · `fix` · `refactor` · `test` · `docs` · `chore`

Examples:
```
[002] T-001 refactor: split AppConfig into RemoteConfig/LocalConfig union
[002] T-002 test: add discriminated union serialization tests
[002] T-009 chore: remove PyGithub dependency and github_client module
```
