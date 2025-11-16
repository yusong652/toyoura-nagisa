"""
Shared file reading utilities for coding tools.

This module provides common file reading functionality used by:
- read.py: Interactive file reading tool
- file_mention_processor.py: File mention content injection
"""

from pathlib import Path
from typing import Optional


# Constants matching read.py
MAX_FILE_SIZE_BYTES = 50 * 1024 * 1024  # 50MB
DEFAULT_MAX_LINES = 2000
MAX_LINE_LENGTH = 2000
SAMPLE_SIZE_BINARY = 8192

ENCODING_CANDIDATES = [
    'utf-8', 'ascii', 'latin-1', 'cp1252', 'iso-8859-1', 'gbk', 'shift_jis'
]


def detect_encoding(file_path: Path) -> Optional[str]:
    """
    Detect file encoding with BOM detection.

    Args:
        file_path: Path to file

    Returns:
        Detected encoding or None
    """
    try:
        with file_path.open('rb') as f:
            raw_data = f.read(min(SAMPLE_SIZE_BINARY, file_path.stat().st_size))

        # Check for BOM
        if raw_data.startswith(b'\xef\xbb\xbf'):
            return 'utf-8-sig'
        elif raw_data.startswith(b'\xff\xfe') or raw_data.startswith(b'\xfe\xff'):
            return 'utf-16'

        # Try encodings in order
        for encoding in ENCODING_CANDIDATES:
            try:
                raw_data.decode(encoding)
                return encoding
            except UnicodeDecodeError:
                continue

        return None

    except Exception:
        return None


def read_text_file_with_line_numbers(
    file_path: Path,
    encoding: str,
    offset: Optional[int] = None,
    limit: Optional[int] = None
) -> str:
    """
    Read text file with Claude Code style line numbering.

    Format: "     1→content" (6-space padding + arrow separator)

    Args:
        file_path: Path to file
        encoding: Text encoding
        offset: Line number to start from (0-indexed)
        limit: Maximum number of lines to read

    Returns:
        Formatted content with line numbers
    """
    try:
        with file_path.open('r', encoding=encoding, errors='replace') as f:
            content = f.read()

        lines = content.splitlines()
        total_lines = len(lines)

        # Apply offset and limit
        start_line = offset or 0
        end_line = min(start_line + (limit or DEFAULT_MAX_LINES), total_lines) if limit else total_lines

        selected_lines = lines[start_line:end_line]

        # Format with line numbers (Claude Code format)
        processed_lines = []
        for i, line in enumerate(selected_lines, start=start_line + 1):
            # Truncate long lines
            if len(line) > MAX_LINE_LENGTH:
                line = line[:MAX_LINE_LENGTH] + "... [line truncated]"

            # Format: "     1→content"
            processed_lines.append(f"{i:6}→{line}")

        return '\n'.join(processed_lines)

    except Exception as e:
        return f"Error reading file: {e}"
