"""grep tool – powerful content search using pure Python regex."""

import re
from pathlib import Path
from typing import List, Dict, Any, Optional, Set

from pydantic import Field
from backend.application.tools.registrar import ToolRegistrar
from backend.application.tools.context import ToolContext
# from fastmcp.server.context import Context  # type: ignore

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
        description="The regular expression pattern to search for in file contents",
    ),
    path: Optional[str] = Field(
        None,
        description="File or directory to search in (defaults to workspace root if not specified)",
    ),
    glob: Optional[str] = Field(
        None,
        description="Glob pattern to filter files (e.g. \"*.js\", \"*.{ts,tsx}\")",
    ),
    type: Optional[str] = Field(
        None,
        description="File type to search. Common types: js, py, ts, rust, go, java, etc.",
    ),
    output_mode: str = Field(
        "files_with_matches",
        description="Output mode: \"content\" shows matching lines, \"files_with_matches\" shows file paths (default), \"count\" shows match counts.",
    ),
    case_insensitive: bool = Field(
        False,
        description="Case insensitive search",
        alias="-i"
    ),
    show_line_numbers: bool = Field(
        False,
        description="Show line numbers in output. Requires output_mode: \"content\".",
        alias="-n"
    ),
    context_after: Optional[int] = Field(
        None,
        description="Number of lines to show after each match. Requires output_mode: \"content\".",
        alias="-A"
    ),
    context_before: Optional[int] = Field(
        None,
        description="Number of lines to show before each match. Requires output_mode: \"content\".",
        alias="-B"
    ),
    context_both: Optional[int] = Field(
        None,
        description="Number of lines to show before and after each match. Requires output_mode: \"content\".",
        alias="-C"
    ),
    head_limit: Optional[int] = Field(
        None,
        description="Limit output to first N results.",
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

    # Compile regex
    try:
        flags = re.IGNORECASE if case_insensitive else 0
        regex = re.compile(pattern, flags)
    except re.error as e:
        return error_response(f"Invalid regex pattern: {e}")

    # Determine search path (no workspace restriction for read operations)
    if path:
        original_path_for_display = path_to_llm_format(path.strip())
        path = normalize_path_separators(path.strip())

        # Resolve path to absolute
        search_path = Path(path).expanduser()
        if not search_path.is_absolute():
            search_path = Path.cwd() / search_path
        search_path = search_path.resolve()

        if not search_path.exists():
            return error_response(f"Path does not exist: {original_path_for_display}")
    else:
        # Default to current working directory
        search_path = Path.cwd()

    # Process context arguments
    ctx_before = context_both if context_both else (context_before or 0)
    ctx_after = context_both if context_both else (context_after or 0)

    # Expand glob patterns for brace expansion support
    glob_patterns = []
    if glob:
        glob_patterns = _expand_braces(glob)

    try:
        results = []
        files_searched = 0
        max_results = head_limit or MAX_RESULTS_DEFAULT

        # Get all files to search
        if search_path.is_file():
            files_to_search = [search_path]
        else:
            files_to_search = list(search_path.rglob("*"))

        for file_path in files_to_search:
            # Skip directories
            if not file_path.is_file():
                continue

            # No workspace restriction for read operations
            # Symlinks are followed normally

            # Skip binary/large files
            if _should_skip_file(file_path):
                continue

            # Filter by glob pattern
            if not _matches_glob_pattern(file_path, search_path, glob_patterns):
                continue

            # Filter by file type
            if not _matches_file_type(file_path, type):
                continue

            files_searched += 1

            # Search the file
            result = _search_file(
                file_path, regex, output_mode,
                show_line_numbers, ctx_before, ctx_after
            )

            if result:
                results.append(result)
                if len(results) >= max_results:
                    break

        # Build response
        if output_mode == "files_with_matches":
            file_paths = [path_to_llm_format(r["file"]) for r in results]
            total_files = len(file_paths)
            message = f"Found {total_files} file{'s' if total_files != 1 else ''}"

            if file_paths:
                llm_content = "\n".join(file_paths)
            else:
                llm_content = f"No files found matching pattern '{pattern}'"

            return success_response(
                message,
                llm_content={"parts": [{"type": "text", "text": llm_content}]},
                files=file_paths,
                total_files=total_files,
                pattern=pattern,
            )

        elif output_mode == "count":
            output_lines = []
            total_matches = 0
            for r in results:
                file_display = path_to_llm_format(r["file"])
                output_lines.append(f"{file_display}:{r['count']}")
                total_matches += r["count"]

            message = f"Found {total_matches} matches in {len(results)} files"

            if output_lines:
                llm_content = "\n".join(output_lines)
            else:
                llm_content = f"No matches found for pattern '{pattern}'"

            return success_response(
                message,
                llm_content={"parts": [{"type": "text", "text": llm_content}]},
                total_matches=total_matches,
                total_files=len(results),
                pattern=pattern,
            )

        else:  # content mode
            output_lines = []
            for r in results:
                file_display = path_to_llm_format(r["file"])
                for line in r["lines"]:
                    output_lines.append(f"{file_display}:{line}")

            message = f"Search results for pattern '{pattern}'"

            if output_lines:
                llm_content = "\n".join(output_lines)
            else:
                llm_content = f"No matches found for pattern '{pattern}'"

            return success_response(
                message,
                llm_content={"parts": [{"type": "text", "text": llm_content}]},
                content=output_lines,
                total_lines=len(output_lines),
                pattern=pattern,
            )

    except Exception as exc:
        return error_response(f"Unexpected error during search: {exc}")

# -----------------------------------------------------------------------------
# Registration helper
# -----------------------------------------------------------------------------

def register_grep_tool(registrar: ToolRegistrar):
    """Register the grep tool with proper tags synchronization."""
    registrar.tool(
        tags={"coding", "filesystem", "search", "content", "regex", "grep"},
        annotations={"category": "coding", "tags": ["coding", "filesystem", "search", "content", "regex", "grep"]}
    )(grep)
