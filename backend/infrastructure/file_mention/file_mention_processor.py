"""
File Mention Processor - Extract and inject mentioned file contents.

This module processes @file mentions in user messages, reading files and
formatting them as system-reminder blocks for LLM consumption.
"""

import logging
from pathlib import Path
from typing import List, Set, Optional
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
    detect_encoding,
    read_text_file_with_line_numbers,
    MAX_FILE_SIZE_BYTES
)

logger = logging.getLogger(__name__)


@dataclass
class FileContent:
    """File content with metadata."""
    path: str
    content: str
    total_lines: int
    encoding: str
    success: bool
    error_message: Optional[str] = None


class FileMentionProcessor:
    """
    Process file mentions in user messages.

    Responsibilities:
    - Deduplicate file paths (single message level)
    - Validate file paths against workspace
    - Read file contents safely
    - Format as system-reminder blocks
    - Error handling (skip failed files)
    """

    def __init__(self, session_id: str, agent_profile: str = "general"):
        """
        Initialize processor for a session.

        Args:
            session_id: Session ID for workspace resolution
            agent_profile: Agent profile for workspace determination (general, pfc, coding, etc.)
        """
        self.session_id = session_id
        self.agent_profile = agent_profile

    async def process_mentioned_files(
        self,
        file_paths: List[str]
    ) -> List[str]:
        """
        Process mentioned files and return system-reminder blocks.

        Args:
            file_paths: List of file paths (relative or absolute)

        Returns:
            List of formatted system-reminder blocks (only successful reads)
        """
        if not file_paths:
            return []

        # Deduplicate (preserve order)
        unique_paths = self._deduplicate_paths(file_paths)
        logger.info(f"Processing {len(unique_paths)} unique file mentions (from {len(file_paths)} total)")

        # Read all files
        reminders = []
        for file_path in unique_paths:
            file_content = await self._read_file_safe(file_path)

            if file_content.success:
                reminder = self._format_file_reminder(file_content)
                reminders.append(reminder)
                logger.info(f"Successfully read mentioned file: {file_path}")
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
            # For PFC profile: tries PFC server's working directory first, falls back to pfc_workspace
            # For other profiles: uses unified workspace directory
            workspace_root = await get_workspace_for_profile(self.agent_profile, self.session_id)

            # Validate path and get absolute path
            abs_file_path = validate_path_in_workspace(normalized_path, workspace_root)
            if abs_file_path is None:
                return FileContent(
                    path=file_path,  # Keep original for error message
                    content="",
                    total_lines=0,
                    encoding="",
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
                    content="",
                    total_lines=0,
                    encoding="",
                    success=False,
                    error_message=f"File not found: {abs_display}"
                )

            # Check it's a file
            if not file_path_obj.is_file():
                return FileContent(
                    path=abs_display,
                    content="",
                    total_lines=0,
                    encoding="",
                    success=False,
                    error_message=f"Not a file: {abs_display}"
                )

            # Check size
            file_size = file_path_obj.stat().st_size
            if file_size > MAX_FILE_SIZE_BYTES:
                return FileContent(
                    path=abs_display,
                    content="",
                    total_lines=0,
                    encoding="",
                    success=False,
                    error_message=f"File too large: {file_size // 1024 // 1024}MB"
                )

            # Security checks
            if file_path_obj.is_symlink() and not is_safe_symlink(file_path_obj, workspace_root):
                return FileContent(
                    path=abs_display,
                    content="",
                    total_lines=0,
                    encoding="",
                    success=False,
                    error_message="Unsafe symlink"
                )

            if not check_parent_symlinks(file_path_obj, workspace_root):
                return FileContent(
                    path=abs_display,
                    content="",
                    total_lines=0,
                    encoding="",
                    success=False,
                    error_message="Unsafe parent symlinks"
                )

            # Detect encoding (use shared utility)
            encoding = detect_encoding(file_path_obj)
            if encoding is None:
                encoding = 'utf-8'  # Fallback

            # Read content with line numbers (use shared utility)
            content = read_text_file_with_line_numbers(file_path_obj, encoding)

            return FileContent(
                path=abs_display,  # Return absolute path
                content=content,
                total_lines=len(content.splitlines()),
                encoding=encoding,
                success=True
            )

        except Exception as e:
            logger.error(f"Unexpected error reading file '{file_path}': {e}")
            return FileContent(
                path=file_path,
                content="",
                total_lines=0,
                encoding="",
                success=False,
                error_message=f"Unexpected error: {str(e)}"
            )

    def _format_file_reminder(self, file_content: FileContent) -> str:
        """
        Format file content as system-reminder block.

        Matches Claude Code format:
        <system-reminder>
        Called the Read tool with the following input: {"file_path":"..."}
        </system-reminder>

        <system-reminder>
        Result of calling the Read tool: "...file content..."
        </system-reminder>

        Args:
            file_content: FileContent object

        Returns:
            Formatted system-reminder block
        """
        # First reminder: tool call record
        tool_call_reminder = (
            f"<system-reminder>\n"
            f"Called the Read tool with the following input: "
            f'{{\"file_path\":\"{file_content.path}\"}}\n'
            f"</system-reminder>"
        )

        # Second reminder: file content
        content_reminder = (
            f"<system-reminder>\n"
            f"Result of calling the Read tool: \"{file_content.content}\"\n"
            f"</system-reminder>"
        )

        # Combine both reminders
        return f"{tool_call_reminder}\n\n{content_reminder}"
