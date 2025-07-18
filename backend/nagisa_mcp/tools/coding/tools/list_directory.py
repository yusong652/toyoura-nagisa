"""list_directory tool – comprehensive directory content listing with advanced filtering and sorting.

This tool provides atomic directory exploration functionality, focusing exclusively on 
listing and organizing directory contents with rich metadata. It does NOT read file 
contents - use read_file or read_many_files for content retrieval.

Modeled after gemini-cli's directory listing capabilities for consistency and interoperability.
"""

from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple, Union
import os
import stat
import mimetypes
from datetime import datetime, timezone
from enum import Enum

from pydantic import Field
from pydantic.fields import FieldInfo
from fastmcp import FastMCP  # type: ignore

from ..utils.path_security import (
    validate_path_in_workspace, 
    WORKSPACE_ROOT, 
    is_safe_symlink,
    check_parent_symlinks
)
from backend.nagisa_mcp.utils.tool_result import ToolResult
from ..utils.file_filter import FileFilter
from .constants import (
    DEFAULT_EXCLUDE_PATTERNS,
    MAX_FILES_DEFAULT,
    MAX_FILES_HARD_LIMIT,
    TEXT_EXTENSIONS,
    BINARY_EXTENSIONS,
    BINARY_DETECTION_SAMPLE_SIZE,
)

__all__ = ["list_directory", "register_list_directory_tool"]

# -----------------------------------------------------------------------------
# Constants specific to directory listing
# -----------------------------------------------------------------------------

# Performance and safety limits
MAX_DIRECTORY_ITEMS = 10000  # Maximum items per directory scan
MAX_DIRECTORY_DEPTH = 20     # Maximum recursive depth for safety
DEFAULT_PAGE_SIZE = 1000     # Default pagination size
MAX_PAGE_SIZE = 5000        # Maximum pagination size

# File size categories (bytes)
SIZE_CATEGORIES = {
    "tiny": 1024,           # < 1KB
    "small": 1024 * 100,    # < 100KB
    "medium": 1024 * 1024,  # < 1MB
    "large": 1024 * 1024 * 10,  # < 10MB
    "huge": 1024 * 1024 * 100,  # < 100MB
}

# Recency thresholds (hours)
RECENCY_THRESHOLDS = {
    "very_recent": 1,       # Modified within 1 hour
    "recent": 24,           # Modified within 24 hours
    "today": 24,            # Modified today
    "week": 24 * 7,         # Modified within a week
    "month": 24 * 30,       # Modified within a month
}

# -----------------------------------------------------------------------------
# Enums for type safety
# -----------------------------------------------------------------------------

class SortBy(str, Enum):
    """Sorting options for directory listing."""
    NAME = "name"
    SIZE = "size"
    MODIFIED = "modified"
    TYPE = "type"
    EXTENSION = "extension"
    RECENCY = "recency"

class FilterBy(str, Enum):
    """Filtering options for directory listing."""
    ALL = "all"
    FILES = "files"
    DIRECTORIES = "directories"
    TEXT = "text"
    BINARY = "binary"
    EXECUTABLES = "executables"
    HIDDEN = "hidden"
    RECENT = "recent"

# -----------------------------------------------------------------------------
# Data structures
# -----------------------------------------------------------------------------

