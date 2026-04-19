# Start and Resume Guide — 001-ai-sync

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
- Requirement: `.dev/001-ai-sync/init.md`
- Plan: `.dev/001-ai-sync/generated/plan.md`
- Tasks: `.dev/001-ai-sync/generated/tasks.md`
- Research: `.dev/001-ai-sync/generated/research.md`

---

## Constitution

### Language & Naming

- All identifiers (variables, functions, classes, constants) must be in English
- All comments and documentation must be in English
- Python naming: `snake_case` for variables/functions, `PascalCase` for classes, `UPPER_SNAKE_CASE` for constants

### Type System

- Use Pydantic v2 for all data structures
- All function parameters and return values must have type annotations
- Use `StrEnum` or `Literal` for fixed-option values
- No bare `Dict[str, Any]` — use Pydantic models instead

### Documentation Comments

- Every file must have a module-level docstring
- Every public class and function must have a full docstring (Args, Returns, Raises)
- Complex algorithms must include an ASCII diagram or example

### OOP Principles

- **Single Responsibility**: each class does one thing (`GitRepo`, `PathMapper`, `FileCollector` are independent)
- **Open/Closed**: new tool support is added by adding a new class, not modifying existing code (adapter pattern)
- **Dependency Inversion**: high-level modules depend on abstractions, not concrete implementations

### Error Handling

- Handle all errors explicitly — never silently swallow exceptions
- Error messages must be meaningful and actionable (tell the user how to fix it)
- Distinguish recoverable errors (raise domain error) from programming errors (let them propagate)

### Testing

- Write tests for each module before moving to the next
- Coverage: normal cases, edge cases, error/exception cases
- Minimum coverage for core logic: 80%
- Test file naming: `test_*.py`

### Dependency Management

```bash
uv add <package>    # add dependency
uv run <script>     # run script
uv sync             # sync dependencies
```

### Security

- No hardcoded secrets or tokens
- GitHub Token stored only in `~/.config/ai-sync/config.json` (user-local file)

---

## OOP & SOLID Principles

### Open/Closed Principle (most important)

New tool support = new `ToolAdapter` subclass. Never edit `SyncEngine`, `FileCollector`, or `PathMapper` to add a new tool.

```python
# Bad: must edit for every new tool
def collect(tool: str) -> list[CollectedFile]:
    if tool == "claude-code": ...
    elif tool == "gemini": ...

# Good: extend by adding a new class
class ToolAdapter(ABC):
    @abstractmethod
    def get_sync_items(self) -> list[SyncItem]: ...

class ClaudeCodeAdapter(ToolAdapter): ...
class GeminiAdapter(ToolAdapter): ...
```

### Single Responsibility

- `FileCollector` — only collects files and resolves symlinks
- `PathMapper` — only does path placeholder substitution
- `GitRepo` — only wraps git operations
- `SyncEngine` — only orchestrates the push/pull flow
- `ToolAdapter` subclasses — only declare their sync item lists

### Dependency Inversion

`SyncEngine` receives all dependencies via constructor injection. The CLI layer assembles them. This enables testing with mock implementations.

```python
class SyncEngine:
    def __init__(
        self,
        adapters: list[ToolAdapter],   # abstraction, not concrete
        repo: GitRepo,
        mapper: PathMapper,
        collector: FileCollector,
        manifest_mgr: ManifestManager,
    ) -> None: ...
```

### Liskov Substitution

All `ToolAdapter` subclasses must be substitutable without `SyncEngine` knowing the concrete type. Never add `isinstance` checks in `SyncEngine`.

---

## Coding Standards (Python)

### Type Annotations

All function parameters and return values must be annotated. No untyped signatures.

### Pydantic v2 Patterns

```python
# Bad
def process(data: dict) -> dict: ...

# Good
def process(data: SyncItem) -> CollectedFile: ...
```

Prohibited patterns:
- `Dict[str, Any]` with variable keys → use a Pydantic model
- `Tuple[str, str, int]` → use a named Pydantic model
- `List[Dict[str, str]]` → use `list[SomeModel]`

### Docstrings (Google Style)

```python
def abstract_paths(self, content: str) -> str:
    """Replace real filesystem paths with platform-neutral placeholders.

    Args:
        content: Text content of a config file.

    Returns:
        Content with all known real paths replaced by placeholders
        (e.g. /Users/alice/.claude → {{CLAUDE_HOME}}).

    Raises:
        Nothing — unknown paths are left unchanged.
    """
```

### Error Handling

```python
# Bad
try:
    config = json.loads(text)
except Exception:
    pass

# Good
try:
    config = json.loads(text)
except json.JSONDecodeError as e:
    raise AiSyncError(f"Invalid JSON in config file: {e}") from e
```

### Guard Clauses

```python
# Bad
def collect(self, adapter: ToolAdapter) -> list[CollectedFile]:
    results = []
    if adapter is not None:
        for item in adapter.get_sync_items():
            if item.local_path.exists():
                ...
    return results

# Good
def collect(self, adapter: ToolAdapter) -> list[CollectedFile]:
    results = []
    for item in adapter.get_sync_items():
        if item.optional and not item.local_path.exists():
            continue
        ...
    return results
```

---

## Git Workflow

Branch: `feat/001-ai-sync`

Commit format:
```
[001] T-XXX <type>: <imperative summary ≤ 72 chars>
```

Types: `feat` · `fix` · `refactor` · `test` · `docs` · `chore`

Examples:
```
[001] T-001 chore: init project structure and pyproject.toml
[001] T-002 feat: add Pydantic models and exception hierarchy
[001] T-003 test: add unit tests for models
```

Rules:
- Commit after each task reaches `done`
- One logical change per commit — do not batch multiple tasks
- Use imperative mood: "add", "fix", "extract" — not "added", "fixing"

---

## Breaking Changes Policy

Project stage: `pre-launch` + new module → breaking changes to existing structure are **allowed**. Prioritize clean, unambiguous structure over compatibility.

---

## Execution Loop

Repeat for each task in `tasks.md`:

```
1.  Mark task as `in-progress` in tasks.md
2.  Read plan.md for the approach for this task
3.  Read all affected existing source files
4.  Review Constitution, OOP & SOLID, and Coding Standards above
5.  Implement the minimal change needed
6.  Verify code:
      [ ] All parameters and return types annotated
      [ ] Every new file has a module-level docstring
      [ ] Every new class has a class-level docstring
      [ ] Every new public function has a full docstring (Args/Returns/Raises)
      [ ] No hardcoded secrets
      [ ] No linting errors
7.  Run existing tests — must pass (no regressions)
8.  Write unit tests: normal cases + edge cases + error cases
9.  Run new tests — all must pass before continuing
10. Update tasks.md: set status to `done`, write implementation summary
11. Commit: git commit -m "[001] T-XXX <type>: <summary>"
```

---

## Handling Blockers

1. Record in `tasks.md` Notes: what was attempted, what failed, what is needed
2. Set task status to `blocked`
3. Ask the user for guidance before continuing

---

## Requirement Complete

When all tasks reach `done`:
1. Notify the user with a summary
2. Check `.dev/TODO.md` for items sourced from this requirement
3. Suggest creating a PR for branch `feat/001-ai-sync`
