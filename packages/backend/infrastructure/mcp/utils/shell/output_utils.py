"""Shell output processing utilities.

Provides functions for processing shell command output:
- Combining stdout and stderr
- Truncating large output
- Normalizing paths for LLM consumption
"""

from typing import Optional

# Constants matching Claude Code behavior
DEFAULT_MAX_OUTPUT_SIZE = 30000  # 30KB output limit


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


def truncate_output(output: str, max_size: int = DEFAULT_MAX_OUTPUT_SIZE) -> str:
    """Truncate output if it exceeds the maximum size.

    Args:
        output: The output string to truncate
        max_size: Maximum allowed size in characters

    Returns:
        Original output if within limit, or truncated with notice appended
    """
    if not output or len(output) <= max_size:
        return output

    truncated = output[:max_size]
    return f"{truncated}\n\n... [OUTPUT TRUNCATED - exceeded {max_size} character limit] ..."


def process_shell_output(
    stdout: str,
    stderr: str,
    max_size: int = DEFAULT_MAX_OUTPUT_SIZE,
    normalize_paths: bool = True
) -> str:
    """Process shell output for LLM consumption.

    Combines stdout/stderr, normalizes paths, and truncates if needed.

    Args:
        stdout: Standard output from command
        stderr: Standard error from command
        max_size: Maximum output size before truncation
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

    # Truncate if too large
    return truncate_output(combined, max_size)
