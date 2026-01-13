"""Shell configuration for cross-platform command execution.

Provides automatic shell detection with platform-specific defaults:
- Unix: $SHELL environment variable, fallback to /bin/bash
- Windows: Git Bash (if in PATH), fallback to cmd.exe

Override with TOYOURA_NAGISA_SHELL environment variable.
"""

import os
import shutil
import sys
from dataclasses import dataclass
from typing import List


@dataclass
class ShellConfig:
    """Shell configuration for subprocess execution.

    Attributes:
        path: Path to the shell executable
        args: Arguments to pass before the command (includes -c or /c)
        is_cmd: True if using cmd.exe (affects command preparation)
    """

    path: str
    args: List[str]
    is_cmd: bool = False

    def build_command(self, command: str) -> List[str]:
        """Build full command list for subprocess execution.

        Args:
            command: The shell command to execute

        Returns:
            List of arguments for subprocess.Popen
        """
        return [self.path, *self.args, command]

    @classmethod
    def detect(cls) -> "ShellConfig":
        """Detect appropriate shell for current platform.

        Priority:
        1. TOYOURA_NAGISA_SHELL environment variable (cross-platform)
        2. Windows: shutil.which("bash") -> cmd.exe
        3. Unix: $SHELL -> /bin/bash

        Returns:
            ShellConfig with path and args for subprocess execution
        """
        # 1. Environment override (cross-platform, assumes bash-compatible)
        if shell := os.environ.get("TOYOURA_NAGISA_SHELL"):
            return cls(path=shell, args=["-l", "-c"], is_cmd=False)

        if sys.platform == "win32":
            # 2. Try PATH detection (Git Bash in PATH)
            if bash := shutil.which("bash"):
                return cls(path=bash, args=["-l", "-c"], is_cmd=False)
            # 3. Fallback to cmd.exe
            return cls(path="cmd.exe", args=["/c"], is_cmd=True)
        else:
            # Unix: Use $SHELL or /bin/bash
            shell = os.environ.get("SHELL", "/bin/bash")
            return cls(path=shell, args=["-l", "-c"], is_cmd=False)


# Singleton instance (lazy initialization)
_shell_config: ShellConfig | None = None


def get_shell_config() -> ShellConfig:
    """Get the global shell configuration instance."""
    global _shell_config
    if _shell_config is None:
        _shell_config = ShellConfig.detect()
    return _shell_config
