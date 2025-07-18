"""glob tool – efficient file pattern matching with advanced filtering and sorting.

This tool provides atomic file path discovery functionality, focusing exclusively on 
finding and listing files that match glob patterns. It does NOT read file contents - 
use read_many_files or read_file for content retrieval.

Modeled after gemini-cli's glob tool for consistency and interoperability.
"""

from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
import fnmatch
import re
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
from backend.nagisa_mcp.utils.tool_result import ToolResult
from ..utils.file_filter import FileFilter
from .constants import (
    DEFAULT_EXCLUDE_PATTERNS,
    MAX_FILES_DEFAULT,
    MAX_FILES_HARD_LIMIT,
    GLOB_RECENCY_THRESHOLD_HOURS,
    GLOB_PATTERN_LIMIT,
)

__all__ = ["glob", "register_glob_tool"]

# -----------------------------------------------------------------------------
# Helper utilities
# -----------------------------------------------------------------------------

def _case_insensitive_glob(base: Path, pattern: str) -> List[Path]:
    """Perform case-insensitive glob matching manually.
    
    Since pathlib.Path.glob() doesn't support case_sensitive parameter in most
    Python versions, we implement manual case-insensitive matching.
    """
    try:
        # Convert pattern to regex for case-insensitive matching
        # Escape special regex chars but preserve glob wildcards
        escaped = re.escape(pattern)
        escaped = escaped.replace(r'\*\*', '§DOUBLESTAR§')  # Temp placeholder
        escaped = escaped.replace(r'\*', '[^/]*')  # * matches anything except /
        escaped = escaped.replace('§DOUBLESTAR§', '.*')  # ** matches anything including /
        escaped = escaped.replace(r'\?', '[^/]')  # ? matches single char except /
        
        regex_pattern = f"^{escaped}$"
        regex = re.compile(regex_pattern, re.IGNORECASE)
        
        # Walk directory tree and match manually
        found_files = []
        for path in base.rglob('*'):
            if path.is_file():
                try:
                    rel_path = path.relative_to(base)
                    if regex.match(str(rel_path)):
                        found_files.append(path)
                except ValueError:
                    continue  # Skip if path is not relative to base
        
        return found_files
    except Exception:
        return []

def _expand_globs_with_case_sensitivity(
    base: Path, 
    patterns: List[str], 
    case_sensitive: bool = True,
    max_files: int = 5000
) -> List[Path]:
    """Expand glob patterns with proper case sensitivity handling."""
    seen_files: set[Path] = set()
    found_files: List[Path] = []
    
    for pattern in patterns:
        if len(found_files) >= max_files:
            break
            
        try:
            # Handle absolute patterns
            if pattern.startswith('/'):
                pattern = pattern.lstrip('/')
            
            # Perform glob matching based on case sensitivity
            if case_sensitive:
                # Use standard glob for case-sensitive matching
                matches = list(base.glob(pattern))
            else:
                # Use manual case-insensitive matching
                matches = _case_insensitive_glob(base, pattern)
            
            # Filter to files only and deduplicate
            for file_path in matches:
                if len(found_files) >= max_files:
                    break
                    
                if file_path.is_file() and file_path not in seen_files:
                    seen_files.add(file_path)
                    found_files.append(file_path)
                    
        except Exception:
            # Skip invalid glob patterns
            continue
    
    return found_files

def _sort_files_by_recency(
    files: List[Path], 
    recency_threshold_hours: float = GLOB_RECENCY_THRESHOLD_HOURS
) -> List[Path]:
    """Sort files with recent files first (by mtime), then alphabetically."""
    
    current_time = datetime.now().timestamp()
    threshold_seconds = recency_threshold_hours * 3600
    
    def sort_key(file_path: Path) -> Tuple[int, float, str]:
        try:
            mtime = file_path.stat().st_mtime
            is_recent = (current_time - mtime) < threshold_seconds
            
            # Return tuple: (priority, -mtime, path)
            # Priority: 0 for recent files (sorted first), 1 for older files
            # -mtime: negative for newest-first sorting within recent files
            # path: alphabetical sorting for older files
            return (0 if is_recent else 1, -mtime if is_recent else 0, str(file_path))
        except Exception:
            # If we can't get file stats, sort to end
            return (2, 0, str(file_path))
    
    return sorted(files, key=sort_key)

def _get_file_info(file_path: Path, workspace_root: Path) -> Dict[str, Any]:
    """Get comprehensive file information for display."""
    try:
        stat_info = file_path.stat()
        rel_path = str(file_path.relative_to(workspace_root))
        
        return {
            "path": rel_path,
            "absolute_path": str(file_path),
            "size": stat_info.st_size,
            "modified_time": datetime.fromtimestamp(stat_info.st_mtime).isoformat(),
            "modified_timestamp": stat_info.st_mtime,
        }
    except Exception as e:
        # Fallback info if we can't get stats
        rel_path = str(file_path.relative_to(workspace_root)) if file_path.is_relative_to(workspace_root) else str(file_path)
        return {
            "path": rel_path,
            "absolute_path": str(file_path),
            "size": 0,
            "modified_time": "unknown",
            "modified_timestamp": 0,
            "error": str(e),
        }

