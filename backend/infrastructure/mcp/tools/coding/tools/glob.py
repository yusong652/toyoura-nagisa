"""glob tool – fast file and directory pattern matching that works with any codebase size.

Supports glob patterns like "**/*.js" or "src/**/*.ts" and returns matching
file and directory paths sorted by modification time. Use this tool when you need to find
files or directories by name patterns.
"""

from pathlib import Path
from typing import List, Dict, Any, Optional

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

__all__ = ["glob", "register_glob_tool"]

# -----------------------------------------------------------------------------
# Constants
# -----------------------------------------------------------------------------

MAX_FILES_DEFAULT = 1000

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
            if '**' in pat:
                # Recursive glob
                matches = base_dir.rglob(pat.replace('**/', ''))
            else:
                # Non-recursive glob
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
        description="The directory to search in (defaults to current working directory if not specified)",
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
        # Find matching files
        matched_files = _expand_glob_pattern(search_dir, pattern, MAX_FILES_DEFAULT)
        
        # Security filtering (even if no files matched)
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
        file_paths = [str(file_path) for file_path in sorted_files]

        # Build Claude Code aligned response
        total_found = len(file_paths)

        # Simple user-facing message - use generic "items" to include both files and directories
        message = f"Found {total_found} matching items"

        # Simple LLM content - just the paths, one per line
        # Provide meaningful message when no results found
        if file_paths:
            llm_content = "\n".join(file_paths)
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