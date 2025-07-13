"""replace tool – precise text replacement within files with intelligent error handling.

This tool provides atomic file editing functionality, focusing exclusively on 
replacing specific text content within files. It does NOT list files or read 
entire contents - use glob for file discovery and read_file for content examination.

Modeled after gemini-cli's replace tool for consistency and interoperability.
"""

from pathlib import Path
from typing import Dict, Any, Optional, Tuple
import re
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
from backend.nagisa_mcp.utils.tool_result import ToolResult
from .constants import (
    MAX_FILE_SIZE_FOR_EDIT,
    TEXT_CHARSET_DEFAULT,
)

__all__ = ["replace", "register_replace_tool"]

# -----------------------------------------------------------------------------
# Constants specific to file editing
# -----------------------------------------------------------------------------

MAX_EDIT_FILE_SIZE = 5 * 1024 * 1024  # 5MB max file size for editing
MAX_OLD_STRING_LENGTH = 50000  # Maximum length of old_string parameter
MAX_NEW_STRING_LENGTH = 50000  # Maximum length of new_string parameter
MAX_EXPECTED_REPLACEMENTS = 1000  # Maximum number of replacements allowed

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

def _apply_replacement(content: str, old_string: str, new_string: str) -> str:
    """Apply replacement of old_string with new_string in content."""
    if not old_string:
        return content
    return content.replace(old_string, new_string)

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

def _validate_context_requirement(content: str, old_string: str, expected_replacements: int) -> Tuple[bool, Optional[str]]:
    """Validate that old_string has sufficient context for single replacements."""
    if expected_replacements != 1:
        return True, None  # Context validation only for single replacements
        
    if not old_string:
        return True, None  # Empty string is valid for file creation
        
    lines = old_string.split('\n')
    if len(lines) < MIN_CONTEXT_LINES * 2 + 1:  # Before + target + after
        return False, f"For single replacements, old_string should include at least {MIN_CONTEXT_LINES} lines of context before and after the target text"
    
    return True, None

def _detect_potential_issues(content: str, old_string: str) -> list[str]:
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

