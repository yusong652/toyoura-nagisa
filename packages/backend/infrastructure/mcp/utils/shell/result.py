"""Shell execution result data structure.

Provides a unified result type for shell command execution,
used by both agent's bash tool and user's shell commands.
"""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class ShellExecutionResult:
    """Result of a shell command execution.

    This dataclass provides a unified structure for shell execution results,
    enabling consistent handling across:
    - Agent's bash tool (backend)
    - User's shell commands (CLI)

    Attributes:
        stdout: Standard output from the command
        stderr: Standard error from the command
        exit_code: Process exit code (0 = success)
        command: The command that was executed
        execution_time: Time taken to execute (seconds)
        working_directory: Directory where command was executed
        timed_out: Whether the command timed out
        original_command: Original command before normalization (if different)
    """
    stdout: str
    stderr: str
    exit_code: int
    command: str
    execution_time: float = 0.0
    working_directory: str = ""
    timed_out: bool = False
    original_command: Optional[str] = None

    @property
    def success(self) -> bool:
        """Check if command executed successfully."""
        return self.exit_code == 0 and not self.timed_out

    @property
    def has_output(self) -> bool:
        """Check if command produced any output."""
        return bool(self.stdout or self.stderr)

    @property
    def combined_output(self) -> str:
        """Get combined stdout and stderr output."""
        from .output_utils import combine_stdout_stderr
        return combine_stdout_stderr(self.stdout, self.stderr)

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        result = {
            "stdout": self.stdout,
            "stderr": self.stderr,
            "exit_code": self.exit_code,
            "command": self.command,
            "execution_time": self.execution_time,
            "working_directory": self.working_directory,
            "timed_out": self.timed_out,
        }
        if self.original_command:
            result["original_command"] = self.original_command
        return result
