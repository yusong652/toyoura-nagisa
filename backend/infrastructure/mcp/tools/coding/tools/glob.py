"""glob tool – fast file and directory pattern matching that works with any codebase size.

Supports glob patterns like "**/*.js" or "src/**/*.ts" and returns matching
file and directory paths sorted by modification time. Use this tool when you need to find
files or directories by name patterns.
"""

import subprocess
from pathlib import Path
from typing import List, Dict, Any, Optional, Set

from pydantic import Field
from pydantic.fields import FieldInfo
from fastmcp import FastMCP  # type: ignore

from ..utils.path_security import (
    validate_path_in_workspace,
    WORKSPACE_ROOT,
    is_safe_symlink,
    check_parent_symlinks
)
from backend.infrastructure.mcp.utils.tool_result import success_response, error_response
from backend.infrastructure.mcp.utils.path_normalization import normalize_path_separators, path_to_llm_format

__all__ = ["glob", "register_glob_tool"]

# -----------------------------------------------------------------------------
# Constants
# -----------------------------------------------------------------------------

MAX_FILES_DEFAULT = 100

# -----------------------------------------------------------------------------
# Helper functions
# -----------------------------------------------------------------------------

def _expand_brace_pattern(pattern: str) -> List[str]:
    """Expand brace patterns like {jpg,png,gif} into multiple patterns.
    
    Args:
        pattern: Pattern potentially containing brace expansion
        
    Returns:
        List of expanded patterns
    """
    import re
    
    # Find brace patterns like {jpg,png,gif}
    brace_match = re.search(r'\{([^}]+)\}', pattern)
    if not brace_match:
        return [pattern]
    
    # Extract the options and create multiple patterns
    options = brace_match.group(1).split(',')
    prefix = pattern[:brace_match.start()]
    suffix = pattern[brace_match.end():]
    
    expanded = []
    for option in options:
        expanded.append(prefix + option.strip() + suffix)
    
    return expanded

def _expand_glob_pattern(
    base_dir: Path,
    pattern: str,
    max_files: int = MAX_FILES_DEFAULT
) -> List[Path]:
    """Expand glob pattern and return matching files.
    
    Args:
        base_dir: Base directory to search from
        pattern: Glob pattern to match (supports brace expansion)
        max_files: Maximum number of files to return
        
    Returns:
        List of matching file paths
    """
    matched_files = []
    
    try:
        # Handle absolute patterns
        if pattern.startswith('/'):
            pattern = pattern.lstrip('/')
        
        # Expand brace patterns
        patterns = _expand_brace_pattern(pattern)
        
        for pat in patterns:
            # Use pathlib's glob for pattern matching
            # pathlib.glob() natively supports ** for recursive matching
            matches = base_dir.glob(pat)
            
            # Filter to files and directories and apply limit
            for match in matches:
                if len(matched_files) >= max_files:
                    break

                if (match.is_file() or match.is_dir()) and match not in matched_files:
                    matched_files.append(match)
                    
    except Exception:
        # Invalid pattern or other error
        pass
    
    return matched_files

def _get_git_visible_files(search_dir: Path) -> Set[Path]:
    """Get set of files visible to git (not in .gitignore).

    Args:
        search_dir: Directory to get files from

    Returns:
        Set of absolute paths to files that are not gitignored
    """
    try:
        # Get tracked files
        tracked_result = subprocess.run(
            ["git", "ls-files"],
            cwd=search_dir,
            capture_output=True,
            text=True,
            timeout=5
        )

        # Get untracked files (respecting .gitignore)
        untracked_result = subprocess.run(
            ["git", "ls-files", "--others", "--exclude-standard"],
            cwd=search_dir,
            capture_output=True,
            text=True,
            timeout=5
        )

        visible_files = set()

        # Process tracked files
        if tracked_result.returncode == 0:
            for line in tracked_result.stdout.strip().split('\n'):
                if line:
                    visible_files.add((search_dir / line).resolve())

        # Process untracked files
        if untracked_result.returncode == 0:
            for line in untracked_result.stdout.strip().split('\n'):
                if line:
                    visible_files.add((search_dir / line).resolve())

        return visible_files
    except Exception:
        # If git fails, return empty set (will fall back to pathlib glob)
        return set()

