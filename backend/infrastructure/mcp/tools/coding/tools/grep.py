"""grep tool – powerful search tool built on git grep."""

import subprocess
import shutil
from pathlib import Path
from typing import List, Dict, Any, Optional

from pydantic import Field
from pydantic.fields import FieldInfo
from fastmcp import FastMCP  # type: ignore

from ..utils.path_security import (
    validate_path_in_workspace, 
    WORKSPACE_ROOT
)
from backend.infrastructure.mcp.utils.tool_result import ToolResult

__all__ = ["grep", "register_grep_tool"]

# -----------------------------------------------------------------------------
# Constants
# -----------------------------------------------------------------------------

SEARCH_TIMEOUT_SECONDS = 30
MAX_OUTPUT_LINES = 10000

# File extension mappings for type filtering
FILE_TYPE_MAP = {
    "js": "*.js",
    "ts": "*.ts", 
    "py": "*.py",
    "python": "*.py",
    "java": "*.java",
    "cpp": "*.cpp",
    "c": "*.c",
    "rust": "*.rs",
    "go": "*.go",
    "php": "*.php",
    "rb": "*.rb",
    "ruby": "*.rb",
    "cs": "*.cs",
    "csharp": "*.cs",
    "sh": "*.sh",
    "bash": "*.sh",
    "json": "*.json",
    "yaml": "*.yaml",
    "yml": "*.yml",
    "xml": "*.xml",
    "html": "*.html",
    "css": "*.css",
    "scss": "*.scss",
    "less": "*.less",
    "md": "*.md",
    "markdown": "*.md",
    "txt": "*.txt",
}

# -----------------------------------------------------------------------------
# Helper functions
# -----------------------------------------------------------------------------

def _run_git_grep(
    pattern: str,
    search_path: Path,
    glob_pattern: Optional[str] = None,
    file_type: Optional[str] = None,
    output_mode: str = "files_with_matches",
    case_insensitive: bool = False,
    show_line_numbers: bool = False,
    context_after: Optional[int] = None,
    context_before: Optional[int] = None,
    context_both: Optional[int] = None,
    multiline: bool = False,
    head_limit: Optional[int] = None
) -> subprocess.CompletedProcess:
    """Run git grep with specified parameters.
    
    Args:
        pattern: Search pattern
        search_path: Directory or file to search
        glob_pattern: Glob pattern to filter files
        file_type: File type filter
        output_mode: Output mode (content/files_with_matches/count)
        case_insensitive: Whether to ignore case
        show_line_numbers: Whether to show line numbers
        context_after: Lines to show after match
        context_before: Lines to show before match
        context_both: Lines to show before and after match
        multiline: Enable multiline mode
        head_limit: Limit output lines (handled in post-processing)
        
    Returns:
        CompletedProcess result from git grep
    """
    cmd = ["git", "grep"]
    
    # Pattern matching flags
    if case_insensitive:
        cmd.append("-i")
    
    # Note: git grep has limited multiline support compared to ripgrep
    # We'll ignore the multiline flag for now
    
    # Output mode
    if output_mode == "files_with_matches":
        cmd.append("-l")  # Only file names
    elif output_mode == "count":
        cmd.append("-c")  # Count matches
    # For "content" mode, no special flag needed
    
    # Line numbers (only for content mode)
    if show_line_numbers and output_mode == "content":
        cmd.append("-n")
    
    # Context lines (only for content mode)
    if output_mode == "content":
        if context_both is not None:
            cmd.extend(["-C", str(context_both)])
        else:
            if context_after is not None:
                cmd.extend(["-A", str(context_after)])
            if context_before is not None:
                cmd.extend(["-B", str(context_before)])
    
    # Add pattern
    cmd.append(pattern)
    
    # Add pathspec separator
    cmd.append("--")
    
    # File filtering - git grep uses pathspecs after --
    if glob_pattern:
        cmd.append(glob_pattern)
    elif file_type and file_type in FILE_TYPE_MAP:
        cmd.append(FILE_TYPE_MAP[file_type])
    else:
        # Search all files if no filter specified
        cmd.append("*")
    
    # Execute git grep from git root
    try:
        # Find git root for this command execution
        git_root_result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            cwd=search_path if search_path.is_dir() else search_path.parent,
            timeout=5
        )
        if git_root_result.returncode != 0:
            raise Exception("Not in a git repository")
            
        git_root = Path(git_root_result.stdout.strip())
        # Running git grep from repository root
        
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=SEARCH_TIMEOUT_SECONDS,
            cwd=git_root
        )
        return result
    except subprocess.TimeoutExpired:
        raise TimeoutError(f"Search timed out after {SEARCH_TIMEOUT_SECONDS} seconds")

