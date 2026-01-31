"""glob tool – fast file and directory pattern matching.

Supports glob patterns like "**/*.js", "src/**/*.ts", and brace expansion "**/*.{jpg,png}".
Returns matching file and directory paths sorted by modification time.
"""

import glob as glob_module
from pathlib import Path
from typing import List, Dict, Any, Optional

from pydantic import Field
from backend.application.tools.registrar import ToolRegistrar
from backend.application.tools.context import ToolContext
# from fastmcp.server.context import Context  # type: ignore

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
        description="The glob pattern to match files against. Supports **, *, ?, and brace expansion {a,b,c}",
    ),
    path: Optional[str] = Field(
        None,
        description="The directory to search in. If not specified, defaults to workspace root. IMPORTANT: Omit this field for default behavior. DO NOT pass null or empty string.",
    ),
) -> Dict[str, Any]:
    """Fast file and directory pattern matching tool.

- Supports glob patterns like "**/*.js" or "src/**/*.ts"
- Supports brace expansion like "**/*.{jpg,png,gif}"
- Returns matching file and directory paths sorted by modification time
- Use this tool when you need to find files or directories by name patterns"""

    # pattern is pre-validated by Pydantic (min_length=1)

    # Determine search directory (no workspace restriction for read operations)
    if path:
        # Normalize path separators for cross-platform compatibility
        original_path_for_display = path_to_llm_format(path.strip())
        path = normalize_path_separators(path.strip())

        # Resolve path to absolute
        search_dir = Path(path).expanduser()
        if not search_dir.is_absolute():
            search_dir = Path.cwd() / search_dir
        search_dir = search_dir.resolve()

        if not search_dir.exists():
            return error_response(f"Directory does not exist: {original_path_for_display}")
        if not search_dir.is_dir():
            return error_response(f"Path is not a directory: {original_path_for_display}")
    else:
        # Default to current working directory
        search_dir = Path.cwd()

    try:
        # Expand brace patterns {a,b,c}
        expanded_patterns = _expand_braces(pattern)

        # Collect all matching files
        all_matches: set[Path] = set()

        for expanded_pattern in expanded_patterns:
            # Use Python's glob with recursive support
            # glob.glob returns strings, convert to Path
            matches = glob_module.glob(
                expanded_pattern,
                root_dir=str(search_dir),
                recursive=True
            )

            for match in matches:
                file_path = (search_dir / match).resolve()

                # No workspace restriction for read operations
                # Symlinks are followed normally
                all_matches.add(file_path)

                # Apply limit early to avoid processing too many files
                if len(all_matches) >= MAX_FILES_DEFAULT:
                    break

            if len(all_matches) >= MAX_FILES_DEFAULT:
                break

        # Convert to list and sort by modification time (newest first)
        safe_files = list(all_matches)
        sorted_files = _sort_by_modification_time(safe_files)[:MAX_FILES_DEFAULT]

        # Build response - use forward slashes for LLM consistency
        file_paths = [path_to_llm_format(file_path) for file_path in sorted_files]

        # Check if results were truncated
        truncated = len(all_matches) >= MAX_FILES_DEFAULT

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
