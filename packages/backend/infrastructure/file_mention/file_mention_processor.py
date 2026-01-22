"""
File Mention Processor - Extract and inject mentioned file contents.

This module processes @file mentions in user messages, reading files and
formatting them as system-reminder blocks for LLM consumption.

Supports:
- Text files: formatted with line numbers
- Binary/Image files: base64-encoded for multimodal LLM consumption
  (with graceful degradation for non-multimodal LLMs)
"""

import logging
import json
from pathlib import Path
from typing import List, Set, Optional, Dict, Any, Union
from dataclasses import dataclass

from backend.infrastructure.mcp.tools.coding.utils.path_security import (
    validate_path_in_workspace,
    is_safe_symlink,
    check_parent_symlinks
)
from backend.shared.utils.workspace import get_workspace_for_profile
from backend.infrastructure.mcp.utils.path_normalization import (
    normalize_path_separators,
    path_to_llm_format
)
from backend.infrastructure.mcp.tools.coding.utils.file_reader import (
    read_file_safely,
    ProcessingResult,
    ContentFormat,
    FileType,
    MAX_FILE_SIZE_BYTES,
    get_multimodal_support_for_session
)

logger = logging.getLogger(__name__)


@dataclass
class FileContent:
    """File content with metadata."""
    path: str
    processing_result: Optional[ProcessingResult]
    success: bool
    error_message: Optional[str] = None


