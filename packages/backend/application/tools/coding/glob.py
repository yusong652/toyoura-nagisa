"""glob tool – fast file and directory pattern matching.

Supports glob patterns like "**/*.js", "src/**/*.ts", and brace expansion "**/*.{jpg,png}".
Returns matching file and directory paths sorted by modification time.
"""

import asyncio
import os
import re
from pathlib import Path
from typing import List, Dict, Any, Pattern

from pydantic import Field
from backend.application.tools.registrar import ToolRegistrar
from backend.application.tools.context import ToolContext
# from fastmcp.server.context import Context  # type: ignore

from .utils.path_security import get_workspace_root_async
from .utils.constants import PRUNE_DIR_NAMES
from .utils.fs_scan import load_gitignore_spec
from backend.shared.utils.tool_result import success_response, error_response
from backend.shared.utils.path_normalization import normalize_path_separators, path_to_llm_format

__all__ = ["glob", "register_glob_tool"]

# -----------------------------------------------------------------------------
# Constants
# -----------------------------------------------------------------------------

MAX_FILES_DEFAULT = 100

# -----------------------------------------------------------------------------
# Helper functions
# -----------------------------------------------------------------------------


def _sort_by_modification_time(files: List[Path]) -> List[Path]:
    """Sort files by modification time (newest first)."""
    def get_mtime(path: Path) -> float:
        try:
            return path.stat().st_mtime
        except Exception:
            return 0.0

    return sorted(files, key=get_mtime, reverse=True)


def _glob_to_regex(pattern: str) -> Pattern[str]:
    """Translate a glob pattern into a regex that matches POSIX-style relative paths.

    Supports ``**`` (any depth incl. zero), ``*`` (within one segment),
    and ``?`` (single char within one segment). The pattern is anchored
    (``^...$``) and uses ``/`` as separator.
    """
    out: List[str] = []
    i = 0
    n = len(pattern)
    while i < n:
        c = pattern[i]
        if c == "*":
            if i + 1 < n and pattern[i + 1] == "*":
                # `**` — match any number of characters including `/`
                i += 2
                if i < n and pattern[i] == "/":
                    # `**/` — allow zero or more directory levels
                    out.append("(?:.*/)?")
                    i += 1
                else:
                    out.append(".*")
            else:
                out.append("[^/]*")
                i += 1
        elif c == "?":
            out.append("[^/]")
            i += 1
        elif c in r".+^$(){}|[]\\":
            out.append("\\" + c)
            i += 1
        else:
            out.append(re.escape(c) if not c.isalnum() and c != "/" else c)
            i += 1
    return re.compile("^" + "".join(out) + "$")


def _expand_braces(pattern: str) -> List[str]:
    """Expand brace patterns like {a,b,c} into multiple patterns.

    Examples:
        "*.{jpg,png}" -> ["*.jpg", "*.png"]
        "**/*.{a,b,c}" -> ["**/*.a", "**/*.b", "**/*.c"]
        "no_braces" -> ["no_braces"]
    """
    import re

    # Find brace pattern {a,b,c}
    match = re.search(r'\{([^{}]+)\}', pattern)
    if not match:
        return [pattern]

    # Get alternatives inside braces
    alternatives = match.group(1).split(',')
    prefix = pattern[:match.start()]
    suffix = pattern[match.end():]

    # Expand recursively (for nested braces)
    expanded = []
    for alt in alternatives:
        expanded.extend(_expand_braces(prefix + alt.strip() + suffix))

    return expanded


# -----------------------------------------------------------------------------
# Main implementation
# -----------------------------------------------------------------------------

