"""PathMapper — cross-platform path placeholder abstraction and restoration.

On push, real filesystem paths are replaced with platform-neutral placeholders
so the stored config can be restored on any OS. On pull, placeholders are
expanded back to the real paths of the target machine.

Placeholder table:

    Placeholder        macOS/Linux                    Windows
    ─────────────────────────────────────────────────────────────────────
    {{HOME}}           /Users/<user>                  C:\\Users\\<user>
    {{CLAUDE_HOME}}    ~/.claude                      %APPDATA%\\Claude
    {{GEMINI_HOME}}    ~/.gemini                      %USERPROFILE%\\.gemini
    {{OPENCODE_HOME}}  ~/.config/opencode             %APPDATA%\\opencode
    {{SKILLS_HOME}}    ~/.skills                      %USERPROFILE%\\.skills
    {{AGENTS_HOME}}    ~/.agents                      %USERPROFILE%\\.agents

Substitution order: longer real paths are replaced first to prevent partial
matches. For example, ~/.claude must be replaced before ~ (i.e. {{HOME}})
so that ~/.claude/settings.json becomes {{CLAUDE_HOME}}/settings.json, not
{{HOME}}/.claude/settings.json.
"""



from pathlib import Path

from ai_sync.models import Platform

# Maximum bytes read to determine whether a file is text or binary.
_TEXT_PROBE_BYTES = 8192


class PathMapper:
    """Translates between real filesystem paths and platform-neutral placeholders.

    Args:
        platform: The operating system of the current machine.
        home: The home directory of the current user (injected for testability).
    """

    def __init__(self, platform: Platform, home: Path) -> None:
        """Initialize PathMapper.

        Args:
            platform: The operating system of the current machine.
            home: The home directory of the current user.
        """
        self._platform = platform
        self._home = home
        # Build once; sorted by real-path length descending so longer paths
        # are substituted first (prevents partial replacements).
        self._placeholders: dict[str, str] = self._build_placeholders()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_placeholders(self) -> dict[str, str]:
        """Return the placeholder → real-path mapping for the current platform.

        The mapping is ordered by real-path length (longest first) so callers
        can iterate it safely for string substitution.

        Returns:
            Ordered dict mapping placeholder strings (e.g. "{{HOME}}") to
            their real filesystem paths on the current machine.
        """
        return dict(self._placeholders)

    def abstract_paths(self, content: str) -> str:
        """Replace real filesystem paths in *content* with placeholders.

        Iterates placeholders in longest-real-path-first order to avoid
        partial substitutions. On Windows, both backslash and forward-slash
        variants of each path are replaced.

        Args:
            content: Text content of a config file (JSON, Markdown, .mjs, …).

        Returns:
            Content with all known real paths replaced by their placeholders.
            Unknown paths are left unchanged.
        """
        result = content
        for placeholder, real_path in self._placeholders.items():
            result = result.replace(real_path, placeholder)
            # Also replace forward-slash variant on Windows so that tools
            # that write paths with "/" still get abstracted correctly.
            if self._platform == Platform.WINDOWS:
                fwd = real_path.replace("\\", "/")
                if fwd != real_path:
                    result = result.replace(fwd, placeholder)
        return result

    def restore_paths(self, content: str) -> str:
        """Replace placeholders in *content* with real filesystem paths.

        Args:
            content: Text content read from the remote repository.

        Returns:
            Content with all placeholders replaced by the real paths of the
            current machine.
        """
        result = content
        for placeholder, real_path in self._placeholders.items():
            result = result.replace(placeholder, real_path)
        return result

    def is_text_file(self, path: Path) -> bool:
        """Return True if *path* appears to be a UTF-8 text file.

        Reads up to 8 KB and attempts a UTF-8 decode. Binary files (images,
        compiled extensions, …) will fail the decode and return False.

        Args:
            path: Path to the file to probe.

        Returns:
            True if the file is readable as UTF-8 text, False otherwise.
        """
        try:
            with path.open("rb") as fh:
                chunk = fh.read(_TEXT_PROBE_BYTES)
            chunk.decode("utf-8")
            return True
        except (UnicodeDecodeError, OSError):
            return False

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _build_placeholders(self) -> dict[str, str]:
        """Build the placeholder → real-path mapping for the current platform.

        Returns:
            Dict ordered by real-path length descending (longest first).
        """
        home = str(self._home)

        if self._platform == Platform.WINDOWS:
            appdata = str(self._home / "AppData" / "Roaming")
            mapping = {
                "{{CLAUDE_HOME}}": f"{appdata}\\Claude",
                "{{OPENCODE_HOME}}": f"{appdata}\\opencode",
                "{{GEMINI_HOME}}": f"{home}\\.gemini",
                "{{SKILLS_HOME}}": f"{home}\\.skills",
                "{{AGENTS_HOME}}": f"{home}\\.agents",
                "{{HOME}}": home,
            }
        else:
            # macOS and Linux share the same path structure.
            mapping = {
                "{{CLAUDE_HOME}}": f"{home}/.claude",
                "{{GEMINI_HOME}}": f"{home}/.gemini",
                "{{OPENCODE_HOME}}": f"{home}/.config/opencode",
                "{{SKILLS_HOME}}": f"{home}/.skills",
                "{{AGENTS_HOME}}": f"{home}/.agents",
                "{{HOME}}": home,
            }

        # Sort by real-path length descending so longer paths are replaced first.
        return dict(sorted(mapping.items(), key=lambda kv: len(kv[1]), reverse=True))
