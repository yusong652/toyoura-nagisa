"""grep tool – efficient regex pattern matching within file contents.

This tool provides atomic content search functionality, focusing exclusively on 
finding text patterns within files. It does NOT list files or read entire contents - 
use glob for file discovery and read_file for full content retrieval.

Modeled after gemini-cli's grep tool for consistency and interoperability.
"""

from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
import re
import subprocess
import shutil
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
from ..utils.tool_result import ToolResult
from ..utils.file_filter import FileFilter
from .constants import (
    DEFAULT_EXCLUDE_PATTERNS,
    MAX_FILES_DEFAULT,
    TEXT_EXTENSIONS,
    BINARY_EXTENSIONS,
    TEXT_CHARSET_DEFAULT,
    BINARY_DETECTION_SAMPLE_SIZE,
)

__all__ = ["grep", "register_grep_tool"]

# -----------------------------------------------------------------------------
# Constants specific to content search
# -----------------------------------------------------------------------------

MAX_SEARCH_FILES = 2000  # Maximum files to search through
MAX_MATCHES_PER_FILE = 50  # Maximum matches to return per file
MAX_TOTAL_MATCHES = 500  # Maximum total matches across all files
MAX_LINE_LENGTH = 1000  # Maximum line length to display (truncate longer lines)
CONTEXT_LINES = 0  # Number of context lines around matches (0 for exact matches only)

# Performance limits
SEARCH_TIMEOUT_SECONDS = 30  # Maximum time for external commands
MAX_FILE_SIZE_FOR_SEARCH = 10 * 1024 * 1024  # 10MB max file size to search

# -----------------------------------------------------------------------------
# Data structures
# -----------------------------------------------------------------------------

class SearchMatch:
    """Represents a single search match within a file."""
    
    def __init__(self, line_number: int, line_content: str, match_start: int = 0, match_end: int = 0):
        self.line_number = line_number
        self.line_content = line_content.rstrip('\r\n')  # Clean line endings
        self.match_start = match_start
        self.match_end = match_end
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "line_number": self.line_number,
            "line_content": self.line_content,
            "match_start": self.match_start,
            "match_end": self.match_end,
        }

class FileSearchResult:
    """Represents search results for a single file."""
    
    def __init__(self, file_path: str, matches: List[SearchMatch]):
        self.file_path = file_path
        self.matches = matches
        self.match_count = len(matches)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "file_path": self.file_path,
            "match_count": self.match_count,
            "matches": [match.to_dict() for match in self.matches],
        }

# -----------------------------------------------------------------------------
# Helper utilities
# -----------------------------------------------------------------------------

def _is_text_file(file_path: Path) -> bool:
    """Determine if a file is likely a text file."""
    try:
        # Check by extension first
        ext = file_path.suffix.lower()
        if ext in TEXT_EXTENSIONS:
            return True
        if ext in BINARY_EXTENSIONS:
            return False
        
        # Binary detection by sampling file content
        with file_path.open('rb') as f:
            sample = f.read(BINARY_DETECTION_SAMPLE_SIZE)
            # Consider it binary if it contains null bytes
            return b'\x00' not in sample
    except Exception:
        return False

def _is_file_too_large(file_path: Path) -> bool:
    """Check if file is too large for efficient searching."""
    try:
        return file_path.stat().st_size > MAX_FILE_SIZE_FOR_SEARCH
    except Exception:
        return True

def _truncate_line(line: str, max_length: int = MAX_LINE_LENGTH) -> str:
    """Truncate a line if it's too long, adding ellipsis."""
    if len(line) <= max_length:
        return line
    return line[:max_length-3] + "..."

def _try_git_grep(
    pattern: str, 
    search_dir: Path, 
    include_pattern: Optional[str] = None,
    case_sensitive: bool = True
) -> Optional[List[FileSearchResult]]:
    """Try to use git grep for searching (fastest option)."""
    try:
        # Check if git is available
        if not shutil.which('git'):
            return None
            
        # Check if we're in a git repository
        git_check = subprocess.run(
            ['git', 'rev-parse', '--git-dir'],
            cwd=search_dir,
            capture_output=True,
            timeout=5,
            text=True
        )
        if git_check.returncode != 0:
            return None
            
        # Build git grep command
        cmd = ['git', 'grep', '--untracked', '-n', '-E']
        if not case_sensitive:
            cmd.append('-i')  # Add ignore-case flag only if case insensitive
        cmd.append(pattern)
        
        if include_pattern:
            cmd.extend(['--', include_pattern])
            
        # Execute git grep
        result = subprocess.run(
            cmd,
            cwd=search_dir,
            capture_output=True,
            timeout=SEARCH_TIMEOUT_SECONDS,
            text=True
        )
        
        if result.returncode == 1:  # No matches found
            return []
        elif result.returncode != 0:  # Error occurred
            return None
            
        return _parse_grep_output(result.stdout, search_dir)
        
    except Exception:
        return None

