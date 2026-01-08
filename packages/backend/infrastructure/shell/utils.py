"""Shared shell execution utilities.

Provides common functionality for shell command execution:
- Python command detection and enhancement
- Environment preparation for subprocess execution

Used by both ShellExecutor (synchronous) and BackgroundProcessManager (async streaming).
"""

import os
import re
import sys
from typing import Dict, Tuple, Optional


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


def prepare_shell_env(
    base_env: Optional[Dict[str, str]],
    force_unbuffered: bool = True,
    encoding: str = "utf-8",
) -> Dict[str, str]:
    """Prepare environment variables for shell execution.

    Creates a copy of the environment with shell-friendly settings:
    - PYTHONUNBUFFERED: Force unbuffered Python output
    - PYTHONIOENCODING: Ensure consistent encoding
    - PYTHONUTF8: Enable UTF-8 mode for Python (Windows)
    - LC_ALL/LANG: Ensure UTF-8 locale for proper Unicode handling

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

    # Enable UTF-8 mode on Windows for consistent encoding
    if sys.platform == "win32":
        env['PYTHONUTF8'] = '1'
    else:
        # On Unix-like systems (macOS, Linux), ensure UTF-8 locale
        # This ensures commands like git, ls output Unicode properly
        # instead of octal escape sequences (e.g., \346\265\213 instead of 测试)
        env['LC_ALL'] = 'en_US.UTF-8'
        env['LANG'] = 'en_US.UTF-8'

    return env
