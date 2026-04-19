# Inspect & Fix Tasks

**来源：** Gemini Code Review（2026-04-17）  
**状态：** 待处理

---

## 问题清单

| ID | 严重度 | 文件 | 行号 | 摘要 | 状态 |
|---|---|---|---|---|---|
| F-001 | 🔴 高危 | `sync_engine.py` | 153-154 | pull 时路径遍历漏洞 | pending |
| F-002 | 🟡 中危 | `cli.py` | 63 | Token 输入明文显示 | pending |
| F-003 | 🟡 中危 | `config_store.py` | 79-82 | config.json 权限未限制 | pending |
| F-004 | 🟢 低危 | `file_collector.py` | 147 | 路径拼接依赖结尾斜杠 | pending |
| F-005 | 🟢 低危 | `path_mapper.py` | 111-129 | 二进制文件检测不严谨 | pending |
| F-006 | 🟢 低危 | `path_mapper.py` | 75-93 | 路径替换可能误匹配非路径字符串 | pending |

---

## 详细分析与解决方案

---

### F-001 — pull 时路径遍历漏洞 🔴 高危

**位置：** `src/ai_sync/sync_engine.py:153-154`

**问题代码：**
```python
rest = Path(*parts[1:]) if len(parts) > 1 else Path()
local_path = adapter.get_base_dir() / rest   # ← 无边界校验
```

**问题描述：**  
如果远端仓库（被恶意篡改或被攻击者控制）包含路径如 `claude-code/../../.ssh/authorized_keys`，`rest` 会解析为 `../../.ssh/authorized_keys`，`local_path` 最终指向 `~/.ssh/authorized_keys`，pull 时会覆盖该文件。

**验证：**  
Python 的 `Path / Path` 不阻止 `..` 越界，`Path("/home/user/.claude") / Path("../../.ssh/id_rsa")` 结果为 `/home/user/.ssh/id_rsa`。

**解决方案：**  
在写入前用 `Path.resolve()` 校验 `local_path` 是否仍在 `base_dir` 范围内：

```python
base_dir = adapter.get_base_dir().resolve()
local_path = (adapter.get_base_dir() / rest).resolve()

if not local_path.is_relative_to(base_dir):
    _console.print(
        f"[red]Security:[/red] path traversal blocked: {rel.as_posix()}"
    )
    continue
```

同时需要在 `models.py` 新增 `SecurityError(AiSyncError)` 异常类，或直接跳过并警告（推荐跳过，避免中断整个 pull）。

**需要同步修复：**  
`sync_engine.py:104` 的 push 路径 `dest = self._repo_dir / cf.repo_path` 同样需要校验 `dest` 不超出 `repo_dir`，防止恶意 Adapter 写出仓库外。

---

### F-002 — Token 输入明文显示 🟡 中危

**位置：** `src/ai_sync/cli.py:63`

**问题代码：**
```python
token = typer.prompt("GitHub personal access token (repo scope)")
```

**问题描述：**  
用户输入 Token 时终端明文回显，存在肩窥风险（shoulder surfing）。在共享屏幕、录屏、终端历史等场景下 Token 可能泄露。

**解决方案：**  
添加 `hide_input=True`：

```python
token = typer.prompt(
    "GitHub personal access token (repo scope)",
    hide_input=True,
)
```

**影响范围：** 仅 `cli.py` 一行，无副作用。

---

### F-003 — config.json 文件权限未限制 🟡 中危

**位置：** `src/ai_sync/config_store.py:79-82`

**问题代码：**
```python
self._path.parent.mkdir(parents=True, exist_ok=True)
self._path.write_text(
    json.dumps(config.model_dump(), indent=2, ensure_ascii=False),
    encoding="utf-8",
)
```

**问题描述：**  
`write_text` 使用系统默认 umask（通常 `0644`），导致 `config.json`（含 GitHub Token）对同机器其他用户可读。在多用户服务器环境下风险较高。

**解决方案：**  
写入后立即设置 `0600` 权限：

```python
import os

self._path.parent.mkdir(parents=True, exist_ok=True)
self._path.write_text(
    json.dumps(config.model_dump(), indent=2, ensure_ascii=False),
    encoding="utf-8",
)
os.chmod(self._path, 0o600)
```

**注意：** Windows 上 `os.chmod` 只支持 `0o444`（只读）和 `0o666`（读写），`0o600` 在 Windows 上无效但不会报错，可接受。