def _sort_by_modification_time(files: List[Path]) -> List[Path]:
    """Sort files by modification time (newest first).

    Args:
        files: List of file paths to sort

    Returns:
        Sorted list with newest files first
    """
    def get_mtime(path: Path) -> float:
        try:
            return path.stat().st_mtime
        except Exception:
            return 0.0

    return sorted(files, key=get_mtime, reverse=True)

# -----------------------------------------------------------------------------
# Main implementation
# -----------------------------------------------------------------------------

def glob(
    pattern: str = Field(
        ...,
        description="The glob pattern to match files against",
    ),
    path: Optional[str] = Field(
        None,
        description="The directory to search in (defaults to workspace root if not specified)",
    ),
) -> Dict[str, Any]:
    """- Fast file and directory pattern matching tool that works with any codebase size
- Supports glob patterns like "**/*.js" or "src/**/*.ts"
- Returns matching file and directory paths sorted by modification time
- Use this tool when you need to find files or directories by name patterns"""

    # Handle Pydantic FieldInfo objects when invoked programmatically
    if isinstance(path, FieldInfo):
        path = None

    # Validate pattern
    if not pattern or not pattern.strip():
        return error_response("Pattern is required and cannot be empty")

    # Determine search directory
    if path:
        # Normalize path separators for cross-platform compatibility
        # This handles cases where LLM generates mixed separators (e.g., C:\path/to/dir)
        path = normalize_path_separators(path.strip())

        # Validate provided path
        search_path = validate_path_in_workspace(path)
        if search_path is None:
            return error_response(f"Path is outside workspace: {path}")
        
        search_dir = Path(search_path)
        if not search_dir.exists():
            return error_response(f"Directory does not exist: {path}")
        if not search_dir.is_dir():
            return error_response(f"Path is not a directory: {path}")
    else:
        # Default to workspace root
        search_dir = WORKSPACE_ROOT

    try:
        # Get git-visible files (respecting .gitignore)
        git_visible_files = _get_git_visible_files(search_dir)

        # If git is available, filter files first before glob matching
        # This is more efficient and ensures we don't hit the limit with gitignored files
        if git_visible_files:
            # Match pattern against git-visible files
            safe_files = []

            for file_path in git_visible_files:
                # Check if file matches the pattern using pathlib's match
                try:
                    # Use pathlib's match for glob patterns (supports **)
                    if file_path.match(pattern):
                        # Check symlink safety
                        if file_path.is_symlink() and not is_safe_symlink(file_path):
                            continue

                        if not check_parent_symlinks(file_path):
                            continue

                        safe_files.append(file_path)

                        # Apply limit
                        if len(safe_files) >= MAX_FILES_DEFAULT:
                            break
                except Exception:
                    # Match failed, skip
                    continue
        else:
            # Fallback to original pathlib glob if git is not available
            matched_files = _expand_glob_pattern(search_dir, pattern, MAX_FILES_DEFAULT)

            safe_files = []
            for file_path in matched_files:
                # Check symlink safety
                if file_path.is_symlink() and not is_safe_symlink(file_path):
                    continue

                if not check_parent_symlinks(file_path):
                    continue

                safe_files.append(file_path)
        
        # Sort by modification time (newest first)
        sorted_files = _sort_by_modification_time(safe_files)

        # Build Claude Code style response - simple file/directory path list
        # Use forward slashes for LLM consistency (cross-platform)
        file_paths = [path_to_llm_format(file_path) for file_path in sorted_files]

        # Build Claude Code aligned response
        total_found = len(file_paths)

        # Check if results were truncated
        truncated = len(safe_files) >= MAX_FILES_DEFAULT

        # Simple user-facing message - use generic "items" to include both files and directories
        if truncated:
            message = f"Found {total_found} matching items (showing first {MAX_FILES_DEFAULT}, results truncated)"
        else:
            message = f"Found {total_found} matching items"

        # Simple LLM content - just the paths, one per line
        # Provide meaningful message when no results found
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

def register_glob_tool(mcp: FastMCP):
    """Register the glob tool with proper tags synchronization."""
    mcp.tool(
        tags={"coding", "filesystem", "search", "pattern"},
        annotations={"category": "coding", "tags": ["coding", "filesystem", "search", "pattern"]}
    )(glob)