def replace(
    file_path: str = Field(
        ...,
        description="Absolute path to the file to modify. Must be within workspace.",
    ),
    old_string: str = Field(
        ...,
        description="Exact text to replace. For single replacements, include 3+ lines of context before/after target. Must match exactly including whitespace.",
    ),
    new_string: str = Field(
        ...,
        description="Exact replacement text. Provide precise text with correct whitespace and formatting.",
    ),
    expected_replacements: int = Field(
        1,
        ge=1,
        le=MAX_EXPECTED_REPLACEMENTS,
        description="Expected number of replacements. Tool fails if actual count differs.",
    ),
) -> Dict[str, Any]:
    """Replace exact text within files with precise targeting and comprehensive validation.

    ## Core Functionality
    - Replaces specific text content using exact string matching
    - Supports single and multiple occurrence replacements
    - Creates new files when old_string is empty
    - Provides detailed diff and validation feedback

    ## Strategic Usage
    - **Always use read_file first** to examine content before editing
    - Include sufficient context (3+ lines) for single replacements
    - Use exact literal text - match whitespace/indentation precisely
    - Verify paths are absolute and within workspace

    ## Return Value
    **For LLM:** Returns structured editing results with comprehensive metadata.
    
    **Structure:**
    ```json
    {
      "operation": {
        "type": "replace",
        "file_path": "/workspace/src/main.py",
        "replacements_made": 1,
        "expected_replacements": 1,
        "is_new_file": false,
        "timestamp": "2025-01-08T10:30:00.123"
      },
      "edit_result": {
        "success": true,
        "content_changed": true,
        "size_change_bytes": 12,
        "line_change_count": 2
      },
      "file_info": {
        "size_bytes": 1024,
        "file_type": "text",
        "extension": ".py",
        "encoding": "utf-8"
      },
      "diff_info": {
        "has_diff": true,
        "diff_preview": "--- original\\n+++ modified\\n@@ -1,3 +1,3 @@\\n...",
        "diff_size": 156
      },
      "validation_info": {
        "context_validated": true,
        "string_lengths": {"old": 156, "new": 168},
        "warnings": [],
        "issues_detected": []
      },
      "summary": {
        "operation_type": "text_replacement",
        "success": true
      }
    }
    ```

    ## Examples
    ```python
    # Single replacement with context
    replace(
        file_path="/workspace/src/main.py",
        old_string="def old_function():\\n    return 'old'\\n\\ndef another_function():",
        new_string="def new_function():\\n    return 'new'\\n\\ndef another_function():"
    )
    
    # Multiple replacements
    replace(
        file_path="/workspace/config.py",
        old_string="DEBUG = True",
        new_string="DEBUG = False",
        expected_replacements=3
    )
    ```

    ## Critical Requirements
    1. **file_path** must be absolute and within workspace
    2. **old_string** must match exactly (whitespace, indentation, newlines)
    3. **new_string** must be exact replacement text
    4. **expected_replacements** must match actual occurrence count
    5. Use empty old_string only for new file creation
    """

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
    if isinstance(expected_replacements, FieldInfo):
        expected_replacements = 1

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
    if not file_path or not file_path.strip():
        return _error("file_path is required and cannot be empty")

    if not Path(file_path).is_absolute():
        return _error(f"file_path must be absolute: {file_path}")

    if len(old_string) > MAX_OLD_STRING_LENGTH:
        return _error(f"old_string too long: {len(old_string)} chars (max: {MAX_OLD_STRING_LENGTH})")

    if len(new_string) > MAX_NEW_STRING_LENGTH:
        return _error(f"new_string too long: {len(new_string)} chars (max: {MAX_NEW_STRING_LENGTH})")

    if expected_replacements < 1 or expected_replacements > MAX_EXPECTED_REPLACEMENTS:
        return _error(f"expected_replacements must be between 1 and {MAX_EXPECTED_REPLACEMENTS}")

    # Validate workspace access
    if not validate_path_in_workspace("."):
        return _error("Cannot access workspace directory")

    # Validate file path is within workspace
    validated_path = validate_path_in_workspace(file_path)
    if validated_path is None:
        return _error(f"File path is outside workspace: {file_path}")

    target_file = Path(validated_path)

    # Security checks for existing files
    if target_file.exists():
        if target_file.is_symlink() and not is_safe_symlink(target_file):
            return _error(f"Unsafe symlink detected: {file_path}")

        if not check_parent_symlinks(target_file):
            return _error(f"Unsafe parent symlinks detected: {file_path}")

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
                return _error(f"Cannot read file: {e}")
        else:
            # File doesn't exist
            if old_string == "":
                # Creating new file
                is_new_file = True
                current_content = ""
                original_size = 0
            else:
                return _error("File not found. Use empty old_string to create a new file.")

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
                return _error("Cannot use empty old_string with existing file. Use non-empty old_string or delete the file first.")

            # Count occurrences
            actual_occurrences = _count_occurrences(current_content, old_string)

            if actual_occurrences == 0:
                return _error(
                    f"Failed to edit: old_string not found in file. "
                    f"Ensure exact match including whitespace, indentation, and context. "
                    f"Use read_file tool to verify current content."
                )

            if actual_occurrences != expected_replacements:
                return _error(
                    f"Failed to edit: expected {expected_replacements} occurrences "
                    f"but found {actual_occurrences}. "
                    f"Adjust expected_replacements or refine old_string for precise targeting."
                )

            # Validate context requirements for single replacements
            context_valid, context_error = _validate_context_requirement(
                current_content, old_string, expected_replacements
            )
            if not context_valid:
                return _error(context_error)

            # Apply replacement
            new_content = _apply_replacement(current_content, old_string, new_string)
            replacements_made = actual_occurrences

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
            return _error(f"Failed to write file: {e}")

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
        warnings = _detect_potential_issues(current_content or "", old_string)

        # Get file metadata
        file_type = _get_file_type(target_file)
        file_extension = target_file.suffix.lower()
        
        # ------------------------------------------------------------------
        # Build SOTA-level response structure (consistent with other tools)
        # ------------------------------------------------------------------

        # Current timestamp for operation tracking
        timestamp = datetime.now().isoformat()

        # Build structured LLM content matching other tools' patterns
        llm_content = {
            "operation": {
                "type": "replace",
                "file_path": str(target_file.relative_to(WORKSPACE_ROOT)),
                "replacements_made": replacements_made,
                "expected_replacements": expected_replacements,
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
                "context_validated": expected_replacements == 1,
                "string_lengths": {
                    "old": len(old_string),
                    "new": len(new_string)
                },
                "warnings": warnings,
                "issues_detected": []
            },
            "summary": {
                "operation_type": "new_file_creation" if is_new_file else "text_replacement",
                "success": True
            }
        }

        # Add conditional sections based on operation type
        if not is_new_file:
            llm_content["diff_info"]["lines_added"] = max(0, line_change_count)
            llm_content["diff_info"]["lines_removed"] = max(0, -line_change_count)

        # Build user-facing message
        if is_new_file:
            message = f"Created new file: {target_file.name} ({new_size} bytes)"
        else:
            replacements_word = "replacement" if replacements_made == 1 else "replacements"
            size_info = f"{'+' if size_change >= 0 else ''}{size_change} bytes"
            message = f"Successfully modified {target_file.name}: {replacements_made} {replacements_word} made ({size_info})"

        # Additional data for backend/UI
        response_data = {
            "file_path": str(target_file),
            "relative_path": str(target_file.relative_to(WORKSPACE_ROOT)),
            "is_new_file": is_new_file,
            "replacements_made": replacements_made,
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
        return _error(f"Unexpected error during file editing: {exc}")

# -----------------------------------------------------------------------------
# Registration helper
# -----------------------------------------------------------------------------

def register_replace_tool(mcp: FastMCP):
    """Register the replace tool with proper tags synchronization."""
    common = dict(
        tags={"coding", "filesystem", "edit", "replace", "modify"}, 
        annotations={"category": "coding", "tags": ["coding", "filesystem", "edit", "replace", "modify"]}
    )
    mcp.tool(**common)(replace) 