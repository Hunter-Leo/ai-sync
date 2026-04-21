# [004] Task Planning

## Status Table

| ID    | Task Name                                      | Status      | Notes |
|-------|------------------------------------------------|-------------|-------|
| T-001 | Fix `_collect_dir` symlink-to-dir guard        | done        | One-line guard added; 14 tests pass. |
| T-002 | Unit tests for T-001                           | done        | Added `test_symlink_to_dir_inside_dir_skipped_silently`. |
| T-003 | Add token guidance in `_init_remote`           | done        | Guidance shown before token prompt; 38 tests pass. |
| T-004 | Unit tests for T-003                           | done        | Added TestTokenGuidance with 2 cases. |
| T-005 | Add 403 hint in `push` error handler           | done        | 403 check + hint added; 40 cli tests pass. |
| T-006 | Unit tests for T-005                           | done        | Added test_push_403_shows_hint + test_push_non_403_error_no_hint. |
| T-007 | Sync remote URL when token changes             | in-progress |       |
| T-008 | Unit tests for T-007                           | not-started |       |

---

## Task Detail Blocks

#### T-001 — Fix `_collect_dir` symlink-to-dir guard

**Goal:** 修复 `FileCollector._collect_dir`，使符号链接解析后仍为目录的条目被静默跳过，不再触发 EISDIR 警告。

**Requirements:**
- 在 `resolved_entry = self._resolve_path(entry)` 之后，将条件 `if resolved_entry is None:` 改为 `if resolved_entry is None or not resolved_entry.is_file():`
- 不改变普通文件和符号链接指向文件的现有行为

**Acceptance Criteria:**
- `ai-sync push` 对含符号链接子目录的路径不再打印 `could not read ... Is a directory` 警告
- 现有测试全部通过（无回归）

**References:** `plan.md § Implementation Path step 1`, `src/ai_sync/file_collector.py:134`

**Implementation Summary:** *(done 后填写)*

---

#### T-002 — Unit tests for T-001

**Goal:** 验证 `_collect_dir` 正确跳过符号链接指向目录的条目。

**Requirements:**
- 新增测试：在临时目录中创建一个符号链接指向子目录，调用 `collect()`，断言返回结果中不含该符号链接对应的条目
- 确认无异常抛出、无警告打印

**Acceptance Criteria:**
- 新增测试通过
- `uv run pytest tests/test_file_collector.py` 全部通过

**References:** `plan.md § Implementation Path step 1`, `tests/test_file_collector.py`

**Implementation Summary:** *(done 后填写)*

---

#### T-003 — Add token guidance in `_init_remote`

**Goal:** 在 `_init_remote` 中，用户确认需要 token 后、输入 token 前，展示详细的 GitHub token 配置指引。

**Requirements:**
- 在 `if needs_token:` 块内、`typer.prompt("Access token", ...)` 之前插入提示文本
- 提示内容包括：
  - 推荐 Fine-grained PAT（更安全）或 Classic PAT（更简单）
  - Fine-grained PAT 所需权限：`Contents: Read and Write`
  - Classic PAT 所需 scope：`repo`
  - Fine-grained 创建链接：`https://github.com/settings/personal-access-tokens/new`
  - Classic 创建链接：`https://github.com/settings/tokens/new`
- 使用 `_console.print()` 保持 rich 风格一致

**Acceptance Criteria:**
- 运行 `ai-sync init` 选择 remote 模式并确认需要 token 时，终端显示上述指引
- 不需要 token 时（`needs_token = False`）不显示指引

**References:** `plan.md § Implementation Path step 2`, `src/ai_sync/cli.py:100`

**Implementation Summary:** *(done 后填写)*

---

#### T-004 — Unit tests for T-003

**Goal:** 验证 token 指引在正确时机显示。

**Requirements:**
- 新增测试：mock `typer.confirm` 返回 `True`（需要 token），断言 `_console.print` 被调用且输出包含 `Fine-grained` 和 `Contents: Read and Write`
- 新增测试：mock `typer.confirm` 返回 `False`（不需要 token），断言指引文本未被打印

**Acceptance Criteria:**
- 新增测试通过
- `uv run pytest tests/test_cli.py` 全部通过

**References:** `plan.md § Implementation Path step 2`, `tests/test_cli.py`

**Implementation Summary:** *(done 后填写)*

---

#### T-005 — Add 403 hint in `push` error handler

**Goal:** `push` 命令遇到 403 错误时，在错误信息后附加 token 重配提示。

**Requirements:**
- 在 `push` 命令的 `except AiSyncError as exc:` 块中，检测 `"403"` 是否出现在 `str(exc)` 中
- 若是，额外打印：`Hint: your token may lack write access. Run 'ai-sync init' to update it.`
- 非 403 错误保持原有行为不变

**Acceptance Criteria:**
- 模拟 403 错误时，终端显示 hint 提示
- 非 403 错误时，不显示 hint

**References:** `plan.md § Implementation Path step 3`, `src/ai_sync/cli.py:159`

**Implementation Summary:** *(done 后填写)*

---

#### T-006 — Unit tests for T-005

**Goal:** 验证 403 hint 在正确条件下显示。

**Requirements:**
- 新增测试：`engine.push()` 抛出含 `"403"` 的 `GitOperationError`，断言 stderr 输出包含 `'ai-sync init'`
- 新增测试：`engine.push()` 抛出不含 `"403"` 的错误，断言 stderr 输出不包含 hint

**Acceptance Criteria:**
- 新增测试通过
- `uv run pytest tests/test_cli.py` 全部通过

**References:** `plan.md § Implementation Path step 3`, `tests/test_cli.py`

**Implementation Summary:** *(done 后填写)*
