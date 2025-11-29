"""
Git Version Manager - Manages execution snapshots on pfc-executions branch.

This module provides git-based version tracking for PFC script executions,
creating commits on a dedicated branch without affecting the working directory.

Python 3.6 compatible implementation.
"""

import logging
import os
import subprocess
from typing import Dict, Optional, Any

# Module logger
logger = logging.getLogger("PFC-Server")

# Constants
EXECUTION_BRANCH = "pfc-executions"


class GitVersionManager:
    """
    Manage git-based version snapshots for PFC executions.

    Creates commits on a dedicated 'pfc-executions' branch using git commit-tree,
    without switching branches or affecting the current working directory.
    """

    def __init__(self, workspace_dir=None):
        # type: (Optional[str]) -> None
        """
        Initialize GitVersionManager.

        Args:
            workspace_dir: Git repository root directory. If None, uses current directory.
        """
        self.workspace_dir = workspace_dir or os.getcwd()
        self._git_available = None  # Lazy check

    def _run_git(self, args, check=True):
        # type: (list, bool) -> subprocess.CompletedProcess
        """
        Run a git command in the workspace directory.

        Args:
            args: List of git command arguments (without 'git' prefix)
            check: If True, raise exception on non-zero exit code

        Returns:
            CompletedProcess with stdout, stderr, returncode
        """
        cmd = ["git"] + args
        try:
            # Python 3.6 compatible: use run with capture_output equivalent
            result = subprocess.run(
                cmd,
                cwd=self.workspace_dir,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=True  # Python 3.6 compatible (text=True in 3.7+)
            )
            if check and result.returncode != 0:
                logger.error("Git command failed: {} -> {}".format(" ".join(cmd), result.stderr))
            return result
        except Exception as e:
            logger.error("Git command error: {} -> {}".format(" ".join(cmd), str(e)))
            raise

    def is_git_available(self):
        # type: () -> bool
        """Check if git is available and we're in a git repository."""
        if self._git_available is not None:
            return self._git_available

        try:
            result = self._run_git(["rev-parse", "--git-dir"], check=False)
            self._git_available = result.returncode == 0
        except Exception:
            self._git_available = False

        return self._git_available

    def check_git_state(self):
        # type: () -> Dict[str, Any]
        """
        Check git repository state for potential issues.

        Returns:
            Dict with:
                - ok: bool - True if safe to proceed
                - error: Optional[str] - Error message if not ok
                - current_branch: str - Current branch name
        """
        if not self.is_git_available():
            return {
                "ok": False,
                "error": "Not in a git repository. Run 'git init' to initialize.",
                "current_branch": None
            }

        # Check for rebase/merge in progress
        git_dir = self._run_git(["rev-parse", "--git-dir"]).stdout.strip()
        git_dir_path = os.path.join(self.workspace_dir, git_dir)

        if os.path.exists(os.path.join(git_dir_path, "rebase-merge")) or \
           os.path.exists(os.path.join(git_dir_path, "rebase-apply")):
            return {
                "ok": False,
                "error": "Git rebase in progress. Please complete or abort the rebase first.",
                "current_branch": None
            }

        if os.path.exists(os.path.join(git_dir_path, "MERGE_HEAD")):
            return {
                "ok": False,
                "error": "Git merge in progress. Please complete or abort the merge first.",
                "current_branch": None
            }

        # Get current branch
        result = self._run_git(["branch", "--show-current"], check=False)
        current_branch = result.stdout.strip() if result.returncode == 0 else None

        # Check if on execution branch (not allowed)
        if current_branch == EXECUTION_BRANCH:
            return {
                "ok": False,
                "error": "Cannot execute from '{}' branch. Please switch to main or a feature branch.".format(EXECUTION_BRANCH),
                "current_branch": current_branch
            }

        return {
            "ok": True,
            "error": None,
            "current_branch": current_branch
        }

    def ensure_execution_branch_exists(self):
        # type: () -> bool
        """
        Ensure the pfc-executions branch exists.

        Creates an orphan branch if it doesn't exist.

        Returns:
            True if branch exists or was created, False on error
        """
        # Check if branch exists
        result = self._run_git(["rev-parse", "--verify", EXECUTION_BRANCH], check=False)

        if result.returncode == 0:
            # Branch already exists
            return True

        # Create orphan branch with initial empty commit
        # We need to do this carefully to not affect current working directory
        logger.info("Creating execution tracking branch: {}".format(EXECUTION_BRANCH))

        try:
            # Get current branch to restore later
            current_result = self._run_git(["branch", "--show-current"])
            current_branch = current_result.stdout.strip()

            # Stash any changes
            stash_result = self._run_git(["stash", "push", "-m", "pfc-exec-temp"], check=False)
            stash_created = "No local changes" not in stash_result.stdout

            try:
                # Create orphan branch
                self._run_git(["checkout", "--orphan", EXECUTION_BRANCH])

                # Reset to remove staged files
                self._run_git(["reset", "--hard"], check=False)

                # Create initial empty commit
                self._run_git([
                    "commit", "--allow-empty",
                    "-m", "Initialize PFC execution tracking\n\nThis branch stores snapshots of code state at each PFC task execution."
                ])

                logger.info("✓ Created execution branch: {}".format(EXECUTION_BRANCH))

            finally:
                # Always restore original branch
                self._run_git(["checkout", current_branch], check=False)

                # Restore stashed changes
                if stash_created:
                    self._run_git(["stash", "pop"], check=False)

            return True

        except Exception as e:
            logger.error("Failed to create execution branch: {}".format(e))
            return False

    def create_execution_commit(self, task_id, description, entry_script=None):
        # type: (str, str, Optional[str]) -> Optional[str]
        """
        Create an execution snapshot commit on pfc-executions branch.

        Uses git write-tree and commit-tree to create commit without switching branches.

        Args:
            task_id: Task identifier for commit message
            description: Task description for commit message
            entry_script: Optional entry script path for commit message

        Returns:
            Commit hash if successful, None on error
        """
        # Check git state
        state = self.check_git_state()
        if not state["ok"]:
            logger.warning("Git state check failed: {}".format(state["error"]))
            return None

        # Ensure execution branch exists
        if not self.ensure_execution_branch_exists():
            logger.warning("Failed to ensure execution branch exists")
            return None

        try:
            # 1. Stage all files (including untracked) to create tree
            self._run_git(["add", "-A"])

            # 2. Create tree object from current index
            tree_result = self._run_git(["write-tree"])
            tree_hash = tree_result.stdout.strip()

            # 3. Reset index to not affect working directory
            self._run_git(["reset"], check=False)

            # 4. Get parent commit from execution branch
            parent_result = self._run_git(["rev-parse", EXECUTION_BRANCH])
            parent_hash = parent_result.stdout.strip()

            # 5. Build commit message
            entry_info = "Entry: {}".format(entry_script) if entry_script else ""
            commit_message = "[PFC-EXEC] {}: {}\n\n{}\nTask ID: {}".format(
                task_id[:8], description, entry_info, task_id
            )

            # 6. Create commit object directly (without switching branches)
            commit_result = self._run_git([
                "commit-tree", tree_hash,
                "-p", parent_hash,
                "-m", commit_message
            ])
            new_commit = commit_result.stdout.strip()

            # 7. Update execution branch ref to point to new commit
            self._run_git(["update-ref", "refs/heads/{}".format(EXECUTION_BRANCH), new_commit])

            logger.info("✓ Created execution commit: {} on branch {}".format(new_commit[:8], EXECUTION_BRANCH))

            return new_commit

        except Exception as e:
            logger.error("Failed to create execution commit: {}".format(e))
            # Try to reset index on failure
            self._run_git(["reset"], check=False)
            return None

    def get_current_commit(self):
        # type: () -> Optional[str]
        """Get current HEAD commit hash."""
        if not self.is_git_available():
            return None

        result = self._run_git(["rev-parse", "HEAD"], check=False)
        if result.returncode == 0:
            return result.stdout.strip()
        return None

    def is_dirty(self):
        # type: () -> bool
        """Check if working directory has uncommitted changes."""
        if not self.is_git_available():
            return False

        result = self._run_git(["status", "--porcelain"], check=False)
        return bool(result.stdout.strip())


# Singleton instance for the server
_manager = None  # type: Optional[GitVersionManager]


def get_git_manager(workspace_dir=None):
    # type: (Optional[str]) -> GitVersionManager
    """
    Get or create the GitVersionManager singleton.

    Args:
        workspace_dir: Git repository root directory

    Returns:
        GitVersionManager instance
    """
    global _manager
    if _manager is None:
        _manager = GitVersionManager(workspace_dir)
    return _manager