def _try_system_grep(
    pattern: str, 
    search_dir: Path, 
    include_pattern: Optional[str] = None,
    case_sensitive: bool = True
) -> Optional[List[FileSearchResult]]:
    """Try to use system grep for searching."""
    try:
        # Check if grep is available
        if not shutil.which('grep'):
            return None
            
        # Build grep command
        cmd = ['grep', '-r', '-n', '-E']
        if not case_sensitive:
            cmd.append('-i')  # Add ignore-case flag only if case insensitive
        
        # Add common exclusions
        for exclude_dir in ['.git', 'node_modules', '__pycache__', '.cache']:
            cmd.extend(['--exclude-dir', exclude_dir])
            
        if include_pattern:
            cmd.extend(['--include', include_pattern])
            
        cmd.extend([pattern, '.'])
        
        # Execute system grep
        result = subprocess.run(
            cmd,
            cwd=search_dir,
            capture_output=True,
            timeout=SEARCH_TIMEOUT_SECONDS,
            text=True
        )
        
        if result.returncode == 1:  # No matches found
            return []
        elif result.returncode != 0:  # Error occurred
            return None
            
        return _parse_grep_output(result.stdout, search_dir)
        
    except Exception:
        return None

def _parse_grep_output(output: str, base_dir: Path) -> List[FileSearchResult]:
    """Parse grep output format: filepath:line_number:line_content"""
    file_results = {}
    
    for line in output.strip().split('\n'):
        if not line.strip():
            continue
            
        # Parse grep output format
        parts = line.split(':', 2)
        if len(parts) < 3:
            continue
            
        file_path_str, line_num_str, line_content = parts
        
        try:
            line_number = int(line_num_str)
        except ValueError:
            continue
            
        # Normalize file path
        file_path = str(Path(file_path_str).relative_to(base_dir)) if base_dir else file_path_str
        
        # Create match object
        match = SearchMatch(line_number, _truncate_line(line_content))
        
        # Group by file
        if file_path not in file_results:
            file_results[file_path] = []
        file_results[file_path].append(match)
    
    # Convert to FileSearchResult objects
    results = []
    for file_path, matches in file_results.items():
        # Sort matches by line number
        matches.sort(key=lambda m: m.line_number)
        # Limit matches per file
        matches = matches[:MAX_MATCHES_PER_FILE]
        results.append(FileSearchResult(file_path, matches))
    
    return results

def _fallback_python_search(
    pattern: str,
    search_dir: Path,
    include_pattern: Optional[str] = None,
    respect_git_ignore: bool = True,
    use_default_excludes: bool = True,
    case_sensitive: bool = True
) -> List[FileSearchResult]:
    """Python fallback implementation for text searching."""
    try:
        # Compile regex pattern with appropriate flags
        flags = re.MULTILINE
        if not case_sensitive:
            flags |= re.IGNORECASE
        regex = re.compile(pattern, flags)
    except re.error as e:
        raise ValueError(f"Invalid regular expression: {e}")
    
    # Build file filter
    file_filter = FileFilter(
        workspace_root=WORKSPACE_ROOT,
        show_hidden=False,
        ignore_patterns=None,
        respect_git_ignore=respect_git_ignore,
    )
    
    # Build exclusion patterns
    exclusion_patterns = set()
    if use_default_excludes:
        exclusion_patterns.update(DEFAULT_EXCLUDE_PATTERNS)
    
    # Find files to search
    if include_pattern:
        # Use glob pattern if provided
        file_paths = list(search_dir.glob(include_pattern))
    else:
        # Search all text files
        file_paths = list(search_dir.rglob('*'))
    
    # Filter and search files
    results = []
    total_matches = 0
    files_searched = 0
    
    for file_path in file_paths:
        if files_searched >= MAX_SEARCH_FILES:
            break
            
        if total_matches >= MAX_TOTAL_MATCHES:
            break
            
        try:
            # Basic file checks
            if not file_path.is_file():
                continue
                
            if _is_file_too_large(file_path):
                continue
                
            if not _is_text_file(file_path):
                continue
                
            # Security checks
            if file_path.is_symlink() and not is_safe_symlink(file_path):
                continue
                
            if not check_parent_symlinks(file_path):
                continue
            
            # Apply file filters
            if not file_filter.include(file_path):
                continue
                
            # Search within file
            matches = _search_file_content(file_path, regex, search_dir)
            if matches:
                # Limit matches per file
                matches = matches[:MAX_MATCHES_PER_FILE]
                results.append(FileSearchResult(
                    str(file_path.relative_to(search_dir)), 
                    matches
                ))
                total_matches += len(matches)
                
            files_searched += 1
            
        except Exception:
            # Skip files that can't be processed
            continue
    
    return results