def _process_output(
    output: str, 
    head_limit: Optional[int] = None
) -> List[str]:
    """Process git grep output and apply head limit.
    
    Args:
        output: Raw output from git grep
        head_limit: Maximum lines to return
        
    Returns:
        List of output lines
    """
    if not output.strip():
        return []
    
    lines = output.strip().split('\n')
    
    # Apply head limit if specified
    if head_limit:
        lines = lines[:head_limit]
    
    return lines

# -----------------------------------------------------------------------------
# Main implementation
# -----------------------------------------------------------------------------

def grep(
    pattern: str = Field(
        ...,
        description="The regular expression pattern to search for in file contents",
    ),
    path: Optional[str] = Field(
        None,
        description="File or directory to search in (git grep PATH). Defaults to current working directory.",
    ),
    glob: Optional[str] = Field(
        None,
        description="Glob pattern to filter files (e.g. \"*.js\", \"*.{ts,tsx}\") - maps to git grep pathspec",
    ),
    type: Optional[str] = Field(
        None,
        description="File type to search (git grep --type). Common types: js, py, rust, go, java, etc. More efficient than include for standard file types.",
    ),
    output_mode: str = Field(
        "files_with_matches",
        description="Output mode: \"content\" shows matching lines (supports -A/-B/-C context, -n line numbers, head_limit), \"files_with_matches\" shows file paths (supports head_limit), \"count\" shows match counts (supports head_limit). Defaults to \"files_with_matches\".",
    ),
    case_insensitive: bool = Field(
        False,
        description="Case insensitive search (git grep -i)",
        alias="-i"
    ),
    show_line_numbers: bool = Field(
        False,
        description="Show line numbers in output (git grep -n). Requires output_mode: \"content\", ignored otherwise.",
        alias="-n"
    ),
    context_after: Optional[int] = Field(
        None,
        description="Number of lines to show after each match (git grep -A). Requires output_mode: \"content\", ignored otherwise.",
        alias="-A"
    ),
    context_before: Optional[int] = Field(
        None,
        description="Number of lines to show before each match (git grep -B). Requires output_mode: \"content\", ignored otherwise.",
        alias="-B"
    ),
    context_both: Optional[int] = Field(
        None,
        description="Number of lines to show before and after each match (git grep -C). Requires output_mode: \"content\", ignored otherwise.",
        alias="-C"
    ),
    multiline: bool = Field(
        False,
        description="Enable multiline mode where . matches newlines and patterns can span lines (git grep -U --multiline-dotall). Default: false.",
    ),
    head_limit: Optional[int] = Field(
        None,
        description="Limit output to first N lines/entries, equivalent to \"| head -N\". Works across all output modes: content (limits output lines), files_with_matches (limits file paths), count (limits count entries). When unspecified, shows all results from git grep.",
    ),
) -> Dict[str, Any]:
    """A powerful search tool built on git grep

  Usage:
  - ALWAYS use Grep for search tasks. NEVER invoke `grep` or `rg` as a Bash command. The Grep tool has been optimized for correct permissions and access.
  - Supports full regex syntax (e.g., "log.*Error", "function\\s+\\w+")
  - Filter files with glob parameter (e.g., "*.js", "**/*.tsx") or type parameter (e.g., "js", "py", "rust")
  - Output modes: "content" shows matching lines, "files_with_matches" shows only file paths (default), "count" shows match counts
  - Use Task tool for open-ended searches requiring multiple rounds
  - Pattern syntax: Uses git grep (not grep) - literal braces need escaping (use `interface\\{\\}` to find `interface{}` in Go code)
  - Multiline matching: By default patterns match within single lines only. For cross-line patterns like `struct \\{[\\s\\S]*?field`, use `multiline: true`
"""

    # Handle Pydantic FieldInfo objects when invoked programmatically
    if isinstance(path, FieldInfo):
        path = None
    if isinstance(glob, FieldInfo):
        glob = None
    if isinstance(type, FieldInfo):
        type = None

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
        return _error("Search pattern is required and cannot be empty")

    # Validate output mode
    valid_modes = ["content", "files_with_matches", "count"]
    if output_mode not in valid_modes:
        return _error(f"Invalid output_mode. Must be one of: {', '.join(valid_modes)}")

    # Check if git is available
    if not shutil.which("git"):
        return _error("git is not installed or not available in PATH")
    
    # Find git repository root
    git_root = None
    try:
        # Try to find git root from various possible locations
        search_dirs = [WORKSPACE_ROOT, WORKSPACE_ROOT.parent, Path.cwd()]
        
        for search_dir in search_dirs:
            git_check = subprocess.run(
                ["git", "rev-parse", "--show-toplevel"],
                capture_output=True,
                text=True,
                cwd=search_dir,
                timeout=5
            )
            if git_check.returncode == 0:
                git_root = Path(git_check.stdout.strip())
                break
        
        if git_root is None:
            return _error("Not in a git repository - git grep requires a git repository")
            
    except Exception:
        return _error("Unable to check git repository status")

    # Determine search path
    if path:
        # Validate provided path
        search_path_abs = validate_path_in_workspace(path)
        if search_path_abs is None:
            return _error(f"Path is outside workspace: {path}")
        
        search_path = Path(search_path_abs)
        if not search_path.exists():
            return _error(f"Path does not exist: {path}")
    else:
        # Default to workspace root
        search_path = WORKSPACE_ROOT

    try:
        # Run git grep
        result = _run_git_grep(
            pattern=pattern,
            search_path=search_path,
            glob_pattern=glob,
            file_type=type,
            output_mode=output_mode,
            case_insensitive=case_insensitive,
            show_line_numbers=show_line_numbers,
            context_after=context_after,
            context_before=context_before,
            context_both=context_both,
            multiline=multiline,
            head_limit=head_limit
        )
        
        # Process git grep result
        
        # Handle git grep exit codes
        if result.returncode == 1:  # No matches found
            search_path_str = str(search_path.relative_to(WORKSPACE_ROOT)) if search_path != WORKSPACE_ROOT else "."
            return _error(f"No matches found for pattern '{pattern}' in '{search_path_str}'")
        elif result.returncode != 0:  # Error occurred
            error_msg = result.stderr.strip() if result.stderr else "Unknown git grep error"
            return _error(f"Search error: {error_msg}")

        # Process output
        output_lines = _process_output(result.stdout, head_limit)
        
        if not output_lines:
            search_path_str = str(search_path.relative_to(WORKSPACE_ROOT)) if search_path != WORKSPACE_ROOT else "."
            return _error(f"No matches found for pattern '{pattern}' in '{search_path_str}'")

        # Build response based on output mode
        search_path_str = str(search_path.relative_to(WORKSPACE_ROOT)) if search_path != WORKSPACE_ROOT else "."
        
        if output_mode == "files_with_matches":
            total_files = len(output_lines)
            message = f"Found {total_files} file{'s' if total_files != 1 else ''} with matches"
            
            llm_content = {
                "operation": {
                    "type": "grep",
                    "pattern": pattern,
                    "search_path": search_path_str,
                    "output_mode": output_mode
                },
                "result": {
                    "files": output_lines,
                    "total_files": total_files,
                    "truncated": head_limit is not None and len(output_lines) == head_limit
                }
            }
            
            return _success(
                message,
                llm_content,
                files=output_lines,
                total_files=total_files,
                pattern=pattern,
                search_path=search_path_str,
            )
            
        elif output_mode == "count":
            # Parse count output (file:count format)
            count_data = []
            total_matches = 0
            
            for line in output_lines:
                if ':' in line:
                    file_path, count_str = line.rsplit(':', 1)
                    try:
                        count = int(count_str)
                        count_data.append({"file": file_path, "count": count})
                        total_matches += count
                    except ValueError:
                        continue
                        
            message = f"Found {total_matches} matches in {len(count_data)} files"
            
            llm_content = {
                "operation": {
                    "type": "grep",
                    "pattern": pattern,
                    "search_path": search_path_str,
                    "output_mode": output_mode
                },
                "result": {
                    "counts": count_data,
                    "total_matches": total_matches,
                    "total_files": len(count_data),
                    "truncated": head_limit is not None and len(output_lines) == head_limit
                }
            }
            
            return _success(
                message,
                llm_content,
                counts=count_data,
                total_matches=total_matches,
                total_files=len(count_data),
                pattern=pattern,
                search_path=search_path_str,
            )
            
        else:  # content mode
            total_lines = len(output_lines)
            message = f"Found {total_lines} matching line{'s' if total_lines != 1 else ''}"
            
            llm_content = {
                "operation": {
                    "type": "grep",
                    "pattern": pattern,
                    "search_path": search_path_str,
                    "output_mode": output_mode
                },
                "result": {
                    "content": output_lines,
                    "total_lines": total_lines,
                    "truncated": head_limit is not None and len(output_lines) == head_limit
                }
            }
            
            return _success(
                message,
                llm_content,
                content=output_lines,
                total_lines=total_lines,
                pattern=pattern,
                search_path=search_path_str,
            )

    except TimeoutError as e:
        return _error(str(e))
    except Exception as exc:
        return _error(f"Unexpected error during search: {exc}")

# -----------------------------------------------------------------------------
# Registration helper
# -----------------------------------------------------------------------------

def register_grep_tool(mcp: FastMCP):
    """Register the grep tool with proper tags synchronization."""
    common = dict(
        tags={"coding", "filesystem", "search", "content", "regex", "grep"}, 
        annotations={"category": "coding", "tags": ["coding", "filesystem", "search", "content", "regex", "grep"]}
    )
    mcp.tool(**common)(grep)