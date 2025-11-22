"""Cross-platform path normalization utilities.

This module provides utilities to normalize paths for cross-platform compatibility,
particularly handling mixed path separators that can occur when LLMs generate
commands containing paths.
"""

import re
import sys
from typing import Optional


def normalize_windows_paths(command: str) -> str:
    """
    Normalize mixed path separators in Windows commands.

    Converts paths like 'C:\\Dev\\Han\\aiNagisa/pfc_workspace/file.py'
    to 'C:\\Dev\\Han\\aiNagisa\\pfc_workspace\\file.py' for Windows compatibility.

    This handles cases where LLMs generate commands with mixed separators,
    which cause errors in Windows cmd.exe and PowerShell.

    Args:
        command: Shell command potentially containing mixed path separators

    Returns:
        Command with normalized Windows-style backslash separators

    Example:
        >>> normalize_windows_paths("del C:\\path/to/file.py")
        'del C:\\path\\to\\file.py'  # On Windows

        >>> normalize_windows_paths("del C:\\path/to/file.py")
        'del C:\\path/to/file.py'  # On non-Windows (unchanged)
    """
    if sys.platform != 'win32':
        return command  # Only normalize on Windows

    # Pattern matches Windows absolute paths (with drive letter)
    # Example: C:\path/to/file or C:/path\to\file
    # We look for: drive_letter:\ or drive_letter:/ followed by path segments
    pattern = r'([A-Za-z]:)[/\\]([^"\'\s;|&<>]+)'

    def replace_path(match):
        drive = match.group(1)  # e.g., "C:"
        path_part = match.group(2)  # e.g., "Dev\Han\aiNagisa/pfc_workspace/file.py"
        # Replace all forward slashes with backslashes
        normalized_path = path_part.replace('/', '\\')
        return f"{drive}\\{normalized_path}"

    # Replace all matched paths
    normalized_command = re.sub(pattern, replace_path, command)
    return normalized_command


def normalize_path_separators(path: str, target_platform: Optional[str] = None) -> str:
    """
    Normalize path separators for a specific platform.

    Args:
        path: Path string to normalize
        target_platform: Target platform ('win32', 'linux', 'darwin').
                        If None, uses current platform (sys.platform)

    Returns:
        Path with normalized separators for the target platform

    Example:
        >>> normalize_path_separators("C:/path/to/file", "win32")
        'C:\\path\\to\\file'

        >>> normalize_path_separators("C:\\path\\to\\file", "linux")
        'C:/path/to/file'
    """
    platform = target_platform or sys.platform

    if platform == 'win32':
        # Windows: use backslashes
        return path.replace('/', '\\')
    else:
        # Unix-like (Linux, macOS): use forward slashes
        return path.replace('\\', '/')


def path_to_llm_format(path: 'Path | str') -> str:
    """
    Convert a path to LLM-friendly format (forward slashes).

    This ensures all paths shown to the LLM use consistent forward slash format,
    regardless of the underlying platform.

    Args:
        path: Path object or string to format

    Returns:
        Path string with forward slashes

    Example:
        >>> from pathlib import Path
        >>> path_to_llm_format(Path("C:\\Users\\test\\file.txt"))
        'C:/Users/test/file.txt'
    """
    # Import Path here to avoid circular imports
    from pathlib import Path

    # Convert to string if it's a Path object
    path_str = str(path)

    # Normalize to forward slashes for LLM consistency
    return normalize_path_separators(path_str, target_platform='linux')


def normalize_output_paths_to_llm_format(output: str) -> str:
    """
    Normalize Windows-style paths in command output to LLM-friendly format.

    Converts paths like 'C:\\Users\\test\\file.txt' to 'C:/Users/test/file.txt'
    in command output, making them consistent and easier for LLMs to process.

    This is the inverse of normalize_windows_paths - it converts output paths
    from Windows format to forward slash format for LLM consumption.

    Args:
        output: Command output potentially containing Windows-style paths

    Returns:
        Output with paths normalized to forward slashes

    Example:
        >>> normalize_output_paths_to_llm_format("File: C:\\\\Dev\\\\Han\\\\file.py")
        'File: C:/Dev/Han/file.py'

        >>> normalize_output_paths_to_llm_format("Path: /c/Dev/Han/file.py")
        'Path: /c/Dev/Han/file.py'  # Already normalized, unchanged
    """
    if sys.platform != 'win32':
        return output  # Only process on Windows

    # Pattern matches Windows absolute paths with backslashes
    # Example: C:\path\to\file or D:\another\path
    # We look for: drive_letter:\ followed by path segments with backslashes
    pattern = r'([A-Za-z]:)\\([^\s\n\r<>"|?*]+)'

    def replace_path(match):
        drive = match.group(1)  # e.g., "C:"
        path_part = match.group(2)  # e.g., "Dev\\Han\\aiNagisa\\file.py"
        # Replace all backslashes with forward slashes
        normalized_path = path_part.replace('\\', '/')
        return f"{drive}/{normalized_path}"

    # Replace all matched paths
    normalized_output = re.sub(pattern, replace_path, output)
    return normalized_output


__all__ = ['normalize_windows_paths', 'normalize_path_separators', 'path_to_llm_format', 'normalize_output_paths_to_llm_format']