def _apply_exclusion_filters(
    files: List[Path],
    exclusion_patterns: set[str],
    case_sensitive: bool,
    workspace_root: Path
) -> Tuple[List[Path], Dict[str, int]]:
    """Apply exclusion patterns to file list and return filtered files + skip counts."""
    
    if not exclusion_patterns:
        return files, {}
    
    filtered_files = []
    skipped_counts = {}
    
    for file_path in files:
        try:
            rel_path = file_path.relative_to(workspace_root)
            rel_path_str = str(rel_path)
            
            # Handle case sensitivity for exclusion patterns
            if not case_sensitive:
                rel_path_str = rel_path_str.lower()
                patterns_to_check = [p.lower() for p in exclusion_patterns]
            else:
                patterns_to_check = list(exclusion_patterns)
            
            # Check if file matches any exclusion pattern
            excluded = False
            for pattern in patterns_to_check:
                if fnmatch.fnmatch(rel_path_str, pattern):
                    excluded = True
                    break
            
            if excluded:
                skipped_counts["excluded_patterns"] = skipped_counts.get("excluded_patterns", 0) + 1
            else:
                filtered_files.append(file_path)
                
        except Exception:
            skipped_counts["path_errors"] = skipped_counts.get("path_errors", 0) + 1
    
    return filtered_files, skipped_counts

# -----------------------------------------------------------------------------
# Main implementation
# -----------------------------------------------------------------------------