class DirectoryItem:
    """Represents a single directory item with comprehensive metadata."""
    
    def __init__(self, path: Path, workspace_root: Path):
        self.path = path
        self.workspace_root = workspace_root
        self._stat_info = None
        self._mime_type = None
        self._compute_metadata()
    
    def _compute_metadata(self):
        """Compute all metadata for this directory item."""
        try:
            self._stat_info = self.path.stat()
            if self.path.is_file():
                self._mime_type = mimetypes.guess_type(str(self.path))[0]
        except Exception:
            self._stat_info = None
            self._mime_type = None
    
    @property
    def name(self) -> str:
        """Get item name."""
        return self.path.name
    
    @property
    def relative_path(self) -> str:
        """Get path relative to workspace root."""
        try:
            return str(self.path.relative_to(self.workspace_root))
        except ValueError:
            return str(self.path)
    
    @property
    def absolute_path(self) -> str:
        """Get absolute path."""
        return str(self.path)
    
    @property
    def type(self) -> str:
        """Get item type."""
        if self.path.is_dir():
            return "directory"
        elif self.path.is_file():
            return "file"
        elif self.path.is_symlink():
            return "symlink"
        else:
            return "other"
    
    @property
    def size(self) -> int:
        """Get file size in bytes."""
        if self._stat_info and self.path.is_file():
            return self._stat_info.st_size
        return 0
    
    @property
    def size_category(self) -> str:
        """Get size category."""
        if not self.path.is_file():
            return "directory"
        
        size = self.size
        if size < SIZE_CATEGORIES["tiny"]:
            return "tiny"
        elif size < SIZE_CATEGORIES["small"]:
            return "small"
        elif size < SIZE_CATEGORIES["medium"]:
            return "medium"
        elif size < SIZE_CATEGORIES["large"]:
            return "large"
        elif size < SIZE_CATEGORIES["huge"]:
            return "huge"
        else:
            return "massive"
    
    @property
    def modified_time(self) -> str:
        """Get modification time in ISO format."""
        if self._stat_info:
            return datetime.fromtimestamp(
                self._stat_info.st_mtime, tz=timezone.utc
            ).isoformat().replace('+00:00', 'Z')
        return "unknown"
    
    @property
    def modified_timestamp(self) -> float:
        """Get modification timestamp."""
        if self._stat_info:
            return self._stat_info.st_mtime
        return 0
    
    @property
    def recency_category(self) -> str:
        """Get recency category."""
        if not self._stat_info:
            return "unknown"
        
        current_time = datetime.now().timestamp()
        hours_ago = (current_time - self._stat_info.st_mtime) / 3600
        
        if hours_ago < RECENCY_THRESHOLDS["very_recent"]:
            return "very_recent"
        elif hours_ago < RECENCY_THRESHOLDS["recent"]:
            return "recent"
        elif hours_ago < RECENCY_THRESHOLDS["today"]:
            return "today"
        elif hours_ago < RECENCY_THRESHOLDS["week"]:
            return "week"
        elif hours_ago < RECENCY_THRESHOLDS["month"]:
            return "month"
        else:
            return "old"
    
    @property
    def extension(self) -> str:
        """Get file extension."""
        if self.path.is_file():
            return self.path.suffix.lower()
        return ""
    
    @property
    def mime_type(self) -> Optional[str]:
        """Get MIME type."""
        return self._mime_type
    
    @property
    def is_hidden(self) -> bool:
        """Check if item is hidden."""
        return self.name.startswith('.')
    
    @property
    def is_text(self) -> bool:
        """Check if file is likely text."""
        if not self.path.is_file():
            return False
        
        # Check by extension
        if self.extension in TEXT_EXTENSIONS:
            return True
        if self.extension in BINARY_EXTENSIONS:
            return False
        
        # Check by MIME type
        if self._mime_type:
            return self._mime_type.startswith('text/')
        
        # Binary detection by sampling
        try:
            with self.path.open('rb') as f:
                sample = f.read(BINARY_DETECTION_SAMPLE_SIZE)
                return b'\x00' not in sample
        except Exception:
            return False
    
    @property
    def is_executable(self) -> bool:
        """Check if file is executable."""
        if not self.path.is_file() or not self._stat_info:
            return False
        return bool(self._stat_info.st_mode & stat.S_IXUSR)
    
    @property
    def permissions(self) -> str:
        """Get file permissions in octal format."""
        if self._stat_info:
            return oct(self._stat_info.st_mode)[-3:]
        return "000"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "name": self.name,
            "path": self.relative_path,
            "absolute_path": self.absolute_path,
            "type": self.type,
            "size": self.size,
            "size_category": self.size_category,
            "modified_time": self.modified_time,
            "modified_timestamp": self.modified_timestamp,
            "recency_category": self.recency_category,
            "extension": self.extension,
            "mime_type": self.mime_type,
            "is_hidden": self.is_hidden,
            "is_text": self.is_text,
            "is_executable": self.is_executable,
            "permissions": self.permissions,
        }

