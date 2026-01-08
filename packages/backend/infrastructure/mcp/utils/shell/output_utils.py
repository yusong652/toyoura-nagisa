"""Shell output processing utilities.

Provides functions for processing shell command output:
- Combining stdout and stderr
- Truncating large output
- Normalizing paths for LLM consumption
"""

from typing import Optional

# Output limits for LLM consumption
DEFAULT_MAX_OUTPUT_LINES = 1000  # Line-based limit (more predictable than bytes)


def combine_stdout_stderr(stdout: str, stderr: str) -> str:
    """Combine stdout and stderr into a single output string.

    Args:
        stdout: Standard output from command
        stderr: Standard error from command

    Returns:
        Combined output with stderr appended after stdout (if both exist)
    """
    stdout = stdout or ""
    stderr = stderr or ""

    if stdout and stderr:
        return f"{stdout}\n{stderr}"
    return stdout or stderr


def truncate_output(output: str, max_lines: int = DEFAULT_MAX_OUTPUT_LINES) -> str:
    """Truncate output if it exceeds the maximum line count.

    Args:
        output: The output string to truncate
        max_lines: Maximum allowed number of lines

    Returns:
        Original output if within limit, or truncated with notice appended
    """
    if not output:
        return output

    lines = output.split('\n')
    if len(lines) <= max_lines:
        return output

    truncated = '\n'.join(lines[:max_lines])
    return f"{truncated}\n\n... [TRUNCATED - showing {max_lines} of {len(lines)} lines] ..."


def process_shell_output(
    stdout: str,
    stderr: str,
    max_lines: int = DEFAULT_MAX_OUTPUT_LINES,
    normalize_paths: bool = True
) -> str:
    """Process shell output for LLM consumption.

    Combines stdout/stderr, normalizes paths, and truncates if needed.

    Args:
        stdout: Standard output from command
        stderr: Standard error from command
        max_lines: Maximum output lines before truncation
        normalize_paths: Whether to normalize Windows paths to forward slashes

    Returns:
        Processed output string ready for LLM
    """
    # Combine outputs
    combined = combine_stdout_stderr(stdout, stderr)

    # Normalize Windows paths if requested
    if normalize_paths and combined:
        from backend.infrastructure.mcp.utils.path_normalization import (
            normalize_output_paths_to_llm_format
        )
        combined = normalize_output_paths_to_llm_format(combined)

    # Truncate if too many lines
    return truncate_output(combined, max_lines)
