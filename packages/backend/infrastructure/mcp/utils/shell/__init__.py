"""Shell execution utilities for bash tool and user shell commands.

This module provides shared logic for:
- Agent's bash tool (stateless, per-command execution)
- User's shell commands (stateful, persistent shell session)

Both produce the same LLM-compatible format: <bash-input/stdout/stderr>
"""

from .result import ShellExecutionResult
from .output_utils import (
    combine_stdout_stderr,
    truncate_output,
    process_shell_output,
    DEFAULT_MAX_OUTPUT_CHARS,
)
from .context_format import (
    format_for_llm_context,
    format_caveat_message,
    format_with_caveat,
    format_from_result,
)

__all__ = [
    "ShellExecutionResult",
    "combine_stdout_stderr",
    "truncate_output",
    "process_shell_output",
    "format_for_llm_context",
    "format_caveat_message",
    "format_with_caveat",
    "format_from_result",
    "DEFAULT_MAX_OUTPUT_CHARS",
]