class DirectoryListing:
    """Comprehensive directory listing with advanced filtering and sorting."""
    
    def __init__(self, items: List[DirectoryItem]):
        self.items = items
        self.total_items = len(items)
    
    def filter_by(self, filter_type: FilterBy, **kwargs) -> 'DirectoryListing':
        """Filter items by type."""
        filtered_items = []
        
        for item in self.items:
            if filter_type == FilterBy.ALL:
                filtered_items.append(item)
            elif filter_type == FilterBy.FILES and item.type == "file":
                filtered_items.append(item)
            elif filter_type == FilterBy.DIRECTORIES and item.type == "directory":
                filtered_items.append(item)
            elif filter_type == FilterBy.TEXT and item.is_text:
                filtered_items.append(item)
            elif filter_type == FilterBy.BINARY and item.path.is_file() and not item.is_text:
                filtered_items.append(item)
            elif filter_type == FilterBy.EXECUTABLES and item.is_executable:
                filtered_items.append(item)
            elif filter_type == FilterBy.HIDDEN and item.is_hidden:
                filtered_items.append(item)
            elif filter_type == FilterBy.RECENT and item.recency_category in ["very_recent", "recent"]:
                filtered_items.append(item)
        
        return DirectoryListing(filtered_items)
    
    def sort_by(self, sort_type: SortBy, reverse: bool = False) -> 'DirectoryListing':
        """Sort items by specified criteria."""
        if sort_type == SortBy.NAME:
            key_func = lambda item: (item.type != "directory", item.name.lower())
        elif sort_type == SortBy.SIZE:
            key_func = lambda item: (item.type != "file", item.size)
        elif sort_type == SortBy.MODIFIED:
            key_func = lambda item: item.modified_timestamp
        elif sort_type == SortBy.TYPE:
            key_func = lambda item: (item.type, item.name.lower())
        elif sort_type == SortBy.EXTENSION:
            key_func = lambda item: (item.extension, item.name.lower())
        elif sort_type == SortBy.RECENCY:
            recency_order = {
                "very_recent": 0, "recent": 1, "today": 2, 
                "week": 3, "month": 4, "old": 5, "unknown": 6
            }
            key_func = lambda item: (recency_order.get(item.recency_category, 6), -item.modified_timestamp)
        else:
            key_func = lambda item: item.name.lower()
        
        sorted_items = sorted(self.items, key=key_func, reverse=reverse)
        return DirectoryListing(sorted_items)
    
    def paginate(self, offset: int = 0, limit: int = DEFAULT_PAGE_SIZE) -> 'DirectoryListing':
        """Apply pagination to items."""
        start_idx = min(offset, self.total_items)
        end_idx = min(start_idx + limit, self.total_items)
        paginated_items = self.items[start_idx:end_idx]
        return DirectoryListing(paginated_items)
    
    def get_summary(self) -> Dict[str, Any]:
        """Get comprehensive summary statistics."""
        if not self.items:
            return {
                "total_items": 0,
                "by_type": {},
                "by_size_category": {},
                "by_recency": {},
                "by_extension": {},
                "total_size": 0,
                "hidden_count": 0,
                "executable_count": 0,
                "text_files": 0,
                "binary_files": 0,
            }
        
        # Count by type
        by_type = {}
        by_size_category = {}
        by_recency = {}
        by_extension = {}
        total_size = 0
        hidden_count = 0
        executable_count = 0
        text_files = 0
        binary_files = 0
        
        for item in self.items:
            # Type counts
            by_type[item.type] = by_type.get(item.type, 0) + 1
            
            # Size category counts
            by_size_category[item.size_category] = by_size_category.get(item.size_category, 0) + 1
            
            # Recency counts
            by_recency[item.recency_category] = by_recency.get(item.recency_category, 0) + 1
            
            # Extension counts (for files only)
            if item.type == "file" and item.extension:
                by_extension[item.extension] = by_extension.get(item.extension, 0) + 1
            
            # Aggregate stats
            total_size += item.size
            if item.is_hidden:
                hidden_count += 1
            if item.is_executable:
                executable_count += 1
            if item.type == "file":
                if item.is_text:
                    text_files += 1
                else:
                    binary_files += 1
        
        return {
            "total_items": self.total_items,
            "by_type": by_type,
            "by_size_category": by_size_category,
            "by_recency": by_recency,
            "by_extension": dict(sorted(by_extension.items(), key=lambda x: x[1], reverse=True)[:10]),  # Top 10 extensions
            "total_size": total_size,
            "hidden_count": hidden_count,
            "executable_count": executable_count,
            "text_files": text_files,
            "binary_files": binary_files,
        }

