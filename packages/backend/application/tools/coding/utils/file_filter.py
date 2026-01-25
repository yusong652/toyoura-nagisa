from __future__ import annotations

"""File filtering utilities shared by filesystem tools.

Provides :class:`FileFilter` which handles:

1. Hidden file exclusion (`show_hidden`)
2. Glob pattern ignore (`ignore_patterns`)
3. `.gitignore` respect (`respect_git_ignore`)

By centralising this logic we keep individual tool implementations small and
consistent.
"""

from pathlib import Path
from typing import List, Optional
import fnmatch

# Optional dependency – gracefully degrade if missing
try:
    from pathspec import PathSpec  # type: ignore
    from pathspec.patterns.gitwildmatch import GitWildMatchPattern  # type: ignore
except ModuleNotFoundError:  # pragma: no cover
    PathSpec = None  # type: ignore
    GitWildMatchPattern = None  # type: ignore

__all__ = ["FileFilter"]


class FileFilter:
    """Utility class to decide whether a given *Path* should be included."""

    def __init__(
        self,
        workspace_root: Path,
        show_hidden: bool = False,
        ignore_patterns: Optional[List[str]] = None,
        respect_git_ignore: bool = True,
    ) -> None:
        self.workspace_root = workspace_root.resolve()
        self.show_hidden = show_hidden
        self.ignore_patterns = ignore_patterns or []
        self.git_ignored_count: int = 0

        # Build gitignore spec if requested and available
        self._git_spec = None
        if respect_git_ignore and PathSpec is not None:
            gitignore_file = self.workspace_root / ".gitignore"
            if gitignore_file.exists():
                try:
                    self._git_spec = PathSpec.from_lines(
                        GitWildMatchPattern, gitignore_file.read_text().splitlines()
                    )
                except Exception:
                    # Ignore malformed patterns – treat as no spec
                    self._git_spec = None
        # If respect_git_ignore requested but pathspec missing, we keep None spec.

    # ------------------------------------------------------------------
    # Public helpers
    # ------------------------------------------------------------------

    def include(self, path: Path) -> bool:
        """Return *True* if *path* should be processed, *False* otherwise."""

        # Hidden files/dirs
        if not self.show_hidden and path.name.startswith("."):
            return False

        # Custom ignore glob patterns – match against basename only
        for pattern in self.ignore_patterns:
            if fnmatch.fnmatch(path.name, pattern):
                return False

        # gitignore filtering
        if self._git_spec is not None:
            try:
                rel_path = path.relative_to(self.workspace_root)
            except ValueError:
                rel_path = path.name  # fallback – outside workspace (shouldn't happen)

            if self._git_spec.match_file(str(rel_path)):
                self.git_ignored_count += 1
                return False

        return True

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def gitignored(self) -> int:
        """Number of entries skipped due to .gitignore patterns."""

        return self.git_ignored_count 