def glob(
    pattern: str = Field(
        ...,
        description="Glob pattern to match files (e.g., 'src/**/*.py', '*.md', 'docs/**/*.rst'). Supports recursive (**) and single (*) wildcards.",
    ),
    path: Optional[str] = Field(
        None,
        description="Directory to search within (workspace-relative). If None, searches entire workspace.",
    ),
    case_sensitive: bool = Field(
        False,
        description="Whether pattern matching should be case-sensitive.",
    ),
    respect_git_ignore: bool = Field(
        True,
        description="Whether to respect .gitignore patterns when finding files.",
    ),
    use_default_excludes: bool = Field(
        True,
        description="Enable built-in exclusions for common directories (node_modules, .git, dist, etc.).",
    ),
    exclude: Optional[List[str]] = Field(
        None,
        description="Additional glob patterns to exclude from results (e.g., ['**/test_*.py', '**/*.pyc']).",
    ),
    show_hidden: bool = Field(
        False,
        description="Whether to include hidden files (starting with '.').",
    ),
    sort_by_recency: bool = Field(
        True,
        description="Sort results with recently modified files first, then alphabetically.",
    ),
    max_files: int = Field(
        MAX_FILES_DEFAULT,
        ge=1,
        le=MAX_FILES_HARD_LIMIT,
        description="Maximum number of files to return (performance protection).",
    ),
) -> Dict[str, Any]:
    """Find files matching glob patterns with advanced filtering and metadata.
    
    Returns file paths and metadata only - does NOT read file contents.
    Use for file discovery before reading with read_file or read_many_files.
    """

    # ------------------------------------------------------------------
    # Parameter validation and normalization
    # ------------------------------------------------------------------

    # Handle Pydantic FieldInfo objects when invoked programmatically
    if isinstance(path, FieldInfo):
        path = None
    if isinstance(exclude, FieldInfo):
        exclude = None
    if isinstance(case_sensitive, FieldInfo):
        case_sensitive = False
    if isinstance(respect_git_ignore, FieldInfo):
        respect_git_ignore = True
    if isinstance(use_default_excludes, FieldInfo):
        use_default_excludes = True
    if isinstance(show_hidden, FieldInfo):
        show_hidden = False
    if isinstance(sort_by_recency, FieldInfo):
        sort_by_recency = True
    if isinstance(max_files, FieldInfo):
        max_files = MAX_FILES_DEFAULT

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

    # Validate inputs
    if not pattern or not pattern.strip():
        return _error("Glob pattern is required and cannot be empty")

    if max_files <= 0 or max_files > MAX_FILES_HARD_LIMIT:
        return _error(f"max_files must be between 1 and {MAX_FILES_HARD_LIMIT}")

    # Validate workspace access
    if not validate_path_in_workspace("."):
        return _error("Cannot access workspace directory")

    # Determine search directory
    if path:
        search_abs_path = validate_path_in_workspace(path)
        if search_abs_path is None:
            return _error(f"Search path is outside workspace: {path}")
        
        search_dir = Path(search_abs_path)
        if not search_dir.exists():
            return _error(f"Search path does not exist: {path}")
        if not search_dir.is_dir():
            return _error(f"Search path is not a directory: {path}")
    else:
        search_dir = WORKSPACE_ROOT

    # ------------------------------------------------------------------
    # File discovery with proper case sensitivity handling
    # ------------------------------------------------------------------

    try:
        # Step 1: Perform glob matching with correct case sensitivity
        found_files = _expand_globs_with_case_sensitivity(
            search_dir, 
            [pattern],  # Single pattern for this simplified API
            case_sensitive,
            max_files * 2  # Allow some buffer for filtering
        )

        if not found_files:
            return _error(f"No files found matching pattern: {pattern}")

        # Step 2: Apply security and safety filters
        file_filter = FileFilter(
            workspace_root=WORKSPACE_ROOT,
            show_hidden=show_hidden,
            ignore_patterns=[],  # We'll handle exclusions separately
            respect_git_ignore=respect_git_ignore,
        )

        safe_files = []
        skipped_files = {}

        for file_path in found_files:
            if len(safe_files) >= max_files:
                break

            try:
                # Security checks
                if file_path.is_symlink() and not is_safe_symlink(file_path):
                    skipped_files["unsafe_symlinks"] = skipped_files.get("unsafe_symlinks", 0) + 1
                    continue

                if not check_parent_symlinks(file_path):
                    skipped_files["unsafe_parent_symlinks"] = skipped_files.get("unsafe_parent_symlinks", 0) + 1
                    continue

                # Apply file filter (gitignore, hidden files)
                if not file_filter.include(file_path):
                    if not show_hidden and file_path.name.startswith('.'):
                        skipped_files["hidden_files"] = skipped_files.get("hidden_files", 0) + 1
                    else:
                        skipped_files["gitignored"] = skipped_files.get("gitignored", 0) + 1
                    continue

                safe_files.append(file_path)

            except Exception:
                skipped_files["security_errors"] = skipped_files.get("security_errors", 0) + 1
                continue

        # Step 3: Apply exclusion patterns with proper case sensitivity
        exclusion_patterns = set(exclude or [])
        if use_default_excludes:
            exclusion_patterns.update(DEFAULT_EXCLUDE_PATTERNS)

        final_files, exclusion_skipped = _apply_exclusion_filters(
            safe_files,
            exclusion_patterns,
            case_sensitive,
            WORKSPACE_ROOT
        )

        # Merge skip counts
        skipped_files.update(exclusion_skipped)

        if not final_files:
            return _error(f"No files remained after filtering for pattern: {pattern}")

        # Step 4: Sort files
        if sort_by_recency:
            sorted_files = _sort_files_by_recency(final_files)
        else:
            sorted_files = sorted(final_files, key=str)

        # Step 5: Build comprehensive file information
        file_info_list = []
        for file_path in sorted_files:
            file_info = _get_file_info(file_path, WORKSPACE_ROOT)
            file_info_list.append(file_info)

        # ------------------------------------------------------------------
        # Build SOTA-level response structure
        # ------------------------------------------------------------------

        total_found = len(file_info_list)
        total_skipped = sum(skipped_files.values())
        
        # Create comprehensive summary
        summary = {
            "total_found": total_found,
            "total_skipped": total_skipped,
            "skipped_breakdown": skipped_files,
            "search_limited": len(final_files) >= max_files,
        }

        # Create detailed search info for transparency
        search_info = {
            "pattern": pattern,
            "search_path": str(search_dir.relative_to(WORKSPACE_ROOT)) if search_dir != WORKSPACE_ROOT else ".",
            "case_sensitive": case_sensitive,
            "respect_git_ignore": respect_git_ignore,
            "show_hidden": show_hidden,
            "sort_by_recency": sort_by_recency,
            "max_files": max_files,
            "exclude_patterns": list(exclusion_patterns) if exclusion_patterns else [],
        }

        # Build user-facing message
        message = f"Found {total_found} files"
        if total_skipped > 0:
            message += f" ({total_skipped} skipped)"
        if summary["search_limited"]:
            message += f" (limited to {max_files})"

        # Build structured LLM content following unified standard
        from datetime import datetime
        
        llm_content = {
            "operation": {
                "type": "glob",
                "pattern": pattern,
                "search_path": str(search_dir.relative_to(WORKSPACE_ROOT)) if search_dir != WORKSPACE_ROOT else "."
            },
            "result": {
                "files": file_info_list,
                "total_found": total_found,
                "search_limited": summary["search_limited"]
            }
        }

        # Add skip information only if significant
        if total_skipped > 0:
            llm_content["skipped_files"] = {
                "total": total_skipped,
                "reasons": {k: v for k, v in skipped_files.items() if v > 0}
            }

        return _success(
            message,
            llm_content,
            files=file_info_list,
            summary=summary,
            search_info=search_info,
        )

    except Exception as exc:
        return _error(f"Unexpected error during glob search: {exc}")

# -----------------------------------------------------------------------------
# Registration helper
# -----------------------------------------------------------------------------

def register_glob_tool(mcp: FastMCP):
    """Register the glob tool with proper tags synchronization."""
    common = dict(
        tags={"coding", "filesystem", "search", "pattern", "discovery"}, 
        annotations={"category": "coding", "tags": ["coding", "filesystem", "search", "pattern", "discovery"]}
    )
    mcp.tool(**common)(glob) 