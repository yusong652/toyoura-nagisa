"""Shell state persistence.

Manages persistent shell state (cwd, etc.) for user shell sessions.
State is stored in workspace directory as JSON file.

The state storage is an infrastructure concern - it handles file I/O.
Business logic for when/how to update state belongs in the application layer.
"""

import json
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Optional


# Default state file name within workspace
STATE_FILE_NAME = "shell_state.json"


@dataclass
class ShellState:
    """Persistent shell state.

    Attributes:
        cwd: Current working directory for shell commands
    """
    cwd: str

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "ShellState":
        """Create from dictionary."""
        return cls(cwd=data.get("cwd", ""))


class ShellStateStorage:
    """Manages shell state persistence.

    Reads and writes shell state to a JSON file in the workspace directory.
    Provides atomic updates and handles missing/corrupted state files gracefully.

    Example:
        storage = ShellStateStorage(workspace_root=Path("/path/to/workspace"))
        state = storage.load()
        print(f"Current directory: {state.cwd}")

        state.cwd = "/new/path"
        storage.save(state)
    """

    def __init__(self, workspace_root: Path):
        """Initialize state storage.

        Args:
            workspace_root: Root directory of the workspace.
                           State file will be created at workspace_root/shell_state.json
        """
        self.workspace_root = workspace_root
        self.state_file = workspace_root / STATE_FILE_NAME

    def load(self) -> ShellState:
        """Load shell state from file.

        If state file doesn't exist or is corrupted, returns default state
        with cwd set to workspace root.

        Returns:
            ShellState with current values
        """
        if not self.state_file.exists():
            return self._default_state()

        try:
            with open(self.state_file, "r", encoding="utf-8") as f:
                data = json.load(f)

            state = ShellState.from_dict(data)

            # Validate cwd exists, reset to workspace if not
            if not Path(state.cwd).exists():
                state.cwd = str(self.workspace_root)
                self.save(state)

            return state

        except (json.JSONDecodeError, KeyError, TypeError):
            # Corrupted file, return default
            return self._default_state()

    def save(self, state: ShellState) -> None:
        """Save shell state to file.

        Creates parent directories if needed. Uses atomic write pattern
        to prevent corruption.

        Args:
            state: ShellState to persist
        """
        # Ensure workspace directory exists
        self.workspace_root.mkdir(parents=True, exist_ok=True)

        # Write to temp file first, then rename (atomic on most systems)
        temp_file = self.state_file.with_suffix(".json.tmp")
        try:
            with open(temp_file, "w", encoding="utf-8") as f:
                json.dump(state.to_dict(), f, indent=2, ensure_ascii=False)

            # Atomic rename
            temp_file.rename(self.state_file)

        except Exception:
            # Clean up temp file on failure
            if temp_file.exists():
                temp_file.unlink()
            raise

    def reset(self) -> ShellState:
        """Reset state to default values.

        Returns:
            Fresh default ShellState
        """
        state = self._default_state()
        self.save(state)
        return state

    def update_cwd(self, new_cwd: str) -> ShellState:
        """Update current working directory.

        Convenience method for the most common state update.

        Args:
            new_cwd: New working directory path

        Returns:
            Updated ShellState
        """
        state = self.load()
        state.cwd = new_cwd
        self.save(state)
        return state

    def _default_state(self) -> ShellState:
        """Create default state with workspace root as cwd."""
        return ShellState(cwd=str(self.workspace_root))
