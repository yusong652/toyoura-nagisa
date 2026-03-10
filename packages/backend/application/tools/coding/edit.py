"""edit tool – precise text replacement within files with intelligent error handling.

This tool provides atomic file editing functionality, focusing exclusively on 
replacing specific text content within files. It does NOT list files or read 
entire contents - use glob for file discovery and read_file for content examination.

Fully aligned with Claude's Edit tool for consistency and improved usability.
"""

from pathlib import Path
from typing import Dict, Any, Optional, Tuple

from pydantic import Field
from backend.application.tools.registrar import ToolRegistrar
from backend.application.tools.context import ToolContext
# from fastmcp.server.context import Context  # type: ignore

from .utils.path_security import (
    validate_path_in_workspace,
    get_workspace_root_async,
)
from backend.shared.utils.tool_result import success_response, error_response
from backend.shared.utils.path_normalization import normalize_path_separators, path_to_llm_format
from .utils.constants import (
    TEXT_CHARSET_DEFAULT,
)

__all__ = ["edit", "register_edit_tool"]

# -----------------------------------------------------------------------------
# Constants specific to file editing
# -----------------------------------------------------------------------------

MAX_EDIT_FILE_SIZE = 5 * 1024 * 1024  # 5MB max file size for editing
MAX_OLD_STRING_LENGTH = 50000  # Maximum length of old_string parameter
MAX_NEW_STRING_LENGTH = 50000  # Maximum length of new_string parameter


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


def _validate_uniqueness(content: str, old_string: str, replace_all: bool) -> Tuple[bool, Optional[str]]:
    """Validate that old_string is unique when replace_all is False."""
    if replace_all or not old_string:
        return True, None
    
    occurrences = _count_occurrences(content, old_string)
    if occurrences > 1:
        return False, (
            f"Found {occurrences} matches of the string to replace, but replace_all is false. "
            f"To replace all occurrences, set replace_all to true. To replace only one occurrence, please provide more context to uniquely identify the instance.\n"
            f"String: {old_string[:200]}{'...' if len(old_string) > 200 else ''}"
        )
    
    return True, None


# -----------------------------------------------------------------------------
# Main implementation
# -----------------------------------------------------------------------------

