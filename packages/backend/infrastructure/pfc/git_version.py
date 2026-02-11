"""Git Version Manager - Manages execution snapshots on pfc-executions branch.

Migrated from pfc-bridge to toyoura-nagisa backend.
Creates commits on a dedicated branch without affecting the working directory.
"""

import logging
import os
import subprocess
from typing import Dict, Optional, Any

logger = logging.getLogger(__name__)

EXECUTION_BRANCH = "pfc-executions"


class GitVersionManager:
    """Manage git-based version snapshots for PFC executions.

    Creates commits on a dedicated 'pfc-executions' branch using git commit-tree,
    without switching branches or affecting the current working directory.
    """

    def __init__(self, workspace_dir: Optional[str] = None):
        self.workspace_dir = workspace_dir or os.getcwd()

    def _run_git(self, args: list, check: bool = True) -> subprocess.CompletedProcess:
        """Run a git command in the workspace directory."""
        cmd = ["git"] + args
        kwargs: Dict[str, Any] = {
            "cwd": self.workspace_dir,
            "stdout": subprocess.PIPE,
            "stderr": subprocess.PIPE,
            "text": True,
        }
        if os.name == "nt":
            kwargs["creationflags"] = 0x08000000  # CREATE_NO_WINDOW

        result = subprocess.run(cmd, **kwargs)
        if check and result.returncode != 0:
            logger.error(f"Git command failed: {' '.join(cmd)} -> {result.stderr}")
        return result

    def is_git_available(self) -> bool:
        """Check if git is available and we're in a git repository."""
        try:
            result = self._run_git(["rev-parse", "--git-dir"], check=False)
            return result.returncode == 0
        except Exception:
            return False

    def check_git_state(self) -> Dict[str, Any]:
        """Check git repository state for potential issues."""
        if not self.is_git_available():
            return {"ok": False, "error": "Not in a git repository.", "current_branch": None}

        git_dir = self._run_git(["rev-parse", "--git-dir"]).stdout.strip()
        git_dir_path = os.path.join(self.workspace_dir, git_dir)

        if os.path.exists(os.path.join(git_dir_path, "rebase-merge")) or \
           os.path.exists(os.path.join(git_dir_path, "rebase-apply")):
            return {"ok": False, "error": "Git rebase in progress.", "current_branch": None}

        if os.path.exists(os.path.join(git_dir_path, "MERGE_HEAD")):
            return {"ok": False, "error": "Git merge in progress.", "current_branch": None}

        result = self._run_git(["branch", "--show-current"], check=False)
        current_branch = result.stdout.strip() if result.returncode == 0 else None

        if current_branch == EXECUTION_BRANCH:
            return {
                "ok": False,
                "error": f"Cannot execute from '{EXECUTION_BRANCH}' branch.",
                "current_branch": current_branch,
            }

        return {"ok": True, "error": None, "current_branch": current_branch}

    def ensure_execution_branch_exists(self) -> bool:
        """Ensure the pfc-executions branch exists. Creates orphan if needed."""
        result = self._run_git(["rev-parse", "--verify", EXECUTION_BRANCH], check=False)
        if result.returncode == 0:
            return True

        try:
            current_result = self._run_git(["branch", "--show-current"], check=False)
            current_branch = current_result.stdout.strip()
            if not current_branch:
                head_result = self._run_git(["rev-parse", "HEAD"], check=False)
                current_branch = head_result.stdout.strip() if head_result.returncode == 0 else None

            if not current_branch:
                logger.error("Cannot determine current branch - aborting branch creation")
                return False

            stash_result = self._run_git(["stash", "push", "-m", "pfc-exec-temp"], check=False)
            stash_created = "No local changes" not in stash_result.stdout

            branch_created = False
            try:
                self._run_git(["checkout", "--orphan", EXECUTION_BRANCH])
                self._run_git(["reset", "--hard"], check=False)
                self._run_git(["commit", "--allow-empty", "-m",
                               "Initialize PFC execution tracking"])
                branch_created = True
            finally:
                if current_branch:
                    checkout_result = self._run_git(["checkout", current_branch], check=False)
                    if checkout_result.returncode != 0:
                        self._run_git(["checkout", "-f", current_branch], check=False)
                if stash_created:
                    self._run_git(["stash", "pop"], check=False)

            return branch_created

        except Exception as e:
            logger.error(f"Failed to create execution branch: {e}")
            return False

    def create_execution_commit(
        self,
        task_id: str,
        description: str,
        entry_script: Optional[str] = None,
    ) -> Optional[str]:
        """Create an execution snapshot commit on pfc-executions branch.

        Uses git write-tree and commit-tree to avoid switching branches.

        Returns:
            Commit hash if successful, None on error.
        """
        state = self.check_git_state()
        if not state["ok"]:
            logger.warning(f"Git state check failed: {state['error']}")
            return None

        if not self.ensure_execution_branch_exists():
            return None

        try:
            self._run_git(["add", "-A"])
            tree_result = self._run_git(["write-tree"])
            tree_hash = tree_result.stdout.strip()
            self._run_git(["reset"], check=False)

            parent_result = self._run_git(["rev-parse", EXECUTION_BRANCH])
            parent_hash = parent_result.stdout.strip()

            entry_info = f"Entry: {entry_script}" if entry_script else ""
            commit_message = f"[PFC-EXEC] {task_id[:8]}: {description}\n\n{entry_info}\nTask ID: {task_id}"

            commit_result = self._run_git([
                "commit-tree", tree_hash, "-p", parent_hash, "-m", commit_message
            ])
            new_commit = commit_result.stdout.strip()

            self._run_git(["update-ref", f"refs/heads/{EXECUTION_BRANCH}", new_commit])
            return new_commit

        except Exception as e:
            logger.error(f"Failed to create execution commit: {e}")
            self._run_git(["reset"], check=False)
            return None


def find_git_root(start_path: str) -> Optional[str]:
    """Find the git repository root directory starting from a given path."""
    current = os.path.abspath(start_path)
    if os.path.isfile(current):
        current = os.path.dirname(current)

    while current:
        if os.path.exists(os.path.join(current, ".git")):
            return current
        parent = os.path.dirname(current)
        if parent == current:
            break
        current = parent
    return None


_managers: Dict[str, GitVersionManager] = {}


def get_git_manager(workspace_dir: Optional[str] = None) -> GitVersionManager:
    """Get or create a GitVersionManager for the specified workspace."""
    start_path = workspace_dir or os.getcwd()
    git_root = find_git_root(start_path)
    resolved_dir = git_root or os.path.abspath(start_path)

    if resolved_dir not in _managers:
        _managers[resolved_dir] = GitVersionManager(resolved_dir)
    return _managers[resolved_dir]
