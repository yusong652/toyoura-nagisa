"""Shared shell execution utilities.

Provides common functionality for shell command execution:
- Python command detection and enhancement
- Environment preparation for subprocess execution
- Output buffer limits
- Memory-safe bounded output reading

Used by both ShellExecutor (synchronous) and BackgroundProcessManager (async streaming).
"""

import os
import re
import subprocess
import sys
from dataclasses import dataclass
from typing import Dict, Optional

# select() only works with pipes on Unix, not Windows
if sys.platform != "win32":
    import select


# Background process buffer limits (memory protection)
MAX_LINE_LENGTH = 10000   # Single line max (10KB), prevents minified JS issues
MAX_BUFFER_LINES = 10000  # Circular buffer size for streaming output

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


# =============================================================================
# Bounded Output Reading (Memory Protection)
# =============================================================================

# Maximum bytes to read from stdout/stderr before truncating.
# 512KB is generous for normal use while preventing GB-scale outputs
# from commands like `grep -r` on large codebases.
MAX_OUTPUT_BYTES = 512 * 1024  # 512KB per stream

# Chunk size for reading. Smaller = more responsive, larger = fewer syscalls.
READ_CHUNK_SIZE = 8 * 1024  # 8KB


@dataclass
class BoundedOutput:
    """Result of bounded stream reading."""

    content: str
    truncated: bool
    bytes_read: int

    def with_truncation_notice(self) -> str:
        """Return content with truncation notice if applicable."""
        if not self.truncated:
            return self.content
        return (
            f"{self.content}\n\n"
            f"... [OUTPUT TRUNCATED: {self.bytes_read:,} bytes read, limit reached] ..."
        )


def _bounded_communicate_windows(
    process: subprocess.Popen,
    max_bytes: int,
) -> tuple[BoundedOutput, BoundedOutput]:
    """Windows implementation using simple communicate() with truncation.

    Windows doesn't support select() on pipes, so we use communicate()
    and truncate the output afterward. This is less efficient for large
    outputs but works reliably.
    """
    try:
        stdout, stderr = process.communicate(timeout=300)  # 5 min timeout
    except subprocess.TimeoutExpired:
        process.kill()
        stdout, stderr = process.communicate()

    # Truncate if needed
    stdout = stdout or ""
    stderr = stderr or ""

    stdout_bytes = len(stdout.encode('utf-8', errors='replace'))
    stderr_bytes = len(stderr.encode('utf-8', errors='replace'))

    stdout_truncated = stdout_bytes > max_bytes
    stderr_truncated = stderr_bytes > max_bytes

    if stdout_truncated:
        stdout = stdout[:max_bytes]
        stdout_bytes = max_bytes
    if stderr_truncated:
        stderr = stderr[:max_bytes]
        stderr_bytes = max_bytes

    return (
        BoundedOutput(content=stdout, truncated=stdout_truncated, bytes_read=stdout_bytes),
        BoundedOutput(content=stderr, truncated=stderr_truncated, bytes_read=stderr_bytes),
    )


