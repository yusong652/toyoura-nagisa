"""glob tool – fast file pattern matching that works with any codebase size.

Supports glob patterns like "**/*.js" or "src/**/*.ts" and returns matching
file paths sorted by modification time. Use this tool when you need to find
files by name patterns.
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

def _expand_glob_pattern(
    base_dir: Path,
    pattern: str,
    max_files: int = MAX_FILES_DEFAULT
) -> List[Path]:
    """Expand glob pattern and return matching files.
    
    Args:
        base_dir: Base directory to search from
        pattern: Glob pattern to match
        max_files: Maximum number of files to return
        
    Returns:
        List of matching file paths
    """
    matched_files = []
    
    try:
        # Handle absolute patterns
        if pattern.startswith('/'):
            pattern = pattern.lstrip('/')
        
        # Use pathlib's glob for pattern matching
        if '**' in pattern:
            # Recursive glob
            matches = base_dir.rglob(pattern.replace('**/', ''))
        else:
            # Non-recursive glob
            matches = base_dir.glob(pattern)
        
        # Filter to files only and apply limit
        for match in matches:
            if len(matched_files) >= max_files:
                break
            
            if match.is_file():
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
        description="The directory to search in. If not specified, the current working directory will be used. IMPORTANT: Omit this field to use the default directory. DO NOT enter \"undefined\" or \"null\" - simply omit it for the default behavior. Must be a valid directory path if provided.",
    ),
) -> Dict[str, Any]:
    """- Fast file pattern matching tool that works with any codebase size
- Supports glob patterns like "**/*.js" or "src/**/*.ts"
- Returns matching file paths sorted by modification time
- Use this tool when you need to find files by name patterns"""

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
        
        if not matched_files:
            return error_response("No files found")
        
        # Security filtering
        safe_files = []
        
        for file_path in matched_files:
            # Check symlink safety
            if file_path.is_symlink() and not is_safe_symlink(file_path):
                continue
            
            if not check_parent_symlinks(file_path):
                continue
            
            safe_files.append(file_path)
        
        if not safe_files:
            return error_response("No files found")
        
        # Sort by modification time (newest first)
        sorted_files = _sort_by_modification_time(safe_files)
        
        # Build Claude Code style response - simple file path list
        file_paths = [str(file_path) for file_path in sorted_files]
        
        # Build Claude Code aligned response
        total_found = len(file_paths)
        
        # Simple user-facing message
        message = f"Found {total_found} matching files"
        
        # Simple LLM content - just the file paths, one per line
        llm_content = "\n".join(file_paths)
        
        return success_response(
            message,
            llm_content,
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
    common = dict(
        tags={"coding", "filesystem", "search", "pattern"}, 
        annotations={"category": "coding", "tags": ["coding", "filesystem", "search", "pattern"]}
    )
    mcp.tool(**common)(glob)