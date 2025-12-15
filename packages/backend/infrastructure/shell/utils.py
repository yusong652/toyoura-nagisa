"""Shared shell execution utilities.

Provides common functionality for shell command execution:
- Python command detection and enhancement
- Environment preparation for subprocess execution

Used by both ShellExecutor (synchronous) and BackgroundProcessManager (async streaming).
"""

import os
import re
import sys
from typing import Dict, Tuple


# Python invocation patterns for detection
PYTHON_PATTERNS = [
    r'^\s*python\d*\s+',
    r'^\s*python\d*\.\d+\s+',
    r'^\s*/.*python\d*\s+',
    r'^\s*\.venv/.*python\s+',
    r'^\s*venv/.*python\s+',
    r'^\s*uv\s+run\s+python\s+',
    r'^\s*poetry\s+run\s+python\s+',
    r'^\s*pipenv\s+run\s+python\s+',
]


def detect_python_command(command: str) -> bool:
    """Detect if a command is running Python.

    Checks for common Python invocation patterns including:
    - Direct python/python3 invocations
    - Virtual environment python
    - Package manager runners (uv, poetry, pipenv)

    Args:
        command: Shell command to analyze

    Returns:
        True if command appears to run Python
    """
    for pattern in PYTHON_PATTERNS:
        if re.match(pattern, command, re.IGNORECASE):
            return True
    return False


def enhance_python_command(command: str) -> Tuple[str, bool]:
    """Enhance Python commands to force unbuffered output.

    For Python scripts on Unix, adds PYTHONUNBUFFERED=1 prefix to ensure
    real-time output streaming instead of buffered output.
    On Windows, the environment variable is set via prepare_shell_env instead.

    Args:
        command: Original shell command

    Returns:
        Tuple of (enhanced_command, is_python)
        - enhanced_command: Command with unbuffered flag if Python (Unix only)
        - is_python: Whether Python was detected
    """
    is_python = detect_python_command(command)
    if not is_python:
        return command, False

    # On Windows, env var prefix syntax doesn't work
    # PYTHONUNBUFFERED is set via prepare_shell_env instead
    if sys.platform == "win32":
        return command, True

    # Add PYTHONUNBUFFERED environment variable prefix (Unix only)
    # This is more reliable than -u flag since it works with all Python invocations
    return f"PYTHONUNBUFFERED=1 {command}", True


def prepare_shell_env(
    base_env: Dict[str, str] = None,
    force_unbuffered: bool = True,
    encoding: str = "utf-8",
) -> Dict[str, str]:
    """Prepare environment variables for shell execution.

    Creates a copy of the environment with shell-friendly settings:
    - PYTHONUNBUFFERED: Force unbuffered Python output
    - PYTHONIOENCODING: Ensure consistent encoding

    Args:
        base_env: Base environment dict (defaults to os.environ)
        force_unbuffered: Add PYTHONUNBUFFERED=1
        encoding: Python IO encoding (default: utf-8)

    Returns:
        Environment dict ready for subprocess
    """
    env = (base_env or os.environ).copy()

    if force_unbuffered:
        env['PYTHONUNBUFFERED'] = '1'

    if encoding:
        env['PYTHONIOENCODING'] = encoding

    return env