async def glob(
    context: ToolContext,
    pattern: str = Field(
        ...,
        min_length=1,
        description="Glob pattern to match. Supports **, *, ?, and brace expansion {a,b,c}.",
    ),
    path: str = Field(
        ".",
        min_length=1,
        description="Directory to search. Relative paths resolve from the workspace root.",
    ),
) -> Dict[str, Any]:
    """Fast file and directory pattern matching tool.

- Supports glob patterns like "**/*.js" or "src/**/*.ts"
- Supports brace expansion like "**/*.{jpg,png,gif}"
- Returns matching file and directory paths sorted by modification time
- Use this tool when you need to find files or directories by name patterns"""

    # pattern is pre-validated by Pydantic (min_length=1)

    workspace_root = await get_workspace_root_async(context)

    # Determine search directory (no workspace restriction for read operations)
    if path != ".":
        # Normalize path separators for cross-platform compatibility
        original_path_for_display = path_to_llm_format(path.strip())
        path = normalize_path_separators(path.strip())

        # Resolve path to absolute
        search_dir = Path(path).expanduser()
        if not search_dir.is_absolute():
            # Relative paths are resolved from workspace root
            search_dir = workspace_root / search_dir
        search_dir = search_dir.resolve()

        if not search_dir.exists():
            return error_response(f"Directory does not exist: {original_path_for_display}")
        if not search_dir.is_dir():
            return error_response(f"Path is not a directory: {original_path_for_display}")
    else:
        # Default to workspace root
        search_dir = workspace_root.resolve()

    try:
        # Expand brace patterns {a,b,c}
        expanded_patterns = _expand_braces(pattern)
        regexes = [_glob_to_regex(p) for p in expanded_patterns]
        # Only recurse when the pattern actually spans directories (via `**`).
        # Without `**`, a bare `*.py` must only match at the top level, matching
        # the stdlib `glob.glob(..., recursive=True)` semantics.
        recursive = any("**" in p for p in expanded_patterns)
        gitignore = load_gitignore_spec(search_dir) if recursive else None

        def _scan() -> List[Path]:
            # Walk ourselves so we can prune heavy dirs (node_modules, .git,
            # Library, .Trash, etc.) that otherwise make scans of $HOME or
            # large workspaces take minutes. Runs in a thread so the event
            # loop stays responsive for Codex SSE keepalives either way.
            matches: set[Path] = set()
            root_str = str(search_dir)

            def _match_any(rel: str, basename: str) -> bool:
                for rx in regexes:
                    if rx.match(rel) or rx.match(basename):
                        return True
                return False

            if not recursive:
                # Top-level only scan
                try:
                    with os.scandir(root_str) as it:
                        for entry in it:
                            if _match_any(entry.name, entry.name):
                                matches.add(Path(entry.path))
                                if len(matches) >= MAX_FILES_DEFAULT:
                                    break
                except OSError:
                    pass
                return list(matches)

            for dirpath, dirnames, filenames in os.walk(root_str, followlinks=False):
                rel_dir = os.path.relpath(dirpath, root_str)
                rel_prefix = "" if rel_dir == "." else rel_dir.replace(os.sep, "/") + "/"

                # In-place prune skips traversal into noisy/huge subtrees.
                # Combines a hard-coded blocklist (build caches, OS dirs)
                # with user .gitignore rules so scans of large trees stay
                # bounded and match what `rg`/`fd` would see.
                kept = []
                for d in dirnames:
                    if d in PRUNE_DIR_NAMES:
                        continue
                    if gitignore is not None and gitignore.match_file(rel_prefix + d + "/"):
                        continue
                    kept.append(d)
                dirnames[:] = kept

                # Match directories too (glob returns dirs by default)
                for d in dirnames:
                    rel = rel_prefix + d
                    if _match_any(rel, d):
                        matches.add(Path(dirpath, d))
                        if len(matches) >= MAX_FILES_DEFAULT:
                            return list(matches)

                for f in filenames:
                    rel = rel_prefix + f
                    if gitignore is not None and gitignore.match_file(rel):
                        continue
                    if _match_any(rel, f):
                        matches.add(Path(dirpath, f))
                        if len(matches) >= MAX_FILES_DEFAULT:
                            return list(matches)

            return list(matches)

        safe_files = await asyncio.to_thread(_scan)
        all_matches_count = len(safe_files)
        sorted_files = _sort_by_modification_time(safe_files)[:MAX_FILES_DEFAULT]

        # Build response - use forward slashes for LLM consistency
        file_paths = [path_to_llm_format(file_path) for file_path in sorted_files]

        # Check if results were truncated
        truncated = all_matches_count >= MAX_FILES_DEFAULT

        # User-facing message
        total_found = len(file_paths)
        if truncated:
            message = f"Found {total_found} matching items (showing first {MAX_FILES_DEFAULT}, results truncated)"
        else:
            message = f"Found {total_found} matching items"

        # LLM content - file paths or meaningful "not found" message
        if file_paths:
            llm_content = "\n".join(file_paths)
            if truncated:
                llm_content += f"\n\n(Results limited to {MAX_FILES_DEFAULT} items. Use a more specific pattern or path to narrow the search.)"
        else:
            llm_content = f"No items found matching pattern '{pattern}'"

        return success_response(
            message,
            llm_content={
                "parts": [
                    {"type": "text", "text": llm_content}
                ]
            },
            files=file_paths,
            pattern=pattern,
            total_found=total_found,
            truncated=truncated,
        )

    except Exception as exc:
        return error_response(f"Unexpected error during glob search: {exc}")

# -----------------------------------------------------------------------------
# Registration helper
# -----------------------------------------------------------------------------

def register_glob_tool(registrar: ToolRegistrar):
    """Register the glob tool with proper tags synchronization."""
    registrar.tool(
        tags={"coding", "filesystem", "search", "pattern"},
        annotations={"category": "coding", "tags": ["coding", "filesystem", "search", "pattern"]}
    )(glob)
