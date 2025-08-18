"""edit tool – precise text replacement within files with intelligent error handling.

This tool provides atomic file editing functionality, focusing exclusively on 
replacing specific text content within files. It does NOT list files or read 
entire contents - use glob for file discovery and read_file for content examination.

Fully aligned with Claude's Edit tool for consistency and improved usability.
"""

from pathlib import Path
from typing import Dict, Any, Optional, Tuple
import difflib
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
from .constants import (
    TEXT_CHARSET_DEFAULT,
)

__all__ = ["edit", "register_edit_tool"]

# -----------------------------------------------------------------------------
# Constants specific to file editing
# -----------------------------------------------------------------------------

MAX_EDIT_FILE_SIZE = 5 * 1024 * 1024  # 5MB max file size for editing
MAX_OLD_STRING_LENGTH = 50000  # Maximum length of old_string parameter
MAX_NEW_STRING_LENGTH = 50000  # Maximum length of new_string parameter

# Context requirements for single replacements
MIN_CONTEXT_LINES = 3  # Minimum lines of context required

# -----------------------------------------------------------------------------
# Helper utilities
# -----------------------------------------------------------------------------

def _validate_file_for_editing(file_path: Path) -> Tuple[bool, Optional[str]]:
    """Validate if a file can be safely edited."""
    try:
        if file_path.exists():
            # Check file size
            if file_path.stat().st_size > MAX_EDIT_FILE_SIZE:
                return False, f"File too large for editing: {file_path.stat().st_size} bytes (max: {MAX_EDIT_FILE_SIZE})"
            
            # Check if it's a text file (basic check)
            try:
                with file_path.open('rb') as f:
                    sample = f.read(1024)
                    if b'\x00' in sample:
                        return False, "File appears to be binary and cannot be edited as text"
            except Exception:
                return False, "Cannot read file for validation"
                
        return True, None
    except Exception as e:
        return False, f"File validation error: {e}"

def _count_occurrences(content: str, search_string: str) -> int:
    """Count exact occurrences of search_string in content."""
    if not search_string:
        return 0
    return content.count(search_string)

def _apply_single_replacement(content: str, old_string: str, new_string: str) -> Tuple[str, int]:
    """Apply replacement of first occurrence of old_string with new_string in content.
    
    Returns:
        Tuple of (modified content, number of replacements made)
    """
    if not old_string:
        return content, 0
    
    # Find first occurrence
    index = content.find(old_string)
    if index == -1:
        return content, 0
    
    # Replace only the first occurrence
    new_content = content[:index] + new_string + content[index + len(old_string):]
    return new_content, 1

def _apply_all_replacements(content: str, old_string: str, new_string: str) -> Tuple[str, int]:
    """Apply replacement of all occurrences of old_string with new_string in content.
    
    Returns:
        Tuple of (modified content, number of replacements made)
    """
    if not old_string:
        return content, 0
    
    count = content.count(old_string)
    if count == 0:
        return content, 0
    
    new_content = content.replace(old_string, new_string)
    return new_content, count

def _normalize_line_endings(content: str) -> str:
    """Normalize line endings to LF for consistent processing."""
    return content.replace('\r\n', '\n').replace('\r', '\n')

def _generate_diff(original: str, modified: str, filename: str = "file") -> str:
    """Generate a unified diff between original and modified content."""
    original_lines = original.splitlines(keepends=True)
    modified_lines = modified.splitlines(keepends=True)
    
    diff = list(difflib.unified_diff(
        original_lines,
        modified_lines,
        fromfile=f"{filename} (original)",
        tofile=f"{filename} (modified)",
        n=3  # 3 lines of context
    ))
    
    return ''.join(diff)

def _validate_uniqueness(content: str, old_string: str, replace_all: bool) -> Tuple[bool, Optional[str]]:
    """Validate that old_string is unique when replace_all is False."""
    if replace_all or not old_string:
        return True, None
    
    occurrences = _count_occurrences(content, old_string)
    if occurrences > 1:
        return False, (
            f"The edit will FAIL if `old_string` is not unique in the file ({occurrences} occurrences found). "
            "Either provide a larger string with more surrounding context to make it unique or use `replace_all` to change every instance of `old_string`."
        )
    
    return True, None

