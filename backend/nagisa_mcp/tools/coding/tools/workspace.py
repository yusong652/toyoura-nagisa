from pathlib import Path
from typing import Dict, Union
from pydantic import Field

# -----------------------------------------------------------------------------
# Workspace helpers (moved from coding.workspace to coding.tools.workspace)
# -----------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Path definitions (Pathlib flavoured)
# ---------------------------------------------------------------------------

# Resolve repo root (…/aiNagisa) – six levels up from this file
PROJECT_ROOT = Path(__file__).resolve().parents[5]

# Default workspace (…/workspace/default)
DEFAULT_WORKSPACE = PROJECT_ROOT / "workspace" / "default"
DEFAULT_WORKSPACE.mkdir(parents=True, exist_ok=True)

# Current working directory inside coding workspace (mutable)
CURRENT_CODING_CWD: Path = DEFAULT_WORKSPACE


def get_current_workspace() -> Dict[str, str]:
    """Return the current coding workspace and its root directory."""
    return {
        "workspace": str(CURRENT_CODING_CWD),
        "root": str(DEFAULT_WORKSPACE),
    }


def change_workspace(
    path: str = Field(
        ..., description="Workspace path to change to. Can be relative or absolute path."
    )
) -> Dict[str, str]:
    """Change the current workspace directory (still confined to DEFAULT_WORKSPACE)."""
    global CURRENT_CODING_CWD

    target = (DEFAULT_WORKSPACE / path).resolve()

    if DEFAULT_WORKSPACE not in target.parents and target != DEFAULT_WORKSPACE:
        return {"status": "error", "error": "Path is outside of workspace"}
    if not target.exists():
        return {"status": "error", "error": f"Directory does not exist: {path}"}
    if not target.is_dir():
        return {"status": "error", "error": f"Path is not a directory: {path}"}

    CURRENT_CODING_CWD = target
    return {
        "status": "success",
        "workspace": str(target),
        "root": str(DEFAULT_WORKSPACE),
    }


def validate_path_in_workspace(path: Union[str, Path]) -> str | None:
    """Return absolute path string if *path* lies within *DEFAULT_WORKSPACE*.

    The function accepts both absolute and workspace-relative paths.  Any path
    outside the workspace returns *None*.
    """

    p = Path(path)
    if not p.is_absolute():
        p = (CURRENT_CODING_CWD / p).resolve()
    else:
        p = p.resolve()

    try:
        p.relative_to(DEFAULT_WORKSPACE)
    except ValueError:
        return None
    return str(p)


# -----------------------------------------------------------------------------
# Registration helpers
# -----------------------------------------------------------------------------

def register_workspace_tools(mcp):
    common_kwargs = dict(tags={"coding"}, annotations={"category": "coding"})
    mcp.tool(**common_kwargs)(get_current_workspace)
    mcp.tool(**common_kwargs)(change_workspace) 