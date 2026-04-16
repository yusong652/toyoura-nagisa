"""Shared filesystem-scan helpers for coding tools.

Two concerns live here because they're consumed by both ``glob`` and ``grep``:

1. ``ripgrep`` binary discovery — enables the fast path in grep.
2. ``.gitignore`` chain loading — lets our own Python walks skip files that
   users already expect tooling to hide (matches ripgrep's default behavior).
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import List, Optional

from pathspec import GitIgnoreSpec

__all__ = [
    "RG_PATH",
    "has_ripgrep",
    "load_gitignore_spec",
]


# Resolved once at import: `None` means ripgrep is not installed. Callers
# check this to decide whether to use the fast subprocess path or fall back
# to a pure-Python implementation (e.g. Windows users without `rg`).
RG_PATH: Optional[str] = shutil.which("rg")


def has_ripgrep() -> bool:
    """Return True if a usable ``rg`` binary was found on PATH."""
    return RG_PATH is not None


def load_gitignore_spec(root: Path) -> Optional[GitIgnoreSpec]:
    """Load ``.gitignore`` rules that apply to files under ``root``.

    Walks from ``root`` up to the filesystem root to catch repo-level
    ignores above the search path (e.g. scanning ``packages/backend`` when
    the repo ``.gitignore`` lives at the monorepo root). Returns ``None``
    if no ``.gitignore`` files are found, so callers can skip matching
    entirely in the common no-gitignore case.
    """
    lines: List[str] = []
    current = root
    seen: set[Path] = set()
    # Cap at 32 parents; anything deeper is a pathological path.
    for _ in range(32):
        try:
            current = current.resolve()
        except OSError:
            break
        if current in seen:
            break
        seen.add(current)

        gi = current / ".gitignore"
        try:
            if gi.is_file():
                with gi.open("r", encoding="utf-8", errors="ignore") as fh:
                    lines.extend(fh.read().splitlines())
        except OSError:
            pass

        # Stop at filesystem root or repo root (presence of .git marker).
        if (current / ".git").exists():
            break
        parent = current.parent
        if parent == current:
            break
        current = parent

    if not lines:
        return None
    return GitIgnoreSpec.from_lines(lines)
