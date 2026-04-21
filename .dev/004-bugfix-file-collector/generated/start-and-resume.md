# Start and Resume Guide — 004-bugfix-file-collector-and-token-guidance

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
- Requirement: `.dev/004-bugfix-file-collector/init.md`
- Plan: `.dev/004-bugfix-file-collector/generated/plan.md`
- Tasks: `.dev/004-bugfix-file-collector/generated/tasks.md`

---

## Constitution

- 类型注解：所有函数参数和返回值必须有类型注解
- 文档注释：Google Style，每个公共函数必须有 docstring
- 测试：`test_*.py`，覆盖正常、边界、异常场景
- 工具：`uv run pytest` 运行测试，`ruff check` 检查 lint
- 修改原则：最小化改动，不引入新抽象

---

## OOP & SOLID Principles (applicable rules)

- **SRP**: each function/method has one responsibility
- **OCP**: extend by adding code, not modifying existing logic; avoid `if/elif` chains for new cases
- **Encapsulation**: keep internal state private; expose only what callers need
- Prefer guard clauses (early return) over nested conditionals

---

## Coding Standards (applicable rules)

### Python
- All function parameters and return values must have type annotations
- Every public function must have a Google-style docstring (Args / Returns / Raises)
- DRY: do not duplicate logic
- Single responsibility: each function does one thing
- Use early returns / guard clauses to avoid deep nesting
- Never hardcode secrets or environment-specific values
- Test file naming: `test_*.py`
- Every test file must cover: normal cases, edge cases, error/exception cases

---

## Git Workflow

Branch: `fix/004-bugfix-file-collector`

Commit format:
```
[004] T-XXX fix: <imperative summary ≤ 72 chars>
```

Types: `feat` · `fix` · `refactor` · `test` · `docs` · `chore`

One commit per task after it reaches `done`.
