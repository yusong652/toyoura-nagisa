"""grep tool – powerful content search using pure Python regex."""

import asyncio
import os
import re
from pathlib import Path
from typing import List, Dict, Any, Optional, Set

from pydantic import Field
from backend.application.tools.registrar import ToolRegistrar
from backend.application.tools.context import ToolContext
# from fastmcp.server.context import Context  # type: ignore

from .utils.path_security import get_workspace_root_async
from .utils.constants import PRUNE_DIR_NAMES
from .utils.fs_scan import RG_PATH
from backend.shared.utils.tool_result import success_response, error_response
from backend.shared.utils.path_normalization import normalize_path_separators, path_to_llm_format

__all__ = ["grep", "register_grep_tool"]

# -----------------------------------------------------------------------------
# Constants
# -----------------------------------------------------------------------------

MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024  # 10MB max file size
MAX_RESULTS_DEFAULT = 100

# File extension mappings for type filtering
FILE_TYPE_EXTENSIONS = {
    "js": [".js"],
    "ts": [".ts"],
    "tsx": [".tsx"],
    "py": [".py"],
    "python": [".py"],
    "java": [".java"],
    "cpp": [".cpp", ".cc", ".cxx"],
    "c": [".c", ".h"],
    "rust": [".rs"],
    "go": [".go"],
    "php": [".php"],
    "rb": [".rb"],
    "ruby": [".rb"],
    "cs": [".cs"],
    "csharp": [".cs"],
    "sh": [".sh"],
    "bash": [".sh", ".bash"],
    "json": [".json"],
    "yaml": [".yaml", ".yml"],
    "yml": [".yml", ".yaml"],
    "xml": [".xml"],
    "html": [".html", ".htm"],
    "css": [".css"],
    "scss": [".scss"],
    "less": [".less"],
    "md": [".md"],
    "markdown": [".md"],
    "txt": [".txt"],
}

# Binary file extensions to skip
BINARY_EXTENSIONS = {
    ".png", ".jpg", ".jpeg", ".gif", ".bmp", ".ico", ".webp",
    ".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx",
    ".zip", ".tar", ".gz", ".rar", ".7z",
    ".exe", ".dll", ".so", ".dylib",
    ".pyc", ".pyo", ".class",
    ".mp3", ".mp4", ".avi", ".mov", ".wav",
    ".ttf", ".otf", ".woff", ".woff2",
    ".sqlite", ".db",
}

# -----------------------------------------------------------------------------
# ripgrep fast path
# -----------------------------------------------------------------------------