def _search_file_content(file_path: Path, regex: re.Pattern, base_dir: Path) -> List[SearchMatch]:
    """Search for pattern within a single file."""
    matches = []
    
    try:
        with file_path.open('r', encoding=TEXT_CHARSET_DEFAULT, errors='ignore') as f:
            for line_number, line in enumerate(f, 1):
                line = line.rstrip('\r\n')
                
                # Find all matches in the line
                for match in regex.finditer(line):
                    search_match = SearchMatch(
                        line_number=line_number,
                        line_content=_truncate_line(line),
                        match_start=match.start(),
                        match_end=match.end()
                    )
                    matches.append(search_match)
                    
                    # Limit matches per file
                    if len(matches) >= MAX_MATCHES_PER_FILE:
                        return matches
                        
    except Exception:
        # Return empty list for files that can't be read
        pass
    
    return matches

def _apply_include_filter(
    files: List[Path],
    include_pattern: Optional[str],
    search_dir: Path
) -> List[Path]:
    """Apply include pattern filter to file list."""
    if not include_pattern:
        return files
        
    try:
        # Use glob pattern matching
        filtered_files = []
        for file_path in files:
            rel_path = file_path.relative_to(search_dir)
            if rel_path.match(include_pattern):
                filtered_files.append(file_path)
        return filtered_files
    except Exception:
        return files

# -----------------------------------------------------------------------------
# Main implementation
# -----------------------------------------------------------------------------

