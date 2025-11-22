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
from fastmcp.server.context import Context  # type: ignore

# Use pathspec for GitWildMatch pattern matching (already a project dependency)
try:
    from pathspec import PathSpec  # type: ignore
    from pathspec.patterns import GitWildMatchPattern  # type: ignore
    HAS_PATHSPEC = True
except ImportError:
    PathSpec = None  # type: ignore
    GitWildMatchPattern = None  # type: ignore
    HAS_PATHSPEC = False

from ..utils.path_security import (
    validate_path_in_workspace,
    get_workspace_root_async,
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

async def glob(
    context: Context,
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

    # Get workspace root dynamically based on current session
    workspace_root = await get_workspace_root_async(context)

    # Determine search directory
    if path:
        # Normalize path separators for cross-platform compatibility
        # This handles cases where LLM generates mixed separators (e.g., C:\path/to/dir)
        # Keep original path for LLM-friendly error messages (forward slashes)
        original_path_for_display = path_to_llm_format(path.strip())
        path = normalize_path_separators(path.strip())

        # Validate provided path against dynamic workspace
        search_path = validate_path_in_workspace(path, workspace_root)
        if search_path is None:
            return error_response(f"Path is outside workspace: {original_path_for_display}")

        search_dir = Path(search_path)
        if not search_dir.exists():
            return error_response(f"Directory does not exist: {original_path_for_display}")
        if not search_dir.is_dir():
            return error_response(f"Path is not a directory: {original_path_for_display}")
    else:
        # Default to dynamic workspace root
        search_dir = workspace_root

    try:
        # Normalize pattern: if it's an absolute path, convert to relative
        # This handles cases where LLM generates absolute paths like "C:/workspace/src/*.py"
        normalized_pattern = pattern
        if Path(pattern.split('*')[0].rstrip('/')).is_absolute():
            # Extract the path portion before wildcards
            try:
                # Try to make pattern relative to search_dir
                pattern_base = pattern.split('*')[0].rstrip('/')
                pattern_base_path = Path(normalize_path_separators(pattern_base))

                # Check if pattern is under search_dir
                try:
                    rel_base = pattern_base_path.relative_to(search_dir)
                    # Reconstruct pattern with relative path
                    # Replace the absolute base with relative base
                    normalized_pattern = pattern.replace(
                        pattern_base,
                        path_to_llm_format(rel_base) if str(rel_base) != '.' else ''
                    )
                    # Clean up leading slashes
                    normalized_pattern = normalized_pattern.lstrip('/')
                except ValueError:
                    # Pattern is outside search_dir, return error
                    return error_response(
                        f"Pattern path is outside search directory. "
                        f"Pattern: {pattern}, Search directory: {path_to_llm_format(search_dir)}"
                    )
            except Exception:
                # If normalization fails, use original pattern
                pass

        # Get git-visible files (respecting .gitignore)
        git_visible_files = _get_git_visible_files(search_dir)

        # If git is available, filter files first before glob matching
        # This is more efficient and ensures we don't hit the limit with gitignored files
        if git_visible_files:
            # Match pattern against git-visible files
            safe_files = []

            # Use pathspec for GitWildMatch pattern matching (handles **, *, etc. correctly)
            if PathSpec is not None and GitWildMatchPattern is not None:
                # Create PathSpec with GitWildMatch pattern (like .gitignore)
                spec = PathSpec.from_lines(GitWildMatchPattern, [normalized_pattern])

                for file_path in git_visible_files:
                    try:
                        # Convert to relative path for matching
                        try:
                            rel_path = file_path.relative_to(search_dir)
                            # Use forward slashes for GitWildMatch consistency
                            rel_path_str = path_to_llm_format(rel_path)
                        except ValueError:
                            # If relative_to fails, skip this file
                            continue

                        # Use pathspec GitWildMatch for correct ** and * handling
                        if spec.match_file(rel_path_str):
                            # Check symlink safety (use dynamic workspace root for consistency)
                            if file_path.is_symlink() and not is_safe_symlink(file_path, workspace_root):
                                continue

                            if not check_parent_symlinks(file_path, workspace_root):
                                continue

                            safe_files.append(file_path)

                            # Apply limit
                            if len(safe_files) >= MAX_FILES_DEFAULT:
                                break
                    except Exception:
                        # Match failed, skip
                        continue
            else:
                # Fallback to Path.match if pathspec is not available
                for file_path in git_visible_files:
                    try:
                        # Convert to relative path for matching consistency
                        try:
                            rel_path = file_path.relative_to(search_dir)
                        except ValueError:
                            continue

                        # Match using relative path
                        if Path(rel_path).match(normalized_pattern):
                            # Check symlink safety (use dynamic workspace root for consistency)
                            if file_path.is_symlink() and not is_safe_symlink(file_path, workspace_root):
                                continue

                            if not check_parent_symlinks(file_path, workspace_root):
                                continue

                            safe_files.append(file_path)

                            # Apply limit
                            if len(safe_files) >= MAX_FILES_DEFAULT:
                                break
                    except Exception:
                        continue
        else:
            # Git is required for glob tool
            # This ensures consistent behavior and proper .gitignore filtering
            return error_response(
                "Git is required for file search. "
                "Please ensure git is installed and the directory is a git repository. "
                "Run 'git init' if this is a new project."
            )
        
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