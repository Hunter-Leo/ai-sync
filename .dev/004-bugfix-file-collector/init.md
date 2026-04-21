# [004] bugfix-file-collector-and-token-guidance

## # Project Stage

```
project_stage: pre-launch
```

---

## # Spec

### 背景与动机

执行 `ai-sync push` 时出现两个问题：

1. **目录读取警告（代码 bug）**：`FileCollector._collect_dir` 在遍历目录时，对符号链接条目调用 `_resolve_path` 后，未检查解析结果是否仍为目录，直接将目录路径传入 `_collect_file`，导致 `read_bytes()` 抛出 `[Errno 21] Is a directory` 错误并打印警告。

   复现路径：`~/.agents/skills/` 下存在符号链接指向目录（如 `lovstudio-any2pdf`、`spec-coding-skill`），`rglob("*")` 会将这些符号链接作为条目返回，`entry.is_symlink()` 为 True，通过了过滤检查，但解析后的路径是目录而非文件。

2. **推送 403（UX 问题）**：`ai-sync init` 在提示用户输入 token 时，缺乏足够的引导信息，用户不清楚需要哪种 token、需要哪些权限，导致配置错误的 token 后推送失败。

### 核心问题

1. `_collect_dir` 中缺少对 `resolved_entry.is_file()` 的检查，导致符号链接指向目录时仍尝试读取。
2. `ai-sync init` 的 token 输入提示过于简单，未告知用户 token 类型、所需权限及创建步骤。

### 目标

1. 修复 `FileCollector._collect_dir`，在解析路径后增加 `is_file()` 守卫，跳过所有解析后仍为目录的条目。
2. 在 `ai-sync init` 的 token 输入环节，展示详细的 GitHub token 配置指引（token 类型选择、最小权限说明、创建链接）。

---

## # Requirements

### 功能需求

- **F-001**：`_collect_dir` 在调用 `_collect_file` 前，必须确认 `resolved_entry.is_file()` 为 True，否则静默跳过。
- **F-002**：修复后，`ai-sync push` 对含有符号链接子目录的 `~/.agents/skills/` 不再打印 `could not read ... Is a directory` 警告。
- **F-003**：`ai-sync init` 在提示用户输入 token 前，展示详细的 GitHub token 配置指引，内容包括：
  - 推荐使用 **Fine-grained PAT**（更安全）或 **Classic PAT**（更简单）的说明
  - Fine-grained PAT 所需最小权限：`Contents: Read and Write`
  - Classic PAT 所需最小 scope：`repo`
  - GitHub 创建 token 的直达链接：
    - Fine-grained: `https://github.com/settings/personal-access-tokens/new`
    - Classic: `https://github.com/settings/tokens/new`
- **F-004**：推送 403 时，错误信息中附加 token 配置提示，引导用户重新运行 `ai-sync init` 更新 token。

### 技术需求

- F-001/F-002 修改范围：仅 `src/ai_sync/file_collector.py` 的 `_collect_dir` 方法，一行改动。
- F-003 修改范围：`src/ai_sync/cli.py` 的 `_init_remote` 函数，在 `typer.prompt("Access token", ...)` 前插入提示文本。
- F-004 修改范围：`src/ai_sync/cli.py` 的 `push` 命令错误处理，检测 403 并附加提示。
- 不改变现有行为：普通文件、符号链接指向文件的情况保持不变。
- 新增单元测试：覆盖「符号链接指向目录」场景，确认该条目被静默跳过。

---

## # Action Items

**Prerequisite documents**（不需要）：无

**Required documents**（按顺序）：
- [ ] `generated/plan.md`              — Phase 04
- [ ] `generated/tasks.md`             — Phase 05
- [ ] `generated/start-and-resume.md`  — Phase 06（任务执行前必须存在）

---

## # Constitution

### Python

- 类型注解：所有函数参数和返回值必须有类型注解
- 文档注释：Google Style，每个公共函数必须有 docstring
- 测试：`test_*.py`，覆盖正常、边界、异常场景
- 工具：`uv run pytest` 运行测试，`ruff check` 检查 lint
- 修改原则：最小化改动，不引入新抽象