def _detect_potential_issues(old_string: str) -> list[str]:
    """Detect potential issues with the replacement."""
    issues = []
    
    if not old_string:
        return issues
        
    # Check for whitespace issues
    if old_string != old_string.strip():
        if old_string.startswith(' ') or old_string.startswith('\t'):
            issues.append("old_string starts with whitespace - ensure indentation matches exactly")
        if old_string.endswith(' ') or old_string.endswith('\t'):
            issues.append("old_string ends with whitespace - ensure trailing spaces match exactly")
    
    # Check for line ending issues
    if '\r' in old_string:
        issues.append("old_string contains carriage returns - line endings will be normalized to LF")
    
    return issues

def _get_file_type(path: Path) -> str:
    """Determine file type based on extension."""
    ext = path.suffix.lower()
    
    if ext in {'.py', '.js', '.ts', '.jsx', '.tsx', '.html', '.css', '.md', '.txt', '.json', '.xml', '.yaml', '.yml'}:
        return "text"
    elif ext in {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.svg', '.webp'}:
        return "image"
    elif ext in {'.pdf', '.doc', '.docx'}:
        return "document"
    else:
        return "unknown"

# -----------------------------------------------------------------------------
# Main implementation
# -----------------------------------------------------------------------------

def edit(
    file_path: str = Field(
        ...,
        description="The absolute path to the file to modify",
    ),
    old_string: str = Field(
        ...,
        description="The text to replace",
    ),
    new_string: str = Field(
        ...,
        description="The text to replace it with (must be different from old_string)",
    ),
    replace_all: bool = Field(
        False,
        description="Replace all occurrences of old_string (default: false - replaces only first occurrence).",
    ),
) -> Dict[str, Any]:
    """Performs exact string replacements in files. 

Usage:
- You must use your `Read` tool at least once in the conversation before editing. This tool will error if you attempt an edit without reading the file. 
- When editing text from Read tool output, ensure you preserve the exact indentation (tabs/spaces) as it appears AFTER the line number prefix. The line number prefix format is: spaces + line number + tab. Everything after that tab is the actual file content to match. Never include any part of the line number prefix in the old_string or new_string.
- ALWAYS prefer editing existing files in the codebase. NEVER write new files unless explicitly required.
- Only use emojis if the user explicitly requests it. Avoid adding emojis to files unless asked.
- The edit will FAIL if `old_string` is not unique in the file. Either provide a larger string with more surrounding context to make it unique or use `replace_all` to change every instance of `old_string`. 
- Use `replace_all` for replacing and renaming strings across the file. This parameter is useful if you want to rename a variable for instance."""

    # ------------------------------------------------------------------
    # Parameter validation and normalization
    # ------------------------------------------------------------------

    # Handle Pydantic FieldInfo objects when invoked programmatically
    if isinstance(file_path, FieldInfo):
        file_path = ""
    if isinstance(old_string, FieldInfo):
        old_string = ""
    if isinstance(new_string, FieldInfo):
        new_string = ""
    if isinstance(replace_all, FieldInfo):
        replace_all = False

    # Helper shortcuts for consistent results
    def _error(message: str, suggestion: str = None) -> Dict[str, Any]:
        error_msg = message
        if suggestion:
            error_msg += f" {suggestion}"
        return ToolResult(status="error", message=error_msg, error=message).model_dump()

    def _success(message: str, llm_content: Any, **data: Any) -> Dict[str, Any]:
        return ToolResult(
            status="success",
            message=message,
            llm_content=llm_content,
            data=data,
        ).model_dump()

    # Validate inputs
    if not file_path or not file_path.strip():
        return _error(
            "file_path is required and cannot be empty",
            "Provide a file path relative to workspace root, e.g., 'src/app.py'"
        )

    # Check if old_string and new_string are the same
    if old_string == new_string:
        return _error(
            "old_string and new_string must be different",
            "The replacement would have no effect. Provide different values for old_string and new_string."
        )

    if len(old_string) > MAX_OLD_STRING_LENGTH:
        return _error(
            f"old_string too long: {len(old_string)} chars (max: {MAX_OLD_STRING_LENGTH})",
            "Break down the replacement into smaller chunks or use write_file for large content changes"
        )

    if len(new_string) > MAX_NEW_STRING_LENGTH:
        return _error(
            f"new_string too long: {len(new_string)} chars (max: {MAX_NEW_STRING_LENGTH})",
            "Break down the replacement into smaller chunks or use write_file for large content changes"
        )

    # Validate workspace access
    if not validate_path_in_workspace("."):
        return _error(
            "Cannot access workspace directory",
            "Ensure you're running from within a valid workspace directory"
        )

    # Validate file path is within workspace
    validated_path = validate_path_in_workspace(file_path)
    if validated_path is None:
        return _error(
            f"File path is outside workspace: {file_path}",
            "Use paths relative to workspace root, e.g., 'src/app.py', 'config/settings.json'"
        )

    target_file = Path(validated_path)

    # Security checks for existing files
    if target_file.exists():
        if target_file.is_symlink() and not is_safe_symlink(target_file):
            return _error(
                f"Unsafe symlink detected: {file_path}",
                "Use a regular file path instead of a symlink pointing outside workspace"
            )

        if not check_parent_symlinks(target_file):
            return _error(
                f"Unsafe parent symlinks detected: {file_path}",
                "Use a file path without parent symlinks pointing outside workspace"
            )

    # ------------------------------------------------------------------
    # File validation and content analysis
    # ------------------------------------------------------------------

    try:
        # Validate file is suitable for editing
        can_edit, edit_error = _validate_file_for_editing(target_file)
        if not can_edit:
            return _error(edit_error)

        # Read current content or prepare for new file creation
        current_content = None
        is_new_file = False
        original_size = 0

        if target_file.exists():
            try:
                with target_file.open('r', encoding=TEXT_CHARSET_DEFAULT, errors='replace') as f:
                    current_content = f.read()
                current_content = _normalize_line_endings(current_content)
                original_size = len(current_content.encode(TEXT_CHARSET_DEFAULT))
            except Exception as e:
                return _error(
                    f"Cannot read file: {e}",
                    "Check file permissions and ensure the file is a readable text file"
                )
        else:
            # File doesn't exist
            if old_string == "":
                # Creating new file (Claude Edit tool pattern)
                is_new_file = True
                current_content = ""
                original_size = 0
            else:
                return _error(
                    "File not found. Use empty old_string to create a new file.",
                    "To create a new file, use old_string='' and provide the content in new_string"
                )

        # ------------------------------------------------------------------
        # Replacement logic and validation
        # ------------------------------------------------------------------

        if is_new_file:
            # Creating new file
            new_content = new_string
            replacements_made = 0
        else:
            # Editing existing file
            if old_string == "":
                return _error(
                    "Cannot use empty old_string with existing file.",
                    "To edit existing files, provide the exact text to replace in old_string. To overwrite the entire file, use write_file instead."
                )

            # Check if old_string exists
            occurrences = _count_occurrences(current_content, old_string)
            if occurrences == 0:
                # Provide helpful error message with context
                lines = current_content.split('\n')
                snippet = ""
                if len(lines) <= 10:
                    snippet = "\n\nFile content:\n" + current_content
                else:
                    # Show first and last 5 lines for context
                    first_lines = '\n'.join(lines[:5])
                    last_lines = '\n'.join(lines[-5:])
                    snippet = f"\n\nFile preview (first 5 lines):\n{first_lines}\n...\n(last 5 lines):\n{last_lines}"
                
                return _error(
                    "old_string not found in file",
                    f"Ensure old_string matches exactly including whitespace and indentation. Use read_file to examine the exact content.{snippet if len(snippet) < 500 else ''}"
                )

            # Validate uniqueness for single replacement
            unique_valid, unique_error = _validate_uniqueness(current_content, old_string, replace_all)
            if not unique_valid:
                return _error(unique_error)

            # Apply replacement based on replace_all flag
            if replace_all:
                new_content, replacements_made = _apply_all_replacements(
                    current_content, old_string, new_string
                )
            else:
                new_content, replacements_made = _apply_single_replacement(
                    current_content, old_string, new_string
                )

        # ------------------------------------------------------------------
        # Write file and generate results
        # ------------------------------------------------------------------

        # Ensure parent directories exist
        target_file.parent.mkdir(parents=True, exist_ok=True)

        # Write new content
        try:
            with target_file.open('w', encoding=TEXT_CHARSET_DEFAULT) as f:
                f.write(new_content)
        except Exception as e:
            return _error(
                f"Failed to write file: {e}",
                "Check file permissions and disk space, or try a different file path"
            )

        # Calculate file changes
        new_size = len(new_content.encode(TEXT_CHARSET_DEFAULT))
        size_change = new_size - original_size
        
        # Count line changes
        original_lines = (current_content or "").count('\n')
        new_lines = new_content.count('\n')
        line_change_count = new_lines - original_lines

        # Generate diff for display (if not a new file)
        diff_preview = ""
        has_diff = False
        if not is_new_file and current_content != new_content:
            diff_preview = _generate_diff(
                current_content or "", 
                new_content, 
                target_file.name
            )
            has_diff = True

        # Detect potential issues for warnings
        warnings = _detect_potential_issues(old_string)

        # Get file metadata
        file_type = _get_file_type(target_file)
        file_extension = target_file.suffix.lower()
        
        # ------------------------------------------------------------------
        # Build response structure aligned with Claude's Edit tool
        # ------------------------------------------------------------------

        # Current timestamp for operation tracking
        timestamp = datetime.now().isoformat()

        # Build structured LLM content
        llm_content = {
            "operation": {
                "type": "replace",
                "file_path": str(target_file.relative_to(WORKSPACE_ROOT)),
                "replacements_made": replacements_made,
                "replace_all": replace_all,
                "is_new_file": is_new_file,
                "timestamp": timestamp
            },
            "edit_result": {
                "success": True,
                "content_changed": is_new_file or (current_content != new_content),
                "size_change_bytes": size_change,
                "line_change_count": line_change_count
            },
            "file_info": {
                "size_bytes": new_size,
                "file_type": file_type,
                "extension": file_extension,
                "encoding": TEXT_CHARSET_DEFAULT
            },
            "diff_info": {
                "has_diff": has_diff,
                "diff_preview": diff_preview[:1000] + "..." if len(diff_preview) > 1000 else diff_preview,
                "diff_size": len(diff_preview)
            },
            "validation_info": {
                "string_lengths": {
                    "old": len(old_string),
                    "new": len(new_string)
                },
                "warnings": warnings
            },
            "summary": {
                "operation_type": "new_file_creation" if is_new_file else "text_replacement",
                "mode": "replace_all" if replace_all else "replace_first",
                "success": True
            }
        }

        # Add conditional sections based on operation type
        if not is_new_file:
            llm_content["diff_info"]["lines_added"] = max(0, line_change_count)
            llm_content["diff_info"]["lines_removed"] = max(0, -line_change_count)

        # Build user-facing message
        if is_new_file:
            message = f"✅ Created new file: {target_file.name} ({new_size} bytes)"
        else:
            mode_text = "all" if replace_all else "first"
            replacements_word = "occurrence" if replacements_made == 1 else "occurrences"
            size_info = f"{'+' if size_change >= 0 else ''}{size_change} bytes"
            message = f"✅ Successfully edited {target_file.name}: Replaced {mode_text} {replacements_made} {replacements_word} ({size_info})"

        # Additional data for backend/UI
        response_data = {
            "file_path": str(target_file),
            "relative_path": str(target_file.relative_to(WORKSPACE_ROOT)),
            "is_new_file": is_new_file,
            "replacements_made": replacements_made,
            "replace_all": replace_all,
            "size_change": size_change,
            "line_change_count": line_change_count,
            "diff_preview": diff_preview,
            "warnings": warnings,
        }

        return _success(
            message,
            llm_content,
            **response_data,
        )

    except Exception as exc:
        return _error(
            f"Unexpected error during file editing: {exc}",
            "Verify the file path is correct and the content is valid text"
        )

# -----------------------------------------------------------------------------
# Registration helper
# -----------------------------------------------------------------------------

def register_edit_tool(mcp: FastMCP):
    """Register the edit tool with proper tags synchronization."""
    common = dict(
        tags={"coding", "filesystem", "edit", "replace", "modify"}, 
        annotations={"category": "coding", "tags": ["coding", "filesystem", "edit", "replace", "modify"]}
    )
    mcp.tool(**common)(edit)