# -----------------------------------------------------------------------------
# Helper utilities
# -----------------------------------------------------------------------------

def _scan_directory_safely(
    directory: Path,
    max_items: int = MAX_DIRECTORY_ITEMS,
    show_hidden: bool = False,
    file_filter: Optional[FileFilter] = None
) -> Tuple[List[DirectoryItem], Dict[str, int]]:
    """Safely scan directory with comprehensive error handling."""
    items = []
    skip_counts = {
        "permission_denied": 0,
        "unsafe_symlinks": 0,
        "filter_excluded": 0,
        "hidden_files": 0,
        "scan_errors": 0,
    }
    
    try:
        for child in directory.iterdir():
            if len(items) >= max_items:
                break
            
            try:
                # Security checks
                if child.is_symlink() and not is_safe_symlink(child):
                    skip_counts["unsafe_symlinks"] += 1
                    continue
                
                if not check_parent_symlinks(child):
                    skip_counts["unsafe_symlinks"] += 1
                    continue
                
                # Hidden file handling
                if not show_hidden and child.name.startswith('.'):
                    skip_counts["hidden_files"] += 1
                    continue
                
                # File filter
                if file_filter and not file_filter.include(child):
                    skip_counts["filter_excluded"] += 1
                    continue
                
                # Create directory item
                item = DirectoryItem(child, WORKSPACE_ROOT)
                items.append(item)
                
            except PermissionError:
                skip_counts["permission_denied"] += 1
                continue
            except Exception:
                skip_counts["scan_errors"] += 1
                continue
                
    except PermissionError:
        skip_counts["permission_denied"] += 1
    except Exception:
        skip_counts["scan_errors"] += 1
    
    return items, skip_counts

# -----------------------------------------------------------------------------
# Main implementation
# -----------------------------------------------------------------------------