async def _grep_ripgrep(
    pattern: str,
    search_path: Path,
    output_mode: str,
    case_insensitive: bool,
    show_line_numbers: bool,
    ctx_before: int,
    ctx_after: int,
    glob_patterns: List[str],
    file_type: Optional[str],
    max_results: int,
) -> Optional[List[Dict[str, Any]]]:
    """Run ripgrep via subprocess and parse the output.

    Returns a list of per-file result dicts matching the Python fallback's
    shape (``{file, count[, lines]}``), or ``None`` to signal the caller
    should fall back to the Python walker. Uses rg's ``-0`` so paths can
    contain ``:`` (Windows drive letters) without ambiguity.
    """
    if not RG_PATH:
        return None

    args: List[str] = [
        RG_PATH,
        "--no-messages",      # ignore "permission denied" noise
        "--color=never",
        "--no-heading",       # one `file:...` record per line
        "-0",                 # NUL between path and the rest (drive-letter safe)
    ]
    if case_insensitive:
        args.append("-i")

    if output_mode == "files_with_matches":
        args.append("-l")
    elif output_mode == "count":
        args.append("-c")
    else:  # content
        args.append("-n" if show_line_numbers else "-N")
        if ctx_before:
            args.extend(["-B", str(ctx_before)])
        if ctx_after:
            args.extend(["-A", str(ctx_after)])

    for gp in glob_patterns:
        args.extend(["--glob", gp])
    if file_type:
        args.extend(["--type", file_type])

    args.extend(["-e", pattern, "--", str(search_path)])

    try:
        proc = await asyncio.create_subprocess_exec(
            *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()
    except (OSError, FileNotFoundError):
        # rg disappeared between detection and use; bail to fallback.
        return None

    # rg exit codes: 0 match, 1 no match, 2 error.
    if proc.returncode not in (0, 1):
        # Pattern error or similar — let caller decide to fall back.
        err = stderr.decode("utf-8", errors="replace").strip()
        if "regex parse error" in err or "unrecognized" in err:
            # Probably a Python-regex-only feature (rg uses Rust regex).
            # Fall back so we keep Python regex compatibility.
            return None
        raise RuntimeError(f"ripgrep failed (exit {proc.returncode}): {err[:500]}")

    text = stdout.decode("utf-8", errors="replace")
    if not text:
        return []

    results: List[Dict[str, Any]] = []

    if output_mode == "files_with_matches":
        # Each entry: "<path>\0\n"  (rg emits NUL after path, then newline).
        for rec in text.split("\n"):
            rec = rec.rstrip("\0")
            if rec:
                results.append({"file": Path(rec), "count": 0})
                if len(results) >= max_results:
                    break
        return results

    if output_mode == "count":
        # Each entry: "<path>\0<count>\n"
        for rec in text.splitlines():
            if "\0" not in rec:
                continue
            fp, _, cnt = rec.partition("\0")
            try:
                results.append({"file": Path(fp), "count": int(cnt)})
            except ValueError:
                continue
            if len(results) >= max_results:
                break
        return results

    # Content mode: each record is "<path>\0<line>:<content>" (matches)
    # or "<path>\0<line>-<content>" (context). Without -n it's just
    # "<path>\0<content>". Group by path, preserving encounter order.
    by_file: Dict[str, List[str]] = {}
    order: List[str] = []
    for rec in text.splitlines():
        if rec == "--" or "\0" not in rec:
            continue
        fp, _, rest = rec.partition("\0")
        if fp not in by_file:
            if len(order) >= max_results:
                break
            by_file[fp] = []
            order.append(fp)
        by_file[fp].append(rest)

    for fp in order:
        results.append({
            "file": Path(fp),
            "count": len(by_file[fp]),  # approximate — context lines included
            "lines": by_file[fp],
        })
    return results


# -----------------------------------------------------------------------------
# Helper functions
# -----------------------------------------------------------------------------


def _expand_braces(pattern: str) -> List[str]:
    """Expand brace patterns like {a,b,c} into multiple patterns."""
    match = re.search(r'\{([^{}]+)\}', pattern)
    if not match:
        return [pattern]

    alternatives = match.group(1).split(',')
    prefix = pattern[:match.start()]
    suffix = pattern[match.end():]

    expanded = []
    for alt in alternatives:
        expanded.extend(_expand_braces(prefix + alt.strip() + suffix))

    return expanded


def _should_skip_file(file_path: Path) -> bool:
    """Check if file should be skipped (binary, too large, etc.)."""
    # Skip binary files by extension
    if file_path.suffix.lower() in BINARY_EXTENSIONS:
        return True

    # Skip files that are too large
    try:
        if file_path.stat().st_size > MAX_FILE_SIZE_BYTES:
            return True
    except OSError:
        return True

    return False


def _matches_glob_pattern(file_path: Path, search_dir: Path, glob_patterns: List[str]) -> bool:
    """Check if file matches any of the glob patterns."""
    if not glob_patterns:
        return True

    try:
        rel_path = file_path.relative_to(search_dir)
    except ValueError:
        return False

    for pattern in glob_patterns:
        if rel_path.match(pattern):
            return True

    return False


def _matches_file_type(file_path: Path, file_type: Optional[str]) -> bool:
    """Check if file matches the specified file type."""
    if not file_type:
        return True

    extensions = FILE_TYPE_EXTENSIONS.get(file_type.lower(), [])
    if not extensions:
        return True  # Unknown type, allow all

    return file_path.suffix.lower() in extensions


def _get_context_lines(
    lines: List[str],
    match_indices: Set[int],
    context_before: int,
    context_after: int
) -> List[tuple]:
    """Get lines with context around matches.

    Returns list of (line_number, line_content, is_match) tuples.
    """
    result = []
    shown_indices = set()

    for match_idx in sorted(match_indices):
        start = max(0, match_idx - context_before)
        end = min(len(lines), match_idx + context_after + 1)

        for i in range(start, end):
            if i not in shown_indices:
                shown_indices.add(i)
                is_match = i in match_indices
                result.append((i + 1, lines[i], is_match))  # 1-indexed

    # Sort by line number
    result.sort(key=lambda x: x[0])
    return result


def _search_file(
    file_path: Path,
    regex: re.Pattern,
    output_mode: str,
    show_line_numbers: bool,
    context_before: int,
    context_after: int,
) -> Optional[Dict[str, Any]]:
    """Search a single file for pattern matches.

    Returns:
        Dict with search results or None if no matches/error
    """
    try:
        content = file_path.read_text(encoding='utf-8', errors='ignore')
    except Exception:
        return None

    lines = content.splitlines()

    # Find all matching line indices
    match_indices: Set[int] = set()
    for i, line in enumerate(lines):
        if regex.search(line):
            match_indices.add(i)

    if not match_indices:
        return None

    match_count = len(match_indices)

    if output_mode == "files_with_matches":
        return {"file": file_path, "count": match_count}

    elif output_mode == "count":
        return {"file": file_path, "count": match_count}

    else:  # content mode
        context_lines = _get_context_lines(
            lines, match_indices, context_before, context_after
        )

        formatted_lines = []
        for line_num, line_content, is_match in context_lines:
            if show_line_numbers:
                separator = ":" if is_match else "-"
                formatted_lines.append(f"{line_num}{separator}{line_content}")
            else:
                formatted_lines.append(line_content)

        return {
            "file": file_path,
            "count": match_count,
            "lines": formatted_lines,
        }


# -----------------------------------------------------------------------------
# Main implementation
# -----------------------------------------------------------------------------

async def grep(
    context: ToolContext,
    pattern: str = Field(
        ...,
        description="Regular expression to search for in file contents.",
    ),
    path: str = Field(
        ".",
        min_length=1,
        description="File or directory to search. Relative paths resolve from the workspace root.",
    ),
    glob: Optional[str] = Field(
        None,
        description="Optional glob filter for candidate files, for example \"*.js\" or \"*.{ts,tsx}\".",
    ),
    type: Optional[str] = Field(
        None,
        description="Optional file type filter such as js, py, ts, rust, go, or java.",
    ),
    output_mode: str = Field(
        "files_with_matches",
        description="\"content\" returns matching lines, \"files_with_matches\" returns file paths, \"count\" returns match counts.",
    ),
    case_insensitive: bool = Field(
        False,
        description="Enable case-insensitive matching.",
    ),
    show_line_numbers: bool = Field(
        False,
        description="Show line numbers. Requires output_mode=\"content\".",
    ),
    context_after: Optional[int] = Field(
        None,
        ge=0,
        description="Lines of trailing context after each match. Requires output_mode=\"content\".",
    ),
    context_before: Optional[int] = Field(
        None,
        ge=0,
        description="Lines of leading context before each match. Requires output_mode=\"content\".",
    ),
    context_both: Optional[int] = Field(
        None,
        ge=0,
        description="Lines of context before and after each match. Requires output_mode=\"content\".",
    ),
    head_limit: Optional[int] = Field(
        None,
        description="Maximum number of results to return.",
    ),
) -> Dict[str, Any]:
    """A powerful content search tool using Python regex.

  Usage:
  - Supports Python regex syntax (e.g., "log.*Error", "function\\s+\\w+", "foo|bar")
  - Filter files with glob parameter (e.g., "*.js", "*.{ts,tsx}") or type parameter (e.g., "js", "py")
  - Output modes: "content" shows matching lines, "files_with_matches" shows file paths (default), "count" shows match counts
  - Automatically skips binary files and files larger than 10MB
"""
    # Validate pattern
    if not pattern or not pattern.strip():
        return error_response("Search pattern is required and cannot be empty")

    # Validate output mode
    valid_modes = ["content", "files_with_matches", "count"]
    if output_mode not in valid_modes:
        return error_response(f"Invalid output_mode. Must be one of: {', '.join(valid_modes)}")

    # Validate content-only options
    if output_mode != "content":
        content_only_options = []
        if show_line_numbers:
            content_only_options.append("show_line_numbers")
        if context_after is not None:
            content_only_options.append("context_after")
        if context_before is not None:
            content_only_options.append("context_before")
        if context_both is not None:
            content_only_options.append("context_both")

        if content_only_options:
            return error_response(
                "These options require output_mode='content': "
                + ", ".join(content_only_options)
            )

    # Compile regex
    try:
        flags = re.IGNORECASE if case_insensitive else 0
        regex = re.compile(pattern, flags)
    except re.error as e:
        return error_response(f"Invalid regex pattern: {e}")

    workspace_root = await get_workspace_root_async(context)

    # Determine search path (no workspace restriction for read operations)
    if path != ".":
        original_path_for_display = path_to_llm_format(path.strip())
        path = normalize_path_separators(path.strip())

        # Resolve path to absolute
        search_path = Path(path).expanduser()
        if not search_path.is_absolute():
            search_path = workspace_root / search_path
        search_path = search_path.resolve()

        if not search_path.exists():
            return error_response(f"Path does not exist: {original_path_for_display}")
    else:
        # Default to workspace root
        search_path = workspace_root

    # Process context arguments
    ctx_before = context_both if context_both else (context_before or 0)
    ctx_after = context_both if context_both else (context_after or 0)

    # Expand glob patterns for brace expansion support
    glob_patterns = []
    if glob:
        glob_patterns = _expand_braces(glob)

    max_results = head_limit or MAX_RESULTS_DEFAULT

    # Fast path: delegate to ripgrep if available. Orders of magnitude
    # faster, respects .gitignore/.ignore natively, handles binary detection
    # properly. Falls back to the Python walker on any failure, missing
    # binary, or regex feature rg's Rust engine doesn't support.
    try:
        rg_results = await _grep_ripgrep(
            pattern=pattern,
            search_path=search_path,
            output_mode=output_mode,
            case_insensitive=case_insensitive,
            show_line_numbers=show_line_numbers,
            ctx_before=ctx_before,
            ctx_after=ctx_after,
            glob_patterns=glob_patterns,
            file_type=type,
            max_results=max_results,
        )
    except RuntimeError:
        rg_results = None
    if rg_results is not None:
        results = rg_results
        return _format_grep_response(results, output_mode, pattern)

    def _walk_and_search() -> List[Dict[str, Any]]:
        # Directory walk + per-file regex is heavy (seconds to minutes on
        # large trees). Run in a thread so the event loop keeps pumping
        # — otherwise long searches starve Codex's SSE stream and the
        # whole agent turn stalls.
        collected: List[Dict[str, Any]] = []

        if search_path.is_file():
            file_iter: List[Path] = [search_path]
        else:
            def _iter_files():
                for dirpath, dirnames, filenames in os.walk(search_path, followlinks=False):
                    # Prune heavy/noisy dirs in-place (affects os.walk traversal)
                    dirnames[:] = [d for d in dirnames if d not in PRUNE_DIR_NAMES]
                    for name in filenames:
                        yield Path(dirpath) / name
            file_iter = _iter_files()

        for file_path in file_iter:
            if not file_path.is_file():
                continue
            if _should_skip_file(file_path):
                continue
            if not _matches_glob_pattern(file_path, search_path, glob_patterns):
                continue
            if not _matches_file_type(file_path, type):
                continue

            result = _search_file(
                file_path, regex, output_mode,
                show_line_numbers, ctx_before, ctx_after
            )
            if result:
                collected.append(result)
                if len(collected) >= max_results:
                    break
        return collected

    try:
        results = await asyncio.to_thread(_walk_and_search)
        return _format_grep_response(results, output_mode, pattern)
    except Exception as exc:
        return error_response(f"Unexpected error during search: {exc}")


def _format_grep_response(
    results: List[Dict[str, Any]],
    output_mode: str,
    pattern: str,
) -> Dict[str, Any]:
    """Build the tool response envelope from a list of per-file results."""
    if output_mode == "files_with_matches":
        file_paths = [path_to_llm_format(r["file"]) for r in results]
        total_files = len(file_paths)
        message = f"Found {total_files} file{'s' if total_files != 1 else ''}"
        llm_content = "\n".join(file_paths) if file_paths else f"No files found matching pattern '{pattern}'"
        return success_response(
            message,
            llm_content={"parts": [{"type": "text", "text": llm_content}]},
            files=file_paths,
            total_files=total_files,
            pattern=pattern,
        )

    if output_mode == "count":
        output_lines = []
        total_matches = 0
        for r in results:
            file_display = path_to_llm_format(r["file"])
            output_lines.append(f"{file_display}:{r['count']}")
            total_matches += r["count"]
        message = f"Found {total_matches} matches in {len(results)} files"
        llm_content = "\n".join(output_lines) if output_lines else f"No matches found for pattern '{pattern}'"
        return success_response(
            message,
            llm_content={"parts": [{"type": "text", "text": llm_content}]},
            total_matches=total_matches,
            total_files=len(results),
            pattern=pattern,
        )

    # content mode
    output_lines = []
    for r in results:
        file_display = path_to_llm_format(r["file"])
        for line in r.get("lines", []):
            output_lines.append(f"{file_display}:{line}")
    message = f"Search results for pattern '{pattern}'"
    llm_content = "\n".join(output_lines) if output_lines else f"No matches found for pattern '{pattern}'"
    return success_response(
        message,
        llm_content={"parts": [{"type": "text", "text": llm_content}]},
        content=output_lines,
        total_lines=len(output_lines),
        pattern=pattern,
    )

# -----------------------------------------------------------------------------
# Registration helper
# -----------------------------------------------------------------------------

def register_grep_tool(registrar: ToolRegistrar):
    """Register the grep tool with proper tags synchronization."""
    registrar.tool(
        tags={"coding", "filesystem", "search", "content", "regex", "grep"},
        annotations={"category": "coding", "tags": ["coding", "filesystem", "search", "content", "regex", "grep"]}
    )(grep)