def bounded_communicate(
    process: subprocess.Popen,
    max_bytes: int = MAX_OUTPUT_BYTES,
    chunk_size: int = READ_CHUNK_SIZE,
) -> tuple[BoundedOutput, BoundedOutput]:
    """Memory-safe replacement for process.communicate().

    On Unix: Uses select() for non-blocking I/O with streaming truncation.
    On Windows: Uses communicate() with post-hoc truncation.

    If either stream exceeds the limit, output is truncated.

    Args:
        process: Subprocess with stdout/stderr pipes (text mode)
        max_bytes: Maximum bytes per stream (default 512KB)
        chunk_size: Read chunk size (Unix only)

    Returns:
        Tuple of (stdout_result, stderr_result) as BoundedOutput

    Example:
        process = subprocess.Popen(cmd, stdout=PIPE, stderr=PIPE, text=True)
        stdout, stderr = bounded_communicate(process)
        if stdout.truncated or stderr.truncated:
            # Output was too large
            pass
        result = stdout.with_truncation_notice()
    """
    # Windows: use simple communicate() + truncation
    if sys.platform == "win32":
        return _bounded_communicate_windows(process, max_bytes)

    # Unix: use select() for streaming reads with early termination
    stdout_chunks: list[str] = []
    stderr_chunks: list[str] = []
    stdout_bytes = 0
    stderr_bytes = 0
    stdout_truncated = False
    stderr_truncated = False

    # Get file objects for select
    stdout_fd = process.stdout
    stderr_fd = process.stderr
    read_set: list = []
    if stdout_fd:
        read_set.append(stdout_fd)
    if stderr_fd:
        read_set.append(stderr_fd)

    while read_set:
        # Use select with timeout to check for readable streams
        try:
            readable, _, _ = select.select(read_set, [], [], 0.1)
        except (ValueError, OSError):
            # Pipe closed or invalid
            break

        if not readable:
            # Check if process has exited
            if process.poll() is not None:
                # Process done, do final reads
                for fd in list(read_set):
                    try:
                        remaining = fd.read()
                        if remaining:
                            if fd == stdout_fd and not stdout_truncated:
                                chunk_bytes = len(remaining.encode('utf-8', errors='replace'))
                                if stdout_bytes + chunk_bytes > max_bytes:
                                    # Truncate to fit
                                    allowed = max_bytes - stdout_bytes
                                    stdout_chunks.append(remaining[:allowed])
                                    stdout_bytes = max_bytes
                                    stdout_truncated = True
                                else:
                                    stdout_chunks.append(remaining)
                                    stdout_bytes += chunk_bytes
                            elif fd == stderr_fd and not stderr_truncated:
                                chunk_bytes = len(remaining.encode('utf-8', errors='replace'))
                                if stderr_bytes + chunk_bytes > max_bytes:
                                    allowed = max_bytes - stderr_bytes
                                    stderr_chunks.append(remaining[:allowed])
                                    stderr_bytes = max_bytes
                                    stderr_truncated = True
                                else:
                                    stderr_chunks.append(remaining)
                                    stderr_bytes += chunk_bytes
                    except Exception:
                        pass
                break
            continue

        for fd in readable:
            try:
                chunk = fd.read(chunk_size)
            except Exception:
                read_set.remove(fd)
                continue

            if not chunk:
                # EOF on this stream
                read_set.remove(fd)
                continue

            chunk_bytes = len(chunk.encode('utf-8', errors='replace'))

            if fd == stdout_fd:
                if stdout_truncated:
                    # Already truncated, discard
                    continue
                if stdout_bytes + chunk_bytes > max_bytes:
                    # Would exceed limit - truncate and mark
                    allowed = max_bytes - stdout_bytes
                    if allowed > 0:
                        stdout_chunks.append(chunk[:allowed])
                    stdout_bytes = max_bytes
                    stdout_truncated = True
                    # Kill process immediately to unblock pipes
                    if process.poll() is None:
                        process.kill()
                else:
                    stdout_chunks.append(chunk)
                    stdout_bytes += chunk_bytes

            elif fd == stderr_fd:
                if stderr_truncated:
                    continue
                if stderr_bytes + chunk_bytes > max_bytes:
                    allowed = max_bytes - stderr_bytes
                    if allowed > 0:
                        stderr_chunks.append(chunk[:allowed])
                    stderr_bytes = max_bytes
                    stderr_truncated = True
                    if process.poll() is None:
                        process.kill()
                else:
                    stderr_chunks.append(chunk)
                    stderr_bytes += chunk_bytes

        # If both streams truncated, stop reading
        if stdout_truncated and stderr_truncated:
            break

    # Ensure process is terminated
    if process.poll() is None:
        process.kill()
        try:
            process.wait(timeout=2.0)
        except subprocess.TimeoutExpired:
            pass

    return (
        BoundedOutput(
            content=''.join(stdout_chunks),
            truncated=stdout_truncated,
            bytes_read=stdout_bytes,
        ),
        BoundedOutput(
            content=''.join(stderr_chunks),
            truncated=stderr_truncated,
            bytes_read=stderr_bytes,
        ),
    )
