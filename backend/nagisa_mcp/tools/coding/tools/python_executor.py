# NOTE: We purposely avoid importing *subprocess* globally at tool-registration
# time because certain sandbox environments patch it.  Import lazily inside the
# function instead if you prefer.  Here we import at module level for clarity.

import os
import subprocess
from typing import Dict, List

from pydantic import Field

from .workspace import validate_path_in_workspace

# -----------------------------------------------------------------------------
# Python script execution tool
# -----------------------------------------------------------------------------

def execute_python_script(
    path: str = Field(..., description="Path to the Python script to execute."),
    args: List[str] = Field(
        default_factory=list,
        description="Command-line arguments to pass to the script (list of strings)",
    ),
    timeout: int = Field(30, description="Maximum execution time in seconds."),
) -> Dict[str, str]:
    """Execute *path* in a **sub-process** for better isolation.

    Highlights
    ----------
    1. Runs script in a separate process using :pymod:`subprocess` – the main
       server process never executes untrusted code via ``exec``.
    2. Respects *timeout* (seconds).  An unresponsive or long-running script is
       force-killed after the allotted time, preventing denial-of-service.
    3. Standard output / error are captured and returned as strings.
    4. Exit status determines ``status`` field – ``success`` for ``returncode==0``.
    """

    # ---------------------------------------------------------------------
    # Validation & path resolution
    # ---------------------------------------------------------------------
    abs_path = validate_path_in_workspace(path)
    if abs_path is None:
        return {"status": "error", "error": f"Path is outside of workspace: {path}"}
    if not os.path.exists(abs_path):
        return {"status": "error", "error": f"Script does not exist: {path}"}
    if not os.path.isfile(abs_path):
        return {"status": "error", "error": f"Path is not a file: {path}"}

    # Ensure *args* is a list of strings – avoid accidental shell-injection risk.
    if not isinstance(args, list):
        return {"status": "error", "error": "'args' must be a list of strings"}
    str_args = [str(a) for a in args]

    # ---------------------------------------------------------------------
    # Sub-process execution
    # ---------------------------------------------------------------------
    cmd = [os.getenv("PYTHON", os.sys.executable), abs_path] + str_args
    script_dir = os.path.dirname(abs_path)

    try:
        result = subprocess.run(
            cmd,
            cwd=script_dir,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        status = "success" if result.returncode == 0 else "error"
        return {
            "status": status,
            "output": result.stdout,
            "error": result.stderr,
            "exit_code": result.returncode,
        }
    except subprocess.TimeoutExpired as exc:
        # Kill process tree if still alive; subprocess.run already does.
        return {
            "status": "error",
            "output": exc.stdout or "",
            "error": f"Script exceeded timeout of {timeout}s and was terminated.",
            "exit_code": -1,
        }
    except Exception as exc:  # pylint: disable=broad-except
        return {
            "status": "error",
            "output": "",
            "error": f"Failed to run script: {exc}",
            "exit_code": -1,
        }


# -----------------------------------------------------------------------------
# Registration helper
# -----------------------------------------------------------------------------

def register_python_executor_tools(mcp):
    mcp.tool(tags={"coding"}, annotations={"category": "coding"})(execute_python_script) 