---

### F-004 — 路径拼接依赖结尾斜杠 🟢 低危

**位置：** `src/ai_sync/file_collector.py:147`

**问题代码：**
```python
repo_path = f"{tool_prefix}/{repo_dir}{rel.as_posix()}"
```

**问题描述：**  
若 `repo_dir = "hooks"`（无结尾斜杠），`rel = "pre.mjs"`，结果为 `claude-code/hookspre.mjs`（错误）。  
当前所有 Adapter 均使用结尾斜杠（如 `"hooks/"`），所以目前不触发，但属于隐患。

**验证：**  
检查所有 Adapter 的 `SyncItem.repo_path`：
- `ClaudeCodeAdapter`：`"hooks/"`, `"skills/"` ✓（有斜杠）
- `GeminiAdapter`：`"commands/"`, `"skills/"` ✓
- `OpenCodeAdapter`：`"agents/"`, `"commands/"` ✓
- `SharedSkillsAdapter`：`"skills/"`, `"agents/skills/"` ✓

**解决方案：**  
使用 `Path` 拼接替代字符串拼接，消除对斜杠的依赖：

```python
repo_path = (Path(tool_prefix) / repo_dir / rel).as_posix()
```

这样无论 `repo_dir` 是否有结尾斜杠，结果都正确。

---

### F-005 — 二进制文件检测不严谨 🟢 低危

**位置：** `src/ai_sync/path_mapper.py:111-129`

**问题代码：**
```python
def is_text_file(self, path: Path) -> bool:
    try:
        with path.open("rb") as fh:
            chunk = fh.read(_TEXT_PROBE_BYTES)  # 8KB
        chunk.decode("utf-8")
        return True
    except (UnicodeDecodeError, OSError):
        return False
```

**问题描述：**  
部分二进制文件（如带有长文本元数据的 PNG、带注释的 PDF 前段）的前 8KB 可能恰好是合法 UTF-8，导致被误判为文本文件，执行路径替换后损坏文件内容。

**解决方案：**  
在 UTF-8 解码检查前，先检查是否包含 null 字节（`\x00`）。几乎所有真正的二进制文件都包含 null 字节，而合法文本文件不会：

```python
def is_text_file(self, path: Path) -> bool:
    try:
        with path.open("rb") as fh:
            chunk = fh.read(_TEXT_PROBE_BYTES)
        if b"\x00" in chunk:   # null 字节 → 二进制
            return False
        chunk.decode("utf-8")
        return True
    except (UnicodeDecodeError, OSError):
        return False
```

**效果：** 覆盖绝大多数二进制格式（PNG、JPEG、ELF、.mjs 编译产物等），误判率极低。

---

### F-006 — 路径替换可能误匹配非路径字符串 🟢 低危

**位置：** `src/ai_sync/path_mapper.py:75-93`

**问题代码：**
```python
result = result.replace(real_path, placeholder)
```

**问题描述：**  
`str.replace` 是全局子串替换，不区分上下文。例如用户名为 `alice`，home 为 `/home/alice`，若配置文件中有字符串 `"author": "alice@example.com"`，不会被误替换（因为完整路径 `/home/alice` 不是子串）。但若配置中有 `"path": "/home/alice/project"`，会被正确替换为 `"path": "{{HOME}}/project"`，这是预期行为。

**实际风险评估：**  
Gemini 提到的"用户名包含在路径中"场景，实际上只有当配置文件中出现完整的 `/home/<user>` 路径时才会触发替换，这正是我们期望的行为。误替换的真实场景极为罕见（需要配置值恰好包含完整 home 路径作为非路径用途）。

**结论：** 当前实现对于 AI 工具配置文件（JSON、Markdown、.mjs）是合理的。**暂不修改**，标记为已知限制，在文档中说明。

---

## 修复优先级

| 优先级 | ID | 原因 |
|---|---|---|
| P0（发布前必须） | F-001 | 高危安全漏洞，可写入任意文件 |
| P0（发布前必须） | F-002 | Token 泄露风险，一行修复 |
| P0（发布前必须） | F-003 | Token 权限暴露，两行修复 |
| P1（发布前建议） | F-004 | 代码健壮性，防止未来 Adapter 引入 bug |
| P1（发布前建议） | F-005 | 防止二进制文件损坏 |
| P2（已知限制） | F-006 | 风险极低，暂不修改，文档说明 |