class FileMentionProcessor:
    """
    Process file mentions in user messages.

    Responsibilities:
    - Deduplicate file paths (single message level)
    - Validate file paths against workspace
    - Read file contents safely (text and binary/multimodal)
    - Format as system-reminder blocks
    - Error handling (skip failed files)
    """

    def __init__(self, session_id: str, agent_profile = "pfc_expert"):
        """
        Initialize processor for a session.

        Args:
            session_id: Session ID for workspace resolution
            agent_profile: Agent profile for workspace determination (pfc_expert, disabled)
        """
        self.session_id = session_id
        self.agent_profile = agent_profile

    async def process_mentioned_files(
        self,
        file_paths: List[str]
    ) -> List[Union[str, Dict[str, Any]]]:
        """
        Process mentioned files and return system-reminder blocks.

        Args:
            file_paths: List of file paths (relative or absolute)

        Returns:
            List of formatted system-reminder blocks or structured multimodal parts
            (only successful reads)
        """
        if not file_paths:
            return []

        # Deduplicate (preserve order)
        unique_paths = self._deduplicate_paths(file_paths)

        # Read all files
        reminders = []
        for file_path in unique_paths:
            file_content = await self._read_file_safe(file_path)

            if file_content.success and file_content.processing_result:
                # Format reminder for LLM injection
                reminder = self._format_file_reminder(file_content)
                reminders.append(reminder)

                # Track read file in tool_manager (for edit prerequisite validation)
                try:
                    from backend.infrastructure.llm.session_client import get_session_llm_client
                    
                    llm_client = get_session_llm_client(self.session_id)
                    llm_client.tool_manager._track_read_file(self.session_id, file_content.path)
                        
                except Exception as e:
                    # Non-critical: Log warning but don't block file injection
                    logger.warning(f"Failed to track read file '{file_path}': {e}")
            else:
                # Skip failed files (just log, don't inject)
                logger.warning(
                    f"Failed to read mentioned file '{file_path}': {file_content.error_message}"
                )

        return reminders

    def _deduplicate_paths(self, file_paths: List[str]) -> List[str]:
        """
        Deduplicate file paths while preserving order.

        Args:
            file_paths: List of file paths

        Returns:
            Deduplicated list in original order
        """
        import os
        seen: Set[str] = set()
        unique = []

        for path in file_paths:
            # Normalize for comparison (handle ./, ../, etc.)
            normalized = normalize_path_separators(path.strip())
            # Use os.path.normpath to resolve ./ and ../ patterns
            canonical = os.path.normpath(normalized)

            if canonical and canonical not in seen:
                seen.add(canonical)
                unique.append(canonical)

        return unique

    async def _read_file_safe(self, file_path: str) -> FileContent:
        """
        Safely read file with validation and error handling.

        Args:
            file_path: File path (relative to workspace)

        Returns:
            FileContent object with success status and absolute path
        """
        try:
            # Normalize path
            normalized_path = normalize_path_separators(file_path.strip())

            # Get workspace root based on agent profile
            workspace_root = await get_workspace_for_profile(self.agent_profile, self.session_id)

            # Validate path and get absolute path
            abs_file_path = validate_path_in_workspace(normalized_path, workspace_root)
            if abs_file_path is None:
                return FileContent(
                    path=file_path,
                    processing_result=None,
                    success=False,
                    error_message=f"Path outside workspace: {file_path}"
                )

            file_path_obj = Path(abs_file_path)

            # Format absolute path for LLM (matches Claude Code)
            abs_display = path_to_llm_format(file_path_obj)

            # Check existence
            if not file_path_obj.exists():
                return FileContent(
                    path=abs_display,
                    processing_result=None,
                    success=False,
                    error_message=f"File not found: {abs_display}"
                )

            # Check it's a file
            if not file_path_obj.is_file():
                return FileContent(
                    path=abs_display,
                    processing_result=None,
                    success=False,
                    error_message=f"Not a file: {abs_display}"
                )

            # Check size
            file_size = file_path_obj.stat().st_size
            if file_size > MAX_FILE_SIZE_BYTES:
                return FileContent(
                    path=abs_display,
                    processing_result=None,
                    success=False,
                    error_message=f"File too large: {file_size // 1024 // 1024}MB"
                )

            # Security checks
            if file_path_obj.is_symlink() and not is_safe_symlink(file_path_obj, workspace_root):
                return FileContent(
                    path=abs_display,
                    processing_result=None,
                    success=False,
                    error_message="Unsafe symlink"
                )

            if not check_parent_symlinks(file_path_obj, workspace_root):
                return FileContent(
                    path=abs_display,
                    processing_result=None,
                    success=False,
                    error_message="Unsafe parent symlinks"
                )

            # Read content with automatic type detection (text vs binary/image)
            processing_result = read_file_safely(file_path_obj)

            return FileContent(
                path=abs_display,  # Return absolute path
                processing_result=processing_result,
                success=True
            )

        except Exception as e:
            logger.error(f"Unexpected error reading file '{file_path}': {e}")
            return FileContent(
                path=file_path,
                processing_result=None,
                success=False,
                error_message=f"Unexpected error: {str(e)}"
            )

    def _format_file_reminder(self, file_content: FileContent) -> Union[str, Dict[str, Any]]:
        """
        Format file content as system-reminder block or multimodal part.

        For text files:
        - Returns string with two system-reminder blocks (tool call + result)

        For binary/image files:
        - Returns dict with multimodal parts structure for LLM APIs

        Args:
            file_content: FileContent object

        Returns:
            Formatted system-reminder string or multimodal parts dict
        """
        if not file_content.processing_result:
            return ""

        result = file_content.processing_result

        # First reminder: tool call record (always included)
        tool_call_reminder = (
            f"<system-reminder>\n"
            f"Called the Read tool with the following input: "
            f'{{"file_path":"{file_content.path}"}}\n'
            f"</system-reminder>"
        )

        # Handle different content formats
        if result.content_format == ContentFormat.METADATA:
            # Validation errors (empty file, invalid image, etc.)
            # Return as warning in system-reminder format
            warning_msg = result.content if isinstance(result.content, str) else str(result.content)
            warning_reminder = (
                f"{tool_call_reminder}\n\n"
                f"<system-reminder>\n"
                f"Result of calling the Read tool:\n"
                f"Warning: {warning_msg}\n"
                f"</system-reminder>"
            )
            logger.warning(f"File validation warning for {file_content.path}: {warning_msg}")
            return warning_reminder

        if result.content_format == ContentFormat.INLINE_DATA:
            # Binary/Image files: check multimodal support
            if isinstance(result.content, dict) and "inline_data" in result.content:
                inline_data = result.content["inline_data"]

                # Check if current LLM provider supports multimodal
                supports_multimodal = get_multimodal_support_for_session(self.session_id)

                if not supports_multimodal:
                    # Graceful degradation: return simple text message for LLM
                    file_type = result.file_type.value if result.file_type else "binary"
                    file_size_kb = result.original_size / 1024

                    # Simple message for LLM (no backend implementation details)
                    fallback_message = (
                        f"{tool_call_reminder}\n\n"
                        f"<system-reminder>\n"
                        f"Result of calling the Read tool:\n"
                        f"Cannot read {file_type} file: {file_content.path}\n"
                        f"File type: {inline_data.get('mime_type', 'unknown')}\n"
                        f"File size: {file_size_kb:.2f} KB\n\n"
                        f"User attempted to mention a {file_type} file, but multimodal content is not supported.\n"
                        f"Only text files can be read.\n"
                        f"</system-reminder>"
                    )

                    logger.info(f"Multimodal not supported - returning text fallback for {file_content.path}")
                    return fallback_message

                # Multimodal supported: return structured parts
                combined_text = (
                    f"{tool_call_reminder}\n\n"
                    f"<system-reminder>\n"
                    f"Result of calling the Read tool:\n"
                    f"</system-reminder>"
                )

                parts = [
                    {
                        "type": "text",
                        "text": combined_text
                    },
                    {
                        "inline_data": inline_data  # Direct inline_data format for LLM APIs
                    }
                ]

                # Return structured format that will be properly injected
                return {
                    "type": "multimodal_file_mention",
                    "parts": parts
                }

        # Text files or metadata: return standard system-reminder format
        # Second reminder: file content
        content_str = result.content if isinstance(result.content, str) else str(result.content)

        # Escape double quotes in content for JSON embedding
        escaped_content = content_str.replace('\\', '\\\\').replace('"', '\\"')

        content_reminder = (
            f"<system-reminder>\n"
            f'Result of calling the Read tool: "{escaped_content}"\n'
            f"</system-reminder>"
        )

        # Combine both reminders
        return f"{tool_call_reminder}\n\n{content_reminder}"