async def edit(
    context: ToolContext,
    path: str = Field(
        ...,
        min_length=1,
        description="Path to the file to modify. Relative paths resolve from the workspace root.",
    ),
    old_string: str = Field(
        ...,
        description="Text to replace.",
    ),
    new_string: str = Field(
        ...,
        description="Replacement text. Must differ from old_string.",
    ),
    replace_all: bool = Field(
        False,
        description="Replace all occurrences instead of only the first unique match.",
    ),
) -> Dict[str, Any]:
    """Performs exact string replacements in files.

Usage:
- You must use your `Read` tool at least once in the conversation before editing. This tool will error if you attempt an edit without reading the file.
- Relative paths are resolved from the workspace root.
- When editing text from Read tool output, ensure you preserve the exact indentation (tabs/spaces) as it appears AFTER the line number prefix. The line number prefix format is: spaces + line number + arrow (→). Everything after that arrow is the actual file content to match. Never include any part of the line number prefix in the old_string or new_string.
- IMPORTANT: When you see Read tool output like "     5→while i < 35:", the old_string should be "while i < 35:" (WITHOUT the "     5→" prefix). The line numbers and arrows are for reference only and are NOT part of the file content.
- ALWAYS prefer editing existing files in the codebase. NEVER write new files unless explicitly required.
- Only use emojis if the user explicitly requests it. Avoid adding emojis to files unless asked.
- The edit will FAIL if `old_string` is not unique in the file. Either provide a larger string with more surrounding context to make it unique or use `replace_all` to change every instance of `old_string`.
- Use `replace_all` for replacing and renaming strings across the file. This parameter is useful if you want to rename a variable for instance.

PFC Script Guidelines (when editing .py files for PFC simulations):
- Add print() statements for progress monitoring (visible via pfc_check_task_status)
- Use itasca.command("model save 'name'") for checkpoint persistence
- Export data to CSV/JSON files for post-analysis (write analysis scripts to process, don't read CSV directly)"""

    # ------------------------------------------------------------------
    # Parameter validation and normalization
    # ------------------------------------------------------------------

    # path is pre-validated by Pydantic (min_length=1)

    # Normalize path separators for cross-platform compatibility
    # This handles cases where LLM generates mixed separators (e.g., C:\path/to/file)
    # Keep original path for LLM-friendly error messages (forward slashes)
    original_path_for_display = path_to_llm_format(path.strip())
    path = normalize_path_separators(path.strip())

    # Check if old_string and new_string are the same
    if old_string == new_string:
        return error_response("old_string and new_string must be different")

    if len(old_string) > MAX_OLD_STRING_LENGTH:
        return error_response(f"old_string too long: {len(old_string)} chars (max: {MAX_OLD_STRING_LENGTH})")

    if len(new_string) > MAX_NEW_STRING_LENGTH:
        return error_response(f"new_string too long: {len(new_string)} chars (max: {MAX_NEW_STRING_LENGTH})")

    # Get workspace root dynamically based on current session
    workspace_root = await get_workspace_root_async(context)

    # Validate file path is within workspace
    validated_path = validate_path_in_workspace(path, workspace_root)
    if validated_path is None:
        return error_response(f"File path is outside workspace: {original_path_for_display}")

    target_file = Path(validated_path)

    # ------------------------------------------------------------------
    # File validation and content analysis
    # ------------------------------------------------------------------

    try:
        # Validate file is suitable for editing
        can_edit, edit_error = _validate_file_for_editing(target_file)
        if not can_edit:
            return error_response(edit_error or "File validation failed")

        # Read current file content
        if not target_file.exists():
            return error_response(f"File not found: {path}")

        try:
            with target_file.open('r', encoding=TEXT_CHARSET_DEFAULT, errors='replace') as f:
                current_content = f.read()
            current_content = _normalize_line_endings(current_content)
        except Exception as e:
            return error_response(f"Cannot read file: {e}")

        # ------------------------------------------------------------------
        # Replacement logic and validation
        # ------------------------------------------------------------------

        # Validate old_string is not empty
        if old_string == "":
            return error_response("old_string cannot be empty for file editing")

        # Check if old_string accidentally includes line number prefix
        import re
        line_prefix_pattern = r'^\s+\d+→'
        if re.match(line_prefix_pattern, old_string):
            # Extract the actual content after the arrow
            actual_content = re.sub(r'^\s+\d+→', '', old_string)
            return error_response(
                f"The old_string appears to include the line number prefix from Read tool output.\n"
                f"Line numbers and arrows (→) are for reference only and should NOT be included in old_string.\n"
                f"You provided: {old_string[:100]}\n"
                f"You should use: {actual_content[:100]}\n"
                f"Please retry with only the actual file content (text after the arrow)."
            )

        # Check if old_string exists
        occurrences = _count_occurrences(current_content, old_string)
        if occurrences == 0:
            error_msg = f"String to replace not found in file.\nString: {old_string[:200]}{'...' if len(old_string) > 200 else ''}"
            return error_response(error_msg)

        # Validate uniqueness for single replacement
        unique_valid, unique_error = _validate_uniqueness(current_content, old_string, replace_all)
        if not unique_valid:
            return error_response(unique_error or "String uniqueness validation failed")

        # Apply replacement based on replace_all flag
        if replace_all:
            new_content, _ = _apply_all_replacements(
                current_content, old_string, new_string
            )
        else:
            new_content, _ = _apply_single_replacement(
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
            return error_response(f"Failed to write file: {e}")


        # ------------------------------------------------------------------
        # Build response with diff information
        # ------------------------------------------------------------------

        # Use absolute path with forward slashes for LLM consistency
        abs_path = path_to_llm_format(target_file)
        message = f"The file {abs_path} has been updated."

        # Generate unified diff using full file content for correct line numbers
        import difflib
        file_name = target_file.name
        diff_lines = list(difflib.unified_diff(
            current_content.splitlines(),
            new_content.splitlines(),
            fromfile=f"a/{file_name}",
            tofile=f"b/{file_name}",
            n=3,  # Context lines
            lineterm=''
        ))
        diff_content = '\n'.join(diff_lines) if diff_lines else ''

        # Count additions and deletions
        additions = sum(1 for line in diff_lines if line.startswith('+') and not line.startswith('+++'))
        deletions = sum(1 for line in diff_lines if line.startswith('-') and not line.startswith('---'))

        return success_response(
            message,
            llm_content={
                "parts": [
                    {"type": "text", "text": message}
                ]
            },
            # Include diff info in data for CLI display
            diff={
                "content": diff_content,
                "additions": additions,
                "deletions": deletions,
                "file_path": abs_path,
            }
        )

    except Exception as exc:
        return error_response(f"Unexpected error during file editing: {exc}")

# -----------------------------------------------------------------------------
# Registration helper
# -----------------------------------------------------------------------------

def register_edit_tool(registrar: ToolRegistrar):
    """Register the edit tool with proper tags synchronization."""

    registrar.tool(
        tags={"coding", "filesystem", "edit", "replace", "modify"}, 
        annotations={"category": "coding", "tags": ["coding", "filesystem", "edit", "replace", "modify"]}
    )(edit)
