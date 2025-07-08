"""list_directory tool (split from coding.fs_tools)."""

from pathlib import Path
from typing import List, Dict, Any, Optional
from pydantic import Field
from pydantic.fields import FieldInfo
from fastmcp import FastMCP  # type: ignore
from datetime import datetime, timezone

from ..utils.file_filter import FileFilter
from ..utils.tool_result import ToolResult
from ..utils.path_security import WORKSPACE_ROOT, validate_path_in_workspace, is_safe_symlink

# Optional dependency for .gitignore parsing
try:
    from pathspec import PathSpec  # type: ignore
except ModuleNotFoundError:  # pragma: no cover – optional feature
    PathSpec = None  # type: ignore

__all__ = ["list_directory", "register_list_directory_tool"]

# Constants for pagination defaults
DEFAULT_MAX_ITEMS = 1000  # Default limit to prevent OOM
MAX_ITEMS_LIMIT = 5000    # Hard limit for safety


def list_directory(
    path: str = Field("", description="Directory path to list contents from (workspace-relative)"),
    show_hidden: bool = Field(False, description="Whether to include hidden .* files"),
    respect_git_ignore: bool = Field(
        True, description="Whether to respect .gitignore patterns when listing files"
    ),
    ignore: Optional[List[str]] = Field(
        None, description="Glob ignore patterns (e.g. '*.pyc')"
    ),
    offset: Optional[int] = Field(
        None,
        ge=0,
        description="Item offset (0-based) for pagination. Allows chunked reads to avoid OOM with large directories."
    ),
    limit: Optional[int] = Field(
        None,
        gt=0,
        description="Maximum number of items to return. Defaults to 1000, max 5000 for safety."
    ),
) -> Dict[str, Any]:
    """Lists the contents of a directory, returning a list of files and subdirectories.

    ## Core Functionality
    - Provides a detailed listing of items within a specified `path`.
    - By default, it respects `.gitignore` and hides hidden files (e.g., `.env`).
    - Use `show_hidden=True` to include hidden files.
    - Use `ignore` to provide custom glob patterns for exclusion (e.g., `*.tmp`).

    ## Strategic Usage
    - This is your primary tool for exploring the file system and understanding the structure of a project.
    - Use this tool *before* reading or writing files to confirm their location and names.
    - For very large directories, the output will be paginated. Use the `offset` and `limit` parameters to view more items. The tool's output will tell you the total number of items.

    ## Return Value (What you will receive)
    The output you get back from this tool will be one of the following two things:

    1.  **Success:** A `JSON array` (list) of objects, where each object represents a file or directory.
        - **Object Schema:** `{"name": string, "type": "file"|"directory", "size": int, "modified_time": "ISO_8601_string"}`
        - **Example:**
          ```json
          [
            {"name": "src", "type": "directory", "size": 4096, "modified_time": "2025-07-08T10:30:00Z"},
            {"name": "README.md", "type": "file", "size": 1536, "modified_time": "2025-07-08T10:35:00Z"}
          ]
          ```
    2.  **Error:** A single `string` starting with "Error:", explaining what went wrong.
        - Example: `"Error: Path is not a directory: README.md"`

    You MUST parse the JSON array to inspect the directory contents.
    """

    # ------------------------------------------------------------------
    # Parameter validation (manual to stay lightweight)
    # ------------------------------------------------------------------
    
    # Handle Pydantic FieldInfo objects when invoked programmatically
    if isinstance(path, FieldInfo):
        path = ""
    if isinstance(show_hidden, FieldInfo):
        show_hidden = False
    if isinstance(respect_git_ignore, FieldInfo):
        respect_git_ignore = True
    if isinstance(ignore, FieldInfo):
        ignore = None
    if isinstance(offset, FieldInfo):
        offset = None
    if isinstance(limit, FieldInfo):
        limit = None

    # Helper shortcuts for consistent results
    def _error(message: str) -> Dict[str, Any]:
        return ToolResult(status="error", message=message, error=message).model_dump()

    def _success(message: str, llm_content: Any | None, **data: Any) -> Dict[str, Any]:
        payload = data or None
        return ToolResult(
            status="success",
            message=message,
            llm_content=llm_content,
            data=payload,
        ).model_dump()

    # Validate numeric parameters
    if offset is not None and offset < 0:
        return _error(f"offset must be non-negative, got {offset}")
    if limit is not None and limit <= 0:
        return _error(f"limit must be positive, got {limit}")
    if limit is not None and limit > MAX_ITEMS_LIMIT:
        return _error(f"limit exceeds maximum allowed ({MAX_ITEMS_LIMIT}), got {limit}")

    # Set defaults
    actual_offset = offset or 0
    actual_limit = limit or DEFAULT_MAX_ITEMS
    actual_limit = min(actual_limit, MAX_ITEMS_LIMIT)

    # Validate path security
    abs_path = validate_path_in_workspace(path)
    if abs_path is None:
        return _error(f"Path is outside of workspace: {path}")

    try:
        p = Path(abs_path)
        
        # Check path existence and type
        if not p.exists():
            return _error(f"Path does not exist: {path}")
        if not p.is_dir():
            return _error(f"Path is not a directory: {path}")

        # Additional symlink safety check for the target directory itself
        if not is_safe_symlink(p):
            return _error("Target directory is an unsafe symlink pointing outside workspace")

        # ------------------------------------------------------------------
        # Build reusable file filter
        # ------------------------------------------------------------------
        file_filter = FileFilter(
            workspace_root=WORKSPACE_ROOT,
            show_hidden=show_hidden,
            ignore_patterns=ignore,
            respect_git_ignore=respect_git_ignore,
        )

        # ------------------------------------------------------------------
        # Collect all valid items (with safety checks)
        # ------------------------------------------------------------------
        all_items: List[Dict[str, Any]] = []
        unsafe_symlinks_count = 0

        for child in p.iterdir():
            # Filter by file filter first
            if not file_filter.include(child):
                continue

            # Symlink safety check
            if child.is_symlink() and not is_safe_symlink(child):
                unsafe_symlinks_count += 1
                continue

            try:
                # Get file stats safely
                stat = child.stat()
                all_items.append({
                    "name": child.name,
                    "type": "directory" if child.is_dir() else "file",
                    "size": stat.st_size if child.is_file() else 0,
                    "modified_time": datetime.fromtimestamp(
                        stat.st_mtime, tz=timezone.utc
                    ).isoformat().replace('+00:00', 'Z'),
                })
            except (OSError, PermissionError):
                # Skip items we can't access
                continue

        # ------------------------------------------------------------------
        # Sort: directories first, then alphabetical (case-insensitive)
        # ------------------------------------------------------------------
        all_items.sort(key=lambda x: (x["type"] != "directory", x["name"].lower()))

        # ------------------------------------------------------------------
        # Apply pagination
        # ------------------------------------------------------------------
        total_items = len(all_items)
        start_idx = min(actual_offset, total_items)
        end_idx = min(start_idx + actual_limit, total_items)
        
        paginated_items = all_items[start_idx:end_idx]
        is_truncated = end_idx < total_items

        # ------------------------------------------------------------------
        # Prepare response data
        # ------------------------------------------------------------------
        payload: Dict[str, Any] = {
            "items": paginated_items,
            "total_items": total_items,
        }

        if is_truncated or actual_offset > 0:
            payload["showing_range"] = [start_idx + 1, end_idx]  # 1-based range
            payload["truncated"] = is_truncated

        if file_filter.gitignored:
            payload["git_ignored"] = file_filter.gitignored

        if unsafe_symlinks_count > 0:
            payload["unsafe_symlinks"] = unsafe_symlinks_count

        # Check for optional warnings
        extra: Dict[str, Any] = {}
        if respect_git_ignore and "PathSpec" in globals() and PathSpec is None:
            extra["warning"] = "pathspec library not installed – gitignore filtering skipped"

        # Build message
        if is_truncated or actual_offset > 0:
            message = f"Listed {len(paginated_items)} item(s) (showing {start_idx + 1}-{end_idx} of {total_items} total)"
        else:
            message = f"Listed {len(paginated_items)} item(s)"

        if unsafe_symlinks_count > 0:
            message += f" - excluded {unsafe_symlinks_count} unsafe symlink(s)"

        return _success(
            message,
            llm_content=paginated_items,
            **payload,
            **extra,
        )

    except PermissionError:
        return _error("Permission denied when accessing directory")
    except OSError as exc:
        return _error(f"IO error: {exc}")
    except Exception as exc:  # pylint: disable=broad-except
        return _error(f"Unexpected error: {exc}")


# -----------------------------------------------------------------------------
# Registration helper
# -----------------------------------------------------------------------------

def register_list_directory_tool(mcp: FastMCP):
    """Register the list_directory tool with proper tags synchronization."""
    common = dict(
        tags={"coding", "filesystem", "list", "directory", "exploration"}, 
        annotations={"category": "coding", "tags": ["coding", "filesystem", "list", "directory", "exploration"]}
    )
    mcp.tool(**common)(list_directory) 