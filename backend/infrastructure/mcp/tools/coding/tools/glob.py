"""glob tool – find files matching patterns."""

from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime

from pydantic import Field
from pydantic.fields import FieldInfo
from fastmcp import FastMCP  # type: ignore

from ..utils.path_security import (
    validate_path_in_workspace, 
    WORKSPACE_ROOT, 
    is_safe_symlink,
    check_parent_symlinks
)
from backend.infrastructure.mcp.utils.tool_result import ToolResult

__all__ = ["glob", "register_glob_tool"]

# -----------------------------------------------------------------------------
# Constants
# -----------------------------------------------------------------------------

MAX_FILES_DEFAULT = 1000
MAX_FILES_HARD_LIMIT = 10000

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
        description="The directory to search in. If not specified, the current working directory will be used. IMPORTANT: Omit this field to use the default directory.",
    ),
) -> Dict[str, Any]:
    """Fast file pattern matching tool that works with any codebase size"""

    # Handle Pydantic FieldInfo objects when invoked programmatically
    if isinstance(path, FieldInfo):
        path = None

    # Helper shortcuts for consistent results
    def _error(message: str) -> Dict[str, Any]:
        return ToolResult(status="error", message=message, error=message).model_dump()

    def _success(message: str, llm_content: Any, **data: Any) -> Dict[str, Any]:
        return ToolResult(
            status="success",
            message=message,
            llm_content=llm_content,
            data=data,
        ).model_dump()

    # Validate pattern
    if not pattern or not pattern.strip():
        return _error("Pattern is required and cannot be empty")

    # Determine search directory
    if path:
        # Validate provided path
        search_path = validate_path_in_workspace(path)
        if search_path is None:
            return _error(f"Path is outside workspace: {path}")
        
        search_dir = Path(search_path)
        if not search_dir.exists():
            return _error(f"Directory does not exist: {path}")
        if not search_dir.is_dir():
            return _error(f"Path is not a directory: {path}")
    else:
        # Default to workspace root
        search_dir = WORKSPACE_ROOT

    try:
        # Find matching files
        matched_files = _expand_glob_pattern(search_dir, pattern, MAX_FILES_DEFAULT)
        
        if not matched_files:
            return _error(f"No files found matching pattern: {pattern}")
        
        # Security filtering
        safe_files = []
        skipped_count = 0
        
        for file_path in matched_files:
            # Check symlink safety
            if file_path.is_symlink() and not is_safe_symlink(file_path):
                skipped_count += 1
                continue
            
            if not check_parent_symlinks(file_path):
                skipped_count += 1
                continue
            
            safe_files.append(file_path)
        
        if not safe_files:
            return _error(f"No accessible files found matching pattern: {pattern}")
        
        # Sort by modification time (newest first)
        sorted_files = _sort_by_modification_time(safe_files)
        
        # Build file information
        file_list = []
        for file_path in sorted_files:
            try:
                stat = file_path.stat()
                rel_path = file_path.relative_to(WORKSPACE_ROOT)
                
                file_info = {
                    "path": str(rel_path),
                    "size": stat.st_size,
                    "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                }
                file_list.append(file_info)
            except Exception:
                # Skip files we can't stat
                continue
        
        # Build response
        total_found = len(file_list)
        search_path_str = str(search_dir.relative_to(WORKSPACE_ROOT)) if search_dir != WORKSPACE_ROOT else "."
        
        # User-facing message
        message = f"Found {total_found} file{'s' if total_found != 1 else ''} matching '{pattern}'"
        if skipped_count > 0:
            message += f" ({skipped_count} skipped)"
        
        # Structured LLM content
        llm_content = {
            "operation": {
                "type": "glob",
                "pattern": pattern,
                "search_path": search_path_str,
            },
            "result": {
                "files": file_list,
                "total_found": total_found,
                "truncated": len(matched_files) >= MAX_FILES_DEFAULT,
            }
        }
        
        if skipped_count > 0:
            llm_content["skipped"] = skipped_count
        
        return _success(
            message,
            llm_content,
            files=file_list,
            pattern=pattern,
            search_path=search_path_str,
            total_found=total_found,
            skipped=skipped_count,
        )

    except Exception as exc:
        return _error(f"Unexpected error during glob search: {exc}")

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