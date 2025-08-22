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
from backend.infrastructure.mcp.utils.tool_result import success_response, error_response

__all__ = ["grep", "register_grep_tool"]

# -----------------------------------------------------------------------------
# Constants
# -----------------------------------------------------------------------------

SEARCH_TIMEOUT_SECONDS = 30

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
        
    Returns:
        CompletedProcess result from git grep
    """
    cmd = ["git", "grep"]
    
    # Pattern matching flags
    if case_insensitive:
        cmd.append("-i")
    
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
        if context_both is not None and context_both > 0:
            cmd.extend(["-C", str(context_both)])
        else:
            if context_after is not None and context_after > 0:
                cmd.extend(["-A", str(context_after)])
            if context_before is not None and context_before > 0:
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
        description="File or directory to search in (defaults to current working directory if not specified)",
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
"""

    # Handle Pydantic FieldInfo objects when invoked programmatically
    if isinstance(path, FieldInfo):
        path = None
    if isinstance(glob, FieldInfo):
        glob = None
    if isinstance(type, FieldInfo):
        type = None
    if isinstance(case_insensitive, FieldInfo):
        case_insensitive = False
    if isinstance(show_line_numbers, FieldInfo):
        show_line_numbers = False
    if isinstance(context_after, FieldInfo):
        context_after = None
    if isinstance(context_before, FieldInfo):
        context_before = None
    if isinstance(context_both, FieldInfo):
        context_both = None
    if isinstance(head_limit, FieldInfo):
        head_limit = None

    # Validate pattern
    if not pattern or not pattern.strip():
        return error_response("Search pattern is required and cannot be empty")

    # Validate output mode
    valid_modes = ["content", "files_with_matches", "count"]
    if output_mode not in valid_modes:
        return error_response(f"Invalid output_mode. Must be one of: {', '.join(valid_modes)}")

    # Check if git is available
    if not shutil.which("git"):
        return error_response("git is not installed or not available in PATH")
    
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
            return error_response("Not in a git repository - git grep requires a git repository")
            
    except Exception:
        return error_response("Unable to check git repository status")

    # Determine search path
    if path:
        # Validate provided path
        search_path_abs = validate_path_in_workspace(path)
        if search_path_abs is None:
            return error_response(f"Path is outside workspace: {path}")
        
        search_path = Path(search_path_abs)
        if not search_path.exists():
            return error_response(f"Path does not exist: {path}")
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
        )
        
        # Process git grep result
        
        # Handle git grep exit codes
        if result.returncode == 1:  # No matches found
            output_lines = []
        elif result.returncode != 0:  # Error occurred
            error_msg = result.stderr.strip() if result.stderr else "Unknown git grep error"
            return error_response(f"Search error: {error_msg}")
        else:
            # Process output
            output_lines = _process_output(result.stdout, head_limit)

        # Build response based on output mode
        
        if output_mode == "files_with_matches":
            total_files = len(output_lines)
            message = f"Found {total_files} file{'s' if total_files != 1 else ''}"
            
            # Simple LLM content - just the file paths, one per line (empty string if no files)
            llm_content = "\n".join(output_lines) if output_lines else ""
            
            return success_response(
                message,
                llm_content,
                files=output_lines,
                total_files=total_files,
                pattern=pattern,
            )
            
        elif output_mode == "count":
            # Parse count output (file:count format)
            total_matches = 0
            
            for line in output_lines:
                if ':' in line:
                    _, count_str = line.rsplit(':', 1)
                    try:
                        count = int(count_str)
                        total_matches += count
                    except ValueError:
                        continue
                        
            message = f"Found {total_matches} matches in {len(output_lines)} files"
            
            # Simple LLM content - just the count output, one per line
            llm_content = "\n".join(output_lines)
            
            return success_response(
                message,
                llm_content,
                total_matches=total_matches,
                total_files=len(output_lines),
                pattern=pattern,
            )
            
        else:  # content mode
            # For content mode, Claude Code doesn't show a count message
            # Just return the matching lines directly
            message = f"Search results for pattern '{pattern}'"
            
            # Simple LLM content - just the matching lines, one per line
            llm_content = "\n".join(output_lines)
            
            return success_response(
                message,
                llm_content,
                content=output_lines,
                total_lines=len(output_lines),
                pattern=pattern,
            )

    except TimeoutError as e:
        return error_response(str(e))
    except Exception as exc:
        return error_response(f"Unexpected error during search: {exc}")

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