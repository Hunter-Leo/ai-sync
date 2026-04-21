# [004] Implementation Plan

## Project Structure

仅涉及两个现有文件，无新增文件：

```
src/ai_sync/
├── file_collector.py   ← [CHANGED] _collect_dir 增加 is_file() 守卫
└── cli.py              ← [CHANGED] _init_remote token 提示 + push 403 错误提示

tests/
└── test_file_collector.py  ← [CHANGED] 新增符号链接指向目录的测试用例
```

---

## Technology Decisions

- Python 3.11+，无新增依赖
- 使用标准库 `pathlib.Path.is_file()` 做守卫，零额外开销
- `rich` 已引入，token 提示使用 `_console.print()` 保持风格一致

---

## Implementation Path

1. **修复 `file_collector.py`**（无依赖）
   - `_collect_dir` 中 `resolved_entry = self._resolve_path(entry)` 之后，将 `if resolved_entry is None:` 改为 `if resolved_entry is None or not resolved_entry.is_file():`
   - 新增测试：创建符号链接指向目录，确认 `collect()` 返回结果中不含该条目，且无异常

2. **更新 `cli.py` — token 配置指引**（无依赖）
   - 在 `_init_remote` 的 `needs_token = typer.confirm(...)` 之前，插入 token 配置说明文本
   - 内容：推荐 Fine-grained PAT、所需权限 `Contents: Read and Write`、Classic PAT scope `repo`、两个创建链接

3. **更新 `cli.py` — push 403 错误提示**（无依赖）
   - 在 `push` 命令的 `except AiSyncError` 块中，检测错误信息是否含 `403`，若是则附加提示：`Run 'ai-sync init' to update your token.`

---

## Key Technical Points

- **最小改动原则**：F-001 仅改一行条件判断，不引入新方法或新类
- **静默跳过**：符号链接指向目录属于正常文件系统状态，不应打印警告，直接 `continue` 即可
- **token 提示时机**：在用户确认需要 token（`needs_token = True`）之后、`typer.prompt` 之前展示，避免不需要 token 的用户看到无关信息
- **403 检测**：`GitOperationError` 的 `str(exc)` 包含 git stderr，直接检查 `"403"` 字符串即可，无需解析结构化数据

---

## Out of Scope

- 不自动刷新或验证 token 有效性
- 不修改 `config.json` 的 token 存储方式
- 不处理非 GitHub 托管平台（GitLab、Gitea 等）的 token 说明
- 不修改 `pull` / `init` 命令的 403 处理（仅 `push` 最常见）

---

## Design Compliance Review

- [x] **SRP** — 每处改动职责单一：文件收集守卫、UI 提示、错误提示各自独立
- [x] **OCP** — 通过条件扩展而非修改核心逻辑
- [x] **LSP** — 无继承变更
- [x] **ISP** — 无接口变更
- [x] **DIP** — 无依赖方向变化
- [x] Constitution — 最小改动，无硬编码，无重复逻辑
