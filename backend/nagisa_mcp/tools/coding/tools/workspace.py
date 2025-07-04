from pathlib import Path
from typing import Union

from .config import get_tools_config

# ---------------------------------------------------------------------------
# Workspace root (static, no state)
# ---------------------------------------------------------------------------

# Workspace root from global config (created if missing)
WORKSPACE_ROOT = get_tools_config().root_dir
WORKSPACE_ROOT.mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


def validate_path_in_workspace(path: Union[str, Path]) -> str | None:  # noqa: D401
    """Return absolute path *str* if *path* is located inside ``WORKSPACE_ROOT``.

    1. Relative paths are resolved **against** ``WORKSPACE_ROOT``.
    2. Absolute paths must point inside the workspace.
    3. Returns *None* when the path escapes the workspace boundary.
    """

    # Strip leading slashes to treat "/foo" as "foo" (relative to workspace)
    # This prevents misinterpreting user-supplied "absolute" paths.
    safe_path = str(path).lstrip('/')
    p = Path(safe_path).expanduser()

    if not p.is_absolute():
        p = (WORKSPACE_ROOT / p).resolve()
    else:
        p = p.resolve()

    try:
        p.relative_to(WORKSPACE_ROOT)
    except ValueError:
        return None
    return str(p)

__all__ = ["WORKSPACE_ROOT", "validate_path_in_workspace"] 