def grep(
    pattern: str = Field(
        ...,
        description="Regular expression pattern to search for within file contents (e.g., 'function\\s+\\w+', 'import.*from', 'class\\s+\\w+').",
    ),
    path: Optional[str] = Field(
        None,
        description="Directory to search within (workspace-relative). If None, searches entire workspace.",
    ),
    include: Optional[str] = Field(
        None,
        description="Glob pattern to filter which files are searched (e.g., '*.py', '*.{js,ts}', 'src/**'). If omitted, searches all text files.",
    ),
    case_sensitive: bool = Field(
        False,
        description="Whether pattern matching should be case-sensitive.",
    ),
    respect_git_ignore: bool = Field(
        True,
        description="Whether to respect .gitignore patterns when selecting files to search.",
    ),
    use_default_excludes: bool = Field(
        True,
        description="Enable built-in exclusions for common directories (node_modules, .git, dist, etc.).",
    ),
    max_matches: int = Field(
        MAX_TOTAL_MATCHES,
        ge=1,
        le=2000,
        description="Maximum total number of matches to return across all files.",
    ),
) -> Dict[str, Any]:
    """Search for regex patterns within file contents and return matching lines with context.

    ## Core Functionality
    - Searches for regular expression patterns within text file contents
    - Returns **matching lines with line numbers** - does NOT return full file contents
    - Supports advanced filtering by file patterns and directory exclusions
    - Designed for code search and content discovery, not file listing or full content reading

    ## Strategic Usage
    - Use this tool to **find code patterns** like function definitions, imports, or specific logic
    - Perfect for codebase exploration: `'class\\s+\\w+'` to find class definitions
    - Combine with include patterns: `include='*.py'` to search only Python files
    - Use after `glob` to search within specific file sets

    ## Pattern Examples
    - `'function\\s+\\w+'` - Function definitions
    - `'import.*from'` - Import statements  
    - `'TODO|FIXME'` - Code comments with tasks
    - `'def\\s+test_\\w+'` - Test function definitions
    - `'class\\s+\\w+\\('` - Class definitions with inheritance

    ## Return Value
    Returns a JSON object with the following structure:
    
    ```json
    {
      "files": [
        {
          "file_path": "src/main.py",
          "match_count": 3,
          "matches": [
            {
              "line_number": 15,
              "line_content": "def main_function():",
              "match_start": 0,
              "match_end": 8
            }
          ]
        }
      ],
      "summary": {
        "total_files_with_matches": 2,
        "total_matches": 5,
        "files_searched": 45,
        "search_strategy": "git_grep"
      },
      "search_info": {
        "pattern": "def\\s+\\w+",
        "search_path": "src",
        "include": "*.py",
        "case_sensitive": false,
        "max_matches": 500
      }
    }
    ```

    The `files` array contains detailed match information for each file.
    Use `summary` to understand search coverage and performance.
    Use `search_info` to see exactly what search parameters were applied.
    """

    # ------------------------------------------------------------------
    # Parameter validation and normalization
    # ------------------------------------------------------------------

    # Handle Pydantic FieldInfo objects when invoked programmatically
    if isinstance(path, FieldInfo):
        path = None
    if isinstance(include, FieldInfo):
        include = None
    if isinstance(case_sensitive, FieldInfo):
        case_sensitive = False
    if isinstance(respect_git_ignore, FieldInfo):
        respect_git_ignore = True
    if isinstance(use_default_excludes, FieldInfo):
        use_default_excludes = True
    if isinstance(max_matches, FieldInfo):
        max_matches = MAX_TOTAL_MATCHES

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
        return _error("Search pattern is required and cannot be empty")

    # Validate regex pattern
    try:
        flags = 0 if case_sensitive else re.IGNORECASE
        re.compile(pattern, flags)
    except re.error as e:
        return _error(f"Invalid regular expression pattern: {e}")

    if max_matches <= 0 or max_matches > 2000:
        return _error("max_matches must be between 1 and 2000")

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
    # Execute search with multiple strategies (fast -> fallback)
    # ------------------------------------------------------------------

    try:
        search_results = None
        strategy_used = "none"
        files_searched = 0
        
        # Strategy 1: Try git grep (fastest)
        search_results = _try_git_grep(pattern, search_dir, include, case_sensitive)
        if search_results is not None:
            strategy_used = "git_grep"

        # Strategy 2: Try system grep (second fastest)
        if search_results is None:
            search_results = _try_system_grep(pattern, search_dir, include, case_sensitive)
            if search_results is not None:
                strategy_used = "system_grep"

        # Strategy 3: Python fallback (most compatible)
        if search_results is None:
            search_results = _fallback_python_search(
                pattern, 
                search_dir, 
                include, 
                respect_git_ignore, 
                use_default_excludes,
                case_sensitive
            )
            strategy_used = "python_fallback"
            # Estimate files searched for Python fallback
            files_searched = min(MAX_SEARCH_FILES, len(list(search_dir.rglob('*'))))

        if not search_results:
            search_path_display = str(search_dir.relative_to(WORKSPACE_ROOT)) if search_dir != WORKSPACE_ROOT else "."
            include_info = f" (include: {include})" if include else ""
            return _error(f"No matches found for pattern '{pattern}' in path '{search_path_display}'{include_info}")

        # Apply max_matches limit across all files
        total_matches = 0
        limited_results = []
        
        for file_result in search_results:
            if total_matches >= max_matches:
                break
                
            # Limit matches in this file
            remaining_matches = max_matches - total_matches
            if len(file_result.matches) > remaining_matches:
                file_result.matches = file_result.matches[:remaining_matches]
                file_result.match_count = len(file_result.matches)
            
            limited_results.append(file_result)
            total_matches += file_result.match_count

        # ------------------------------------------------------------------
        # Build SOTA-level response structure
        # ------------------------------------------------------------------

        # Convert results to dictionaries
        files_data = [result.to_dict() for result in limited_results]
        
        # Create comprehensive summary
        summary = {
            "total_files_with_matches": len(files_data),
            "total_matches": total_matches,
            "files_searched": files_searched if files_searched > 0 else len(limited_results),
            "search_strategy": strategy_used,
            "search_limited": total_matches >= max_matches,
        }

        # Create detailed search info for transparency
        search_info = {
            "pattern": pattern,
            "search_path": str(search_dir.relative_to(WORKSPACE_ROOT)) if search_dir != WORKSPACE_ROOT else ".",
            "include": include,
            "case_sensitive": case_sensitive,
            "respect_git_ignore": respect_git_ignore,
            "max_matches": max_matches,
        }

        # Build user-facing message
        files_count = len(files_data)
        files_word = "file" if files_count == 1 else "files"
        matches_word = "match" if total_matches == 1 else "matches"
        
        message = f"Found {total_matches} {matches_word} in {files_count} {files_word}"
        if summary["search_limited"]:
            message += f" (limited to {max_matches})"

        # CRITICAL: LLM content must match the docstring structure exactly
        llm_content = {
            "files": files_data,
            "summary": summary,
            "search_info": search_info,
        }

        return _success(
            message,
            llm_content,
            files=files_data,
            summary=summary,
            search_info=search_info,
        )

    except Exception as exc:
        return _error(f"Unexpected error during content search: {exc}")

# -----------------------------------------------------------------------------
# Registration helper
# -----------------------------------------------------------------------------

def register_grep_tool(mcp: FastMCP):
    """Register the grep tool with proper tags synchronization."""
    common = dict(
        tags={"coding", "filesystem", "search", "content", "regex"}, 
        annotations={"category": "coding", "tags": ["coding", "filesystem", "search", "content", "regex"]}
    )
    mcp.tool(**common)(grep) 