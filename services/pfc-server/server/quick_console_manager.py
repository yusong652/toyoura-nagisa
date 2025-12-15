"""
Quick Console Manager - Manage temporary script files for user Python console.

This module provides script file management for quick Python commands executed
from the user console (`>` prefix). Each command is saved as a temporary script
file for traceability and uniform task handling.

Script files are stored in: workspace/.quick_console/quick_XXX.py

Python 3.6 compatible implementation.
"""

import os
import logging
import threading
from typing import Optional, Tuple

# Module logger
logger = logging.getLogger("PFC-Server")

# Default directory for quick console scripts (relative to workspace)
QUICK_CONSOLE_DIR = ".quick_console"

# Maximum code size in characters (safety limit)
MAX_CODE_SIZE = 10000


class QuickConsoleManager:
    """
    Manage temporary script files for user Python console commands.

    Creates sequentially numbered script files (quick_001.py, quick_002.py, etc.)
    in the workspace/.quick_console/ directory. Each file contains exactly one
    user command for traceability.

    Thread-safe: Uses lock for counter management.
    """

    def __init__(self, workspace_path):
        # type: (str) -> None
        """
        Initialize quick console manager.

        Args:
            workspace_path: Absolute path to the PFC workspace directory
        """
        self.workspace_path = workspace_path
        self.console_dir = os.path.join(workspace_path, QUICK_CONSOLE_DIR)
        self._counter = 0
        self._lock = threading.Lock()

        # Ensure directory exists and initialize counter
        self._init_directory()

        logger.info("✓ QuickConsoleManager initialized (dir: {})".format(self.console_dir))

    def _init_directory(self):
        # type: () -> None
        """Create console directory and determine starting counter from existing files."""
        # Create directory if it doesn't exist
        is_new_dir = not os.path.exists(self.console_dir)
        if is_new_dir:
            os.makedirs(self.console_dir)
            logger.info("Created quick console directory: {}".format(self.console_dir))
            # Create README file for LLM context
            self._create_readme()
            return

        # Ensure README exists (for existing directories)
        readme_path = os.path.join(self.console_dir, "README.md")
        if not os.path.exists(readme_path):
            self._create_readme()

        # Find highest existing counter
        max_counter = 0
        try:
            for filename in os.listdir(self.console_dir):
                if filename.startswith("quick_") and filename.endswith(".py"):
                    try:
                        # Extract number from quick_XXX.py
                        num_str = filename[6:-3]  # Remove "quick_" and ".py"
                        num = int(num_str)
                        if num > max_counter:
                            max_counter = num
                    except ValueError:
                        continue

            self._counter = max_counter
            logger.info("Quick console counter initialized at: {}".format(self._counter))

        except Exception as e:
            logger.warning("Failed to scan existing quick scripts: {}".format(e))

    def _create_readme(self):
        # type: () -> None
        """Create README file explaining the quick console directory."""
        readme_path = os.path.join(self.console_dir, "README.md")
        readme_content = """# Quick Console Scripts

This directory contains Python scripts executed by the **user** through the PFC Python console (`>` prefix in CLI).

## Important Notes for LLM

- **Source**: These scripts are created from user console input, NOT by the AI agent
- **Purpose**: Quick exploration, testing, and interactive PFC operations
- **Naming**: `quick_XXX.py` where XXX is a sequential number
- **Task Source**: Tasks from these scripts have `source: "user_console"` in task history

## Script Format

Each script contains:
1. Header comment with metadata
2. User's Python code (may include `itasca.command()` calls)

## Viewing History

To see all tasks including user console commands:
- Use `pfc_list_tasks` tool
- Filter by `source: "user_console"` for user-initiated tasks
- Filter by `source: "agent"` for AI-initiated tasks

## Note

Do NOT modify or delete these files manually. They serve as execution history
for traceability and debugging purposes.
"""
        try:
            with open(readme_path, 'w', encoding='utf-8') as f:
                f.write(readme_content)
            logger.info("Created README in quick console directory")
        except Exception as e:
            logger.warning("Failed to create README: {}".format(e))

    def _get_next_filename(self):
        # type: () -> Tuple[str, str]
        """
        Get next available filename (thread-safe).

        Returns:
            Tuple of (script_name, script_path):
                - script_name: "quick_XXX.py"
                - script_path: Full absolute path to the script file
        """
        with self._lock:
            self._counter += 1
            script_name = "quick_{:03d}.py".format(self._counter)
            script_path = os.path.join(self.console_dir, script_name)
            return script_name, script_path

    def create_script(self, code, description=None):
        # type: (str, Optional[str]) -> Tuple[str, str, str]
        """
        Create a temporary script file for user console code.

        Args:
            code: Python code to execute (single line or multi-line)
            description: Optional description/comment for the script header

        Returns:
            Tuple of (script_name, script_path, code):
                - script_name: "quick_XXX.py" (for display)
                - script_path: Full absolute path to the script file
                - code: The code content (for reference)

        Raises:
            ValueError: If code is empty or exceeds size limit
            IOError: If file cannot be written
        """
        # Validate code
        if not code or not code.strip():
            raise ValueError("Code cannot be empty")

        if len(code) > MAX_CODE_SIZE:
            raise ValueError("Code exceeds maximum size limit ({} chars)".format(MAX_CODE_SIZE))

        # Get next filename
        script_name, script_path = self._get_next_filename()

        # Build script content with header comment
        header_lines = [
            "# Quick Console Command",
            "# Auto-generated script for user console execution",
        ]
        if description:
            header_lines.append("# Description: {}".format(description))
        header_lines.append("")  # Empty line before code

        script_content = "\n".join(header_lines) + code

        # Write script file
        try:
            with open(script_path, 'w', encoding='utf-8') as f:
                f.write(script_content)

            logger.info("✓ Quick script created: {} ({} chars)".format(
                script_name, len(code)
            ))

            return script_name, script_path, code

        except Exception as e:
            logger.error("Failed to create quick script {}: {}".format(script_name, e))
            raise IOError("Failed to create script file: {}".format(e))

    def get_code_preview(self, code, max_length=50):
        # type: (str, int) -> str
        """
        Generate a truncated preview of code for display.

        Args:
            code: Full code string
            max_length: Maximum preview length

        Returns:
            Truncated code preview (single line)
        """
        # Get first line, strip whitespace
        first_line = code.split('\n')[0].strip()

        if len(first_line) <= max_length:
            return first_line

        return first_line[:max_length - 3] + "..."

    def cleanup_old_scripts(self, keep_count=100):
        # type: (int) -> int
        """
        Remove old script files, keeping the most recent N files.

        Args:
            keep_count: Number of recent scripts to keep

        Returns:
            Number of files removed
        """
        try:
            # List all quick scripts with their numbers
            scripts = []
            for filename in os.listdir(self.console_dir):
                if filename.startswith("quick_") and filename.endswith(".py"):
                    try:
                        num_str = filename[6:-3]
                        num = int(num_str)
                        scripts.append((num, filename))
                    except ValueError:
                        continue

            # Sort by number (oldest first)
            scripts.sort(key=lambda x: x[0])

            # Remove oldest scripts if over limit
            removed = 0
            while len(scripts) > keep_count:
                _, filename = scripts.pop(0)
                filepath = os.path.join(self.console_dir, filename)
                try:
                    os.remove(filepath)
                    removed += 1
                except Exception as e:
                    logger.warning("Failed to remove {}: {}".format(filename, e))

            if removed > 0:
                logger.info("Cleaned up {} old quick script(s)".format(removed))

            return removed

        except Exception as e:
            logger.error("Failed to cleanup quick scripts: {}".format(e))
            return 0