def list_directory(
    path: str = Field(
        "",
        description="Directory path to list contents from (workspace-relative). Use '.' for current directory, or specify subdirectory like 'src' or 'docs'.",
    ),
    show_hidden: bool = Field(
        False,
        description="Whether to include hidden files and directories (starting with '.').",
    ),
    filter_by: FilterBy = Field(
        FilterBy.ALL,
        description="Filter items by type: 'all', 'files', 'directories', 'text', 'binary', 'executables', 'hidden', 'recent'.",
    ),
    sort_by: SortBy = Field(
        SortBy.NAME,
        description="Sort items by: 'name', 'size', 'modified', 'type', 'extension', 'recency'.",
    ),
    sort_reverse: bool = Field(
        False,
        description="Whether to reverse the sort order (e.g., largest first, newest first).",
    ),
    respect_git_ignore: bool = Field(
        True,
        description="Whether to respect .gitignore patterns when listing files.",
    ),
    ignore_patterns: Optional[List[str]] = Field(
        None,
        description="Additional glob patterns to ignore (e.g., ['*.tmp', '*.log', 'build/**']).",
    ),
    include_metadata: bool = Field(
        True,
        description="Whether to include rich metadata (size, modified time, permissions, etc.) in the response.",
    ),
    max_items: int = Field(
        DEFAULT_PAGE_SIZE,
        ge=1,
        le=MAX_PAGE_SIZE,
        description="Maximum number of items to return (pagination limit).",
    ),
    offset: int = Field(
        0,
        ge=0,
        description="Starting position for pagination (0-based index).",
    ),
) -> Dict[str, Any]:
    """List directory contents with detailed metadata, filtering, sorting, and pagination.
    
    Returns file/directory information with rich metadata - does NOT read file contents.
    Use for project structure exploration and file discovery workflows.
    """

    # ------------------------------------------------------------------
    # Parameter validation and normalization
    # ------------------------------------------------------------------

    # Handle Pydantic FieldInfo objects when invoked programmatically
    if isinstance(path, FieldInfo):
        path = ""
    if isinstance(show_hidden, FieldInfo):
        show_hidden = False
    if isinstance(filter_by, FieldInfo):
        filter_by = FilterBy.ALL
    if isinstance(sort_by, FieldInfo):
        sort_by = SortBy.NAME
    if isinstance(sort_reverse, FieldInfo):
        sort_reverse = False
    if isinstance(respect_git_ignore, FieldInfo):
        respect_git_ignore = True
    if isinstance(ignore_patterns, FieldInfo):
        ignore_patterns = None
    if isinstance(include_metadata, FieldInfo):
        include_metadata = True
    if isinstance(max_items, FieldInfo):
        max_items = DEFAULT_PAGE_SIZE
    if isinstance(offset, FieldInfo):
        offset = 0

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

    # Validate parameters
    if offset < 0:
        return _error(f"offset must be non-negative, got {offset}")
    if max_items <= 0 or max_items > MAX_PAGE_SIZE:
        return _error(f"max_items must be between 1 and {MAX_PAGE_SIZE}, got {max_items}")

    # Validate workspace access
    if not validate_path_in_workspace("."):
        return _error("Cannot access workspace directory")

    # Validate and resolve target directory
    abs_path = validate_path_in_workspace(path)
    if abs_path is None:
        return _error(f"Path is outside workspace: {path}")

    try:
        target_dir = Path(abs_path)
        
        # Check path existence and type
        if not target_dir.exists():
            return _error(f"Directory does not exist: {path}")
        if not target_dir.is_dir():
            return _error(f"Path is not a directory: {path}")

        # Additional symlink safety check
        if target_dir.is_symlink() and not is_safe_symlink(target_dir):
            return _error("Target directory is an unsafe symlink pointing outside workspace")

        # ------------------------------------------------------------------
        # Set up file filtering
        # ------------------------------------------------------------------
        
        file_filter = FileFilter(
            workspace_root=WORKSPACE_ROOT,
            show_hidden=show_hidden,
            ignore_patterns=ignore_patterns,
            respect_git_ignore=respect_git_ignore,
        )

        # ------------------------------------------------------------------
        # Scan directory safely
        # ------------------------------------------------------------------
        
        items, skip_counts = _scan_directory_safely(
            target_dir,
            max_items=max_items * 2,  # Allow buffer for filtering
            show_hidden=show_hidden,
            file_filter=file_filter,
        )

        if not items:
            return _error(f"No accessible items found in directory: {path}")

        # ------------------------------------------------------------------
        # Apply filtering and sorting
        # ------------------------------------------------------------------

        listing = DirectoryListing(items)
        
        # Apply filtering
        if filter_by != FilterBy.ALL:
            listing = listing.filter_by(filter_by)
        
        # Apply sorting
        listing = listing.sort_by(sort_by, reverse=sort_reverse)
        
        # Apply pagination
        paginated_listing = listing.paginate(offset=offset, limit=max_items)
        
        # ------------------------------------------------------------------
        # Build comprehensive response
        # ------------------------------------------------------------------

        # Convert items to dictionaries
        if include_metadata:
            items_data = [item.to_dict() for item in paginated_listing.items]
        else:
            # Lightweight response with minimal metadata
            items_data = [
                {
                    "name": item.name,
                    "path": item.relative_path,
                    "type": item.type,
                }
                for item in paginated_listing.items
            ]

        # Get comprehensive summary
        summary = listing.get_summary()
        
        # Add skip counts to summary
        if any(skip_counts.values()):
            summary["skipped_items"] = skip_counts
            summary["total_skipped"] = sum(skip_counts.values())

        # Pagination info
        total_after_filter = listing.total_items
        showing_count = len(paginated_listing.items)
        
        pagination = {
            "offset": offset,
            "limit": max_items,
            "total_available": total_after_filter,
            "showing_range": [offset + 1, offset + showing_count] if showing_count > 0 else [0, 0],
            "has_more": offset + showing_count < total_after_filter,
        }

        # Listing info for transparency
        listing_info = {
            "directory_path": str(target_dir.relative_to(WORKSPACE_ROOT)) if target_dir != WORKSPACE_ROOT else ".",
            "filter_by": filter_by.value,
            "sort_by": sort_by.value,
            "sort_reverse": sort_reverse,
            "show_hidden": show_hidden,
            "respect_git_ignore": respect_git_ignore,
            "include_metadata": include_metadata,
        }

        # Build user-facing message
        if showing_count == 0:
            message = f"No items found in directory '{path}' after filtering"
        else:
            message = f"Listed {showing_count} item(s)"
            if total_after_filter != showing_count:
                message += f" (showing {offset + 1}-{offset + showing_count} of {total_after_filter})"
            if any(skip_counts.values()):
                total_skipped = sum(skip_counts.values())
                message += f" - {total_skipped} items skipped"

        # Build structured LLM content following unified standard
        
        llm_content = {
            "operation": {
                "type": "list_directory",
                "path": str(target_dir.relative_to(WORKSPACE_ROOT)) if target_dir != WORKSPACE_ROOT else ".",
                "filter_by": filter_by.value,
                "sort_by": sort_by.value
            },
            "result": {
                "items": items_data,
                "showing_count": showing_count,
                "total_available": total_after_filter,
                "has_more": pagination["has_more"]
            },
            "summary": summary
        }

        # Add skip information only if significant
        if any(skip_counts.values()) and sum(skip_counts.values()) > 0:
            llm_content["skipped_items"] = {
                "total": sum(skip_counts.values()),
                "reasons": {k: v for k, v in skip_counts.items() if v > 0}
            }

        return _success(
            message,
            llm_content,
            items=items_data,
            summary=summary,
            pagination=pagination,
            listing_info=listing_info,
        )

    except PermissionError:
        return _error("Permission denied when accessing directory")
    except OSError as exc:
        return _error(f"IO error: {exc}")
    except Exception as exc:
        return _error(f"Unexpected error during directory listing: {exc}")

# -----------------------------------------------------------------------------
# Registration helper
# -----------------------------------------------------------------------------

def register_list_directory_tool(mcp: FastMCP):
    """Register the list_directory tool with proper tags synchronization."""
    common = dict(
        tags={"coding", "filesystem", "directory", "listing", "exploration", "metadata"}, 
        annotations={"category": "coding", "tags": ["coding", "filesystem", "directory", "listing", "exploration", "metadata"]}
    )
    mcp.tool(**common)(list_